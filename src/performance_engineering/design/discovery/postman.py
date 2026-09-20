#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


READ_METHODS = {"GET", "HEAD", "OPTIONS"}
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

HEALTH_HINTS = re.compile(
    r"(?:^|[/_\-\s])(health|healthcheck|ping|ready|readiness|live|liveness|status)(?:$|[/_\-\s])",
    re.I,
)
AUTH_HINTS = re.compile(
    r"(?:^|[/_\-\s])(auth|login|token|oauth|signin|session)(?:$|[/_\-\s])",
    re.I,
)

GENERIC_RESOURCE_SEGMENTS = {
    "api", "v1", "v2", "v3", "rest", "graphql",
    "health", "healthcheck", "ping", "status",
    "auth", "login", "token",
}

METHOD_ORDER = {
    "POST": 10,
    "GET": 20,
    "HEAD": 21,
    "OPTIONS": 22,
    "PUT": 30,
    "PATCH": 31,
    "DELETE": 40,
}

TEMPLATE_PATTERN = re.compile(r"\{\{[^{}]+\}\}")


class DiscoveryError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DiscoveryError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DiscoveryError(
            f"Invalid JSON in {path}: line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(data, dict):
        raise DiscoveryError("Normalized model root must be an object.")

    if data.get("schema_version") != "2.0":
        raise DiscoveryError(
            "Expected normalized Postman schema_version 2.0, "
            f"got {data.get('schema_version')}"
        )

    return data


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "scenario"


def request_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    requests = data.get("requests", [])
    if not isinstance(requests, list):
        raise DiscoveryError("requests must be a list.")

    result: dict[str, dict[str, Any]] = {}
    for request in requests:
        if not isinstance(request, dict):
            raise DiscoveryError("Every request must be an object.")

        request_id = request.get("id")
        if not isinstance(request_id, str) or not request_id:
            raise DiscoveryError("Every request requires a non-empty id.")

        if request_id in result:
            raise DiscoveryError(f"Duplicate request id: {request_id}")

        result[request_id] = request

    return result


def dynamic_runtime_variables(data: dict[str, Any]) -> set[str]:
    variables = data.get("variables", {})
    if not isinstance(variables, dict):
        return set()

    runtime = variables.get("dynamic_runtime", [])
    if not isinstance(runtime, list):
        return set()

    return {str(item) for item in runtime if str(item).strip()}


def build_graph(
    data: dict[str, Any],
) -> tuple[
    dict[str, set[str]],
    dict[str, set[str]],
    dict[tuple[str, str], set[str]],
]:
    forward: dict[str, set[str]] = defaultdict(set)
    reverse: dict[str, set[str]] = defaultdict(set)
    edge_variables: dict[tuple[str, str], set[str]] = defaultdict(set)

    for edge in data.get("dependencies", []):
        if not isinstance(edge, dict):
            continue

        producer = edge.get("producer")
        consumer = edge.get("consumer")
        variable = edge.get("variable")

        if (
            isinstance(producer, str)
            and isinstance(consumer, str)
            and isinstance(variable, str)
        ):
            forward[producer].add(consumer)
            reverse[consumer].add(producer)
            edge_variables[(producer, consumer)].add(variable)

    return forward, reverse, edge_variables


def dependency_closure(
    target: str,
    reverse: dict[str, set[str]],
) -> list[str]:
    ancestors: set[str] = set()
    queue = deque([target])

    while queue:
        current = queue.popleft()
        for producer in sorted(reverse.get(current, set())):
            if producer in ancestors:
                continue
            ancestors.add(producer)
            queue.append(producer)

    ordered: list[str] = []
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visited:
            return
        for producer in sorted(reverse.get(node, set())):
            if producer in ancestors:
                visit(producer)
        visited.add(node)
        ordered.append(node)

    for node in sorted(ancestors):
        visit(node)

    ordered.append(target)
    return ordered


def root_folder(request: dict[str, Any]) -> str:
    folders = request.get("folder_path", [])
    if isinstance(folders, list) and folders:
        return str(folders[0])
    return "root"


def derive_path_from_template_url(raw: str) -> str:
    """
    Recover a path even when the URL host contains unresolved Postman variables.

    Examples:
      {{baseUrl}}/orders/123 -> /orders/123
      https://{{host}}/orders -> /orders
      {{protocol}}://{{host}}/v1/users -> /v1/users
    """
    if not raw:
        return ""

    candidate = raw.strip()

    # Replace each template with a syntactically safe placeholder.
    safe = TEMPLATE_PATTERN.sub("placeholder", candidate)

    try:
        parsed = urlsplit(safe)
        if parsed.scheme and parsed.netloc:
            return parsed.path or "/"
    except ValueError:
        pass

    # Common Postman pattern: {{baseUrl}}/path
    match = re.match(r"^\{\{[^{}]+\}\}(?P<path>/.*)?$", candidate)
    if match:
        return match.group("path") or "/"

    # Fallback for unresolved scheme/host templates.
    scheme_match = re.match(
        r"^(?:\{\{[^{}]+\}\}|https?|http)://(?:\{\{[^{}]+\}\}|[^/]+)(?P<path>/.*)?$",
        candidate,
        re.I,
    )
    if scheme_match:
        return scheme_match.group("path") or "/"

    if candidate.startswith("/"):
        return candidate.split("?", 1)[0]

    return ""


def request_path(request: dict[str, Any]) -> str:
    url = request.get("url", {})
    if not isinstance(url, dict):
        return ""

    path = url.get("path")
    if isinstance(path, str) and path:
        return path

    for key in ("resolved", "raw"):
        value = url.get(key)
        if isinstance(value, str) and value:
            derived = derive_path_from_template_url(value)
            if derived:
                return derived

    return ""


def unresolved_for_request(request: dict[str, Any]) -> list[str]:
    url = request.get("url", {})
    if not isinstance(url, dict):
        return []

    values = url.get("unresolved_variables", [])
    if not isinstance(values, list):
        return []

    return sorted(
        {
            str(value)
            for value in values
            if str(value).strip()
        }
    )


def unresolved_for_requests(
    request_ids: list[str],
    requests: dict[str, dict[str, Any]],
) -> list[str]:
    result: set[str] = set()
    for request_id in request_ids:
        result.update(
            unresolved_for_request(
                requests[request_id]
            )
        )
    return sorted(result)


def resource_key(request: dict[str, Any]) -> str | None:
    path = request_path(request)
    if not path:
        return None

    path = path.split("?", 1)[0]
    segments = [segment for segment in path.split("/") if segment]
    filtered: list[str] = []

    for segment in segments:
        lowered = segment.lower()

        if lowered in GENERIC_RESOURCE_SEGMENTS:
            continue
        if re.fullmatch(r"\d+", segment):
            continue
        if re.fullmatch(r"[0-9a-fA-F-]{32,36}", segment):
            continue
        if "{{" in segment or "}}" in segment:
            continue

        filtered.append(lowered)

    return filtered[0] if filtered else None


def has_static_resource_id(request: dict[str, Any]) -> bool:
    candidates = request.get("static_resource_candidates", [])
    return isinstance(candidates, list) and bool(candidates)


def is_health(request: dict[str, Any]) -> bool:
    searchable = f"{request.get('id', '')} {request_path(request)}"
    return bool(HEALTH_HINTS.search(searchable))


def is_auth(request: dict[str, Any]) -> bool:
    searchable = f"{request.get('id', '')} {request_path(request)}"
    return bool(AUTH_HINTS.search(searchable))


def request_sort_key(
    request_id: str,
    requests: dict[str, dict[str, Any]],
) -> tuple[int, str]:
    method = str(requests[request_id].get("method", "")).upper()
    return METHOD_ORDER.get(method, 99), request_id


def unique_candidate_id(
    base: str,
    candidate_type: str,
    used: set[str],
) -> str:
    base_slug = slugify(base)
    type_slug = slugify(candidate_type)

    candidate_id = f"{base_slug}-{type_slug}"
    if candidate_id not in used:
        used.add(candidate_id)
        return candidate_id

    suffix = 2
    while f"{candidate_id}-{suffix}" in used:
        suffix += 1

    final_id = f"{candidate_id}-{suffix}"
    used.add(final_id)
    return final_id


def required_runtime_variables(
    request_ids: list[str],
    data: dict[str, Any],
    edge_variables: dict[tuple[str, str], set[str]],
    requests: dict[str, dict[str, Any]],
) -> list[str]:
    runtime = dynamic_runtime_variables(data)
    if not runtime:
        return []

    required: set[str] = set()

    for request_id in request_ids:
        request = requests[request_id]
        for reference in request.get("variable_references", []):
            if isinstance(reference, str) and reference in runtime:
                required.add(reference)

    for producer in request_ids:
        for consumer in request_ids:
            for variable in edge_variables.get((producer, consumer), set()):
                if variable in runtime:
                    required.add(variable)

    return sorted(required)


def confidence_for(
    request_ids: list[str],
    requests: dict[str, dict[str, Any]],
    warnings: list[str],
) -> str:
    if unresolved_for_requests(request_ids, requests):
        return "MEDIUM"

    if warnings:
        return "MEDIUM"

    if all(
        not requests[request_id].get("unsupported_features")
        for request_id in request_ids
    ):
        return "HIGH"

    return "LOW"


def build_candidate(
    *,
    candidate_id: str,
    candidate_type: str,
    request_ids: list[str],
    requests: dict[str, dict[str, Any]],
    data: dict[str, Any],
    edge_variables: dict[tuple[str, str], set[str]],
    warnings: list[str] | None = None,
    risks: list[str] | None = None,
    requires_correlation: bool = False,
    rationale: str = "",
) -> dict[str, Any]:
    warnings = list(warnings or [])
    risks = list(risks or [])

    unresolved = unresolved_for_requests(
        request_ids,
        requests,
    )

    if unresolved:
        warnings.append(
            "Scenario contains unresolved input variable(s): "
            + ", ".join(unresolved)
        )

    unsupported = sorted(
        {
            feature
            for request_id in request_ids
            for feature in requests[request_id].get(
                "unsupported_features",
                [],
            )
        }
    )

    return {
        "id": candidate_id,
        "type": candidate_type,
        "requests": request_ids,
        "required_runtime_variables": required_runtime_variables(
            request_ids,
            data,
            edge_variables,
            requests,
        ),
        "unresolved_variables": unresolved,
        "requires_correlation": requires_correlation,
        "warnings": warnings,
        "risks": risks,
        "unsupported_features": unsupported,
        "confidence": confidence_for(
            request_ids,
            requests,
            warnings + unsupported,
        ),
        "rationale": rationale,
    }


def discover(data: dict[str, Any]) -> list[dict[str, Any]]:
    requests = request_map(data)
    _, reverse, edge_variables = build_graph(data)

    candidates: list[dict[str, Any]] = []
    seen_shapes: set[tuple[str, tuple[str, ...]]] = set()
    used_ids: set[str] = set()

    def add(
        *,
        base_id: str,
        candidate_type: str,
        request_ids: list[str],
        warnings: list[str] | None = None,
        risks: list[str] | None = None,
        requires_correlation: bool = False,
        rationale: str = "",
    ) -> None:
        shape = (candidate_type, tuple(request_ids))
        if shape in seen_shapes:
            return

        seen_shapes.add(shape)

        cid = unique_candidate_id(
            base_id,
            candidate_type,
            used_ids,
        )

        candidates.append(
            build_candidate(
                candidate_id=cid,
                candidate_type=candidate_type,
                request_ids=request_ids,
                requests=requests,
                data=data,
                edge_variables=edge_variables,
                warnings=warnings,
                risks=risks,
                requires_correlation=requires_correlation,
                rationale=rationale,
            )
        )

    auth_request_ids: set[str] = set()
    for request_id, request in requests.items():
        if is_auth(request):
            auth_request_ids.add(request_id)
            add(
                base_id=request_id,
                candidate_type="AUTH",
                request_ids=[request_id],
                rationale="Authentication/token-oriented request detected.",
            )

    health_request_ids: set[str] = set()
    for request_id, request in requests.items():
        if is_health(request):
            health_request_ids.add(request_id)
            add(
                base_id=request_id,
                candidate_type="HEALTH",
                request_ids=[request_id],
                rationale="Health/ping/status endpoint detected.",
            )

    read_groups: dict[str, list[str]] = defaultdict(list)
    for request_id, request in requests.items():
        method = str(request.get("method", "")).upper()
        if method in READ_METHODS and request_id not in health_request_ids:
            read_groups[root_folder(request)].append(request_id)

    for folder, request_ids in sorted(read_groups.items()):
        request_ids = sorted(
            request_ids,
            key=lambda item: request_sort_key(item, requests),
        )

        if request_ids:
            add(
                base_id=f"{folder}-read",
                candidate_type="READ_ONLY",
                request_ids=request_ids,
                rationale=(
                    f"Read-only requests grouped from folder '{folder}'."
                ),
            )

    for request_id, request in requests.items():
        method = str(request.get("method", "")).upper()

        if method not in WRITE_METHODS:
            continue
        if request_id in auth_request_ids:
            continue
        if request_id in health_request_ids:
            continue
        if reverse.get(request_id):
            continue

        warnings = []
        if has_static_resource_id(request):
            warnings.append(
                "Request targets a static resource identifier."
            )

        add(
            base_id=request_id,
            candidate_type="WRITE",
            request_ids=[request_id],
            warnings=warnings,
            rationale="Independent mutating request detected.",
        )

    for request_id, request in requests.items():
        if not reverse.get(request_id):
            continue

        flow_ids = dependency_closure(request_id, reverse)
        warnings = []

        if has_static_resource_id(request):
            warnings.append(
                "Target request uses a static resource identifier."
            )

        add(
            base_id=f"{request_id}-dependency",
            candidate_type="DEPENDENCY_FLOW",
            request_ids=flow_ids,
            warnings=warnings,
            rationale=(
                "Runtime variable producer/consumer dependency detected."
            ),
        )

    resources: dict[str, list[str]] = defaultdict(list)

    for request_id, request in requests.items():
        key = resource_key(request)
        if key:
            resources[key].append(request_id)

    for resource, request_ids in sorted(resources.items()):
        methods = {
            str(requests[request_id].get("method", "")).upper()
            for request_id in request_ids
        }

        has_create = "POST" in methods
        has_read = bool(methods & READ_METHODS)
        has_modify = bool(methods & {"PUT", "PATCH"})
        has_delete = "DELETE" in methods

        if sum([has_create, has_read, has_modify, has_delete]) < 3:
            continue

        producer_ids: set[str] = set()
        for request_id in request_ids:
            producer_ids.update(reverse.get(request_id, set()))

        lifecycle_ids = sorted(
            request_ids,
            key=lambda item: request_sort_key(item, requests),
        )

        ordered_flow = sorted(producer_ids) + [
            request_id
            for request_id in lifecycle_ids
            if request_id not in producer_ids
        ]

        static_request_ids = [
            request_id
            for request_id in request_ids
            if has_static_resource_id(requests[request_id])
        ]

        warnings = []
        requires_correlation = False

        if has_create and static_request_ids:
            requires_correlation = True
            warnings.append(
                "Create operation exists but downstream requests use "
                "static resource identifiers; dynamic resource-id "
                "extraction/correlation is required before reliable "
                "E2E execution."
            )

        add(
            base_id=f"{resource}-e2e",
            candidate_type="E2E_CANDIDATE",
            request_ids=ordered_flow,
            warnings=warnings,
            requires_correlation=requires_correlation,
            rationale=(
                "Multiple CRUD lifecycle operations detected for "
                f"inferred resource '{resource}'."
            ),
        )

    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Discover deterministic performance scenario candidates "
            "from normalized Postman v2."
        )
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()

    try:
        data = load_json(input_path)
        candidates = discover(data)

        result = {
            "schema_version": "1.2",
            "source_model": str(input_path),
            "collection": data.get("collection", {}).get("name"),
            "candidate_count": len(candidates),
            "candidates": candidates,
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    except DiscoveryError as exc:
        print(
            f"SCENARIO DISCOVERY ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print("=" * 72)
    print("POSTMAN SCENARIO DISCOVERY v1.2")
    print("=" * 72)
    print(f"Collection : {result['collection']}")
    print(f"Candidates : {result['candidate_count']}")
    print(f"Output     : {output_path}")
    print()

    for index, item in enumerate(candidates, 1):
        print(
            f"{index:02d}. {item['id']} | {item['type']} | "
            f"{len(item['requests'])} request(s) | "
            f"{item['confidence']}"
        )

        if item["unresolved_variables"]:
            print(
                "    unresolved: "
                + ", ".join(item["unresolved_variables"])
            )

        if item["requires_correlation"]:
            print("    requires_correlation: true")

    print("=" * 72)
    print("DISCOVERY COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
