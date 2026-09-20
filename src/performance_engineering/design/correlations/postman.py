#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


class CorrelationError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CorrelationError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CorrelationError(
            f"Invalid JSON in {path}: line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(data, dict):
        raise CorrelationError(f"JSON root must be an object: {path}")

    return data


def walk_postman_items(
    items: list[dict[str, Any]],
    prefix: str = "",
):
    for item in items:
        name = str(item.get("name", "")).strip()
        current = f"{prefix}/{name}" if prefix else name

        if isinstance(item.get("request"), dict):
            yield current, item

        children = item.get("item")
        if isinstance(children, list):
            yield from walk_postman_items(children, current)


def event_source(item: dict[str, Any]) -> str:
    sources: list[str] = []

    for event in item.get("event", []) or []:
        if not isinstance(event, dict):
            continue

        if event.get("listen") != "test":
            continue

        script = event.get("script")
        if not isinstance(script, dict):
            continue

        lines = script.get("exec", [])

        if isinstance(lines, str):
            lines = [lines]

        if isinstance(lines, list):
            sources.extend(str(x) for x in lines)

    return "\n".join(sources)


def detect_postman_script_correlations(
    collection: dict[str, Any],
    selected_requests: set[str],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    for request_id, item in walk_postman_items(
        collection.get("item", []) or []
    ):
        if request_id not in selected_requests:
            continue

        source = event_source(item)

        if not source.strip():
            continue

        aliases: dict[str, str] = {}

        # Example:
        # var jsonData = JSON.parse(responseBody)
        for match in re.finditer(
            r"\b(?:var|let|const)\s+([A-Za-z_$][\w$]*)\s*=\s*"
            r"(?:JSON\.parse\s*\(\s*responseBody\s*\)|pm\.response\.json\s*\(\s*\))",
            source,
            flags=re.I,
        ):
            aliases[match.group(1)] = "$"

        # Example:
        # var access_token_response = jsonData['token']
        # const id = responseJson.bookingid
        assignments: dict[str, str] = {}

        for match in re.finditer(
            r"\b(?:var|let|const)\s+([A-Za-z_$][\w$]*)\s*=\s*"
            r"([A-Za-z_$][\w$]*)"
            r"(?:\[['\"]([^'\"]+)['\"]\]|\.([A-Za-z_$][\w$]*))",
            source,
        ):
            target = match.group(1)
            source_var = match.group(2)
            field = match.group(3) or match.group(4)

            if source_var in aliases:
                assignments[target] = f"$.{field}"

        # Direct set from response alias:
        # pm.globals.set("token", jsonData['token'])
        direct_pattern = re.compile(
            r"pm\.(globals|environment|collectionVariables|variables)\.set\s*\(\s*"
            r"['\"]([^'\"]+)['\"]\s*,\s*"
            r"([A-Za-z_$][\w$]*)"
            r"(?:\[['\"]([^'\"]+)['\"]\]|\.([A-Za-z_$][\w$]*))\s*\)",
            flags=re.I,
        )

        for match in direct_pattern.finditer(source):
            scope = match.group(1)
            variable = match.group(2)
            source_var = match.group(3)
            field = match.group(4) or match.group(5)

            if source_var in aliases:
                results.append(
                    {
                        "runtime_variable": variable,
                        "producer": request_id,
                        "json_path": f"$.{field}",
                        "source": "POSTMAN_SCRIPT",
                        "postman_scope": scope.upper(),
                        "confidence": "HIGH",
                        "status": "RESOLVED",
                    }
                )

        # Set from intermediate assignment:
        # pm.globals.set("access_token", access_token_response)
        set_pattern = re.compile(
            r"pm\.(globals|environment|collectionVariables|variables)\.set\s*\(\s*"
            r"['\"]([^'\"]+)['\"]\s*,\s*([A-Za-z_$][\w$]*)\s*\)",
            flags=re.I,
        )

        for match in set_pattern.finditer(source):
            scope = match.group(1)
            variable = match.group(2)
            assigned_var = match.group(3)

            if assigned_var not in assignments:
                continue

            results.append(
                {
                    "runtime_variable": variable,
                    "producer": request_id,
                    "json_path": assignments[assigned_var],
                    "source": "POSTMAN_SCRIPT",
                    "postman_scope": scope.upper(),
                    "confidence": "HIGH",
                    "status": "RESOLVED",
                }
            )

    dedup: dict[tuple[str, str], dict[str, Any]] = {}

    for item in results:
        dedup[
            (
                item["runtime_variable"],
                item["producer"],
            )
        ] = item

    return list(dedup.values())


def candidate_by_id(
    candidates: dict[str, Any],
    candidate_id: str,
) -> dict[str, Any]:
    for candidate in candidates.get("candidates", []) or []:
        if (
            isinstance(candidate, dict)
            and candidate.get("id") == candidate_id
        ):
            return candidate

    raise CorrelationError(
        f"Candidate not found: {candidate_id}"
    )


def infer_resource_correlation(
    normalized: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    selected = set(candidate.get("requests", []) or [])

    requests = {
        req.get("id"): req
        for req in normalized.get("requests", []) or []
        if isinstance(req, dict)
        and req.get("id") in selected
    }

    create_requests: list[dict[str, Any]] = []

    for request_id, request in requests.items():
        method = str(request.get("method", "")).upper()
        path = str(
            (request.get("url") or {}).get("path", "")
        )

        if method == "POST" and path:
            create_requests.append(
                {
                    "id": request_id,
                    "path": path.rstrip("/"),
                }
            )

    static_candidates = [
        item
        for item in normalized.get(
            "static_resource_candidates",
            [],
        ) or []
        if isinstance(item, dict)
        and item.get("request_id") in selected
    ]

    if not create_requests or not static_candidates:
        return None

    # Prefer a create request whose base resource path is the prefix
    # of the downstream static-resource paths.
    best: tuple[int, dict[str, Any]] | None = None

    for create in create_requests:
        score = 0
        create_path = create["path"]

        for static in static_candidates:
            request = requests.get(
                static.get("request_id")
            )

            if not request:
                continue

            downstream_path = str(
                (request.get("url") or {}).get("path", "")
            )

            if downstream_path.startswith(
                create_path + "/"
            ):
                score += 1

        if score and (
            best is None
            or score > best[0]
        ):
            best = (score, create)

    if best is None:
        return None

    create = best[1]
    resource_name = (
        create["path"]
        .strip("/")
        .split("/")[-1]
        .replace("-", "_")
    )

    singular = (
        resource_name[:-1]
        if resource_name.endswith("s")
        else resource_name
    )

    # Common API field conventions, ordered from resource-specific
    # to generic.
    json_path_candidates = [
        f"$.{singular}id",
        f"$.{singular}_id",
        "$.id",
    ]

    runtime_variable = f"{singular}_id"

    consumers = []

    for static in static_candidates:
        request_id = static.get("request_id")
        request = requests.get(request_id)

        if not request:
            continue

        path = str(
            (request.get("url") or {}).get("path", "")
        )

        if path.startswith(
            create["path"] + "/"
        ):
            consumers.append(request_id)

    return {
        "runtime_variable": runtime_variable,
        "producer": create["id"],
        "json_path": json_path_candidates[0],
        "json_path_candidates": json_path_candidates,
        "consumers": sorted(set(consumers)),
        "source": "INFERRED_RESOURCE_LIFECYCLE",
        "confidence": "HIGH",
        "status": "RESOLVED",
        "evidence": {
            "create_path": create["path"],
            "static_resource_count": len(consumers),
        },
    }


def enrich_consumers(
    correlations: list[dict[str, Any]],
    normalized: dict[str, Any],
    candidate: dict[str, Any],
) -> None:
    selected = set(candidate.get("requests", []) or [])

    dependencies = [
        dep
        for dep in normalized.get("dependencies", []) or []
        if isinstance(dep, dict)
    ]

    for correlation in correlations:
        if correlation.get("consumers"):
            continue

        variable = correlation["runtime_variable"]
        producer = correlation["producer"]

        consumers = [
            dep.get("consumer")
            for dep in dependencies
            if dep.get("variable") == variable
            and dep.get("producer") == producer
            and dep.get("consumer") in selected
        ]

        correlation["consumers"] = sorted(
            set(x for x in consumers if x)
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve declared and inferred Postman runtime "
            "correlations for one scenario candidate."
        )
    )

    parser.add_argument("--collection", required=True)
    parser.add_argument("--normalized", required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--output", required=True)

    args = parser.parse_args()

    try:
        collection = load_json(
            Path(args.collection).expanduser().resolve()
        )
        normalized = load_json(
            Path(args.normalized).expanduser().resolve()
        )
        candidates = load_json(
            Path(args.candidates).expanduser().resolve()
        )
        output = Path(
            args.output
        ).expanduser().resolve()

        candidate = candidate_by_id(
            candidates,
            args.candidate_id,
        )

        selected = set(
            candidate.get("requests", []) or []
        )

        correlations = (
            detect_postman_script_correlations(
                collection,
                selected,
            )
        )

        resource = infer_resource_correlation(
            normalized,
            candidate,
        )

        if resource is not None:
            correlations.append(resource)

        enrich_consumers(
            correlations,
            normalized,
            candidate,
        )

        unresolved = [
            item
            for item in correlations
            if item.get("status") != "RESOLVED"
        ]

        payload = {
            "schema_version": "1.0",
            "scenario_candidate": {
                "id": candidate.get("id"),
                "type": candidate.get("type"),
            },
            "correlations": correlations,
            "summary": {
                "correlation_count": len(
                    correlations
                ),
                "resolved_count": (
                    len(correlations)
                    - len(unresolved)
                ),
                "unresolved_count": len(
                    unresolved
                ),
            },
            "ready_for_compilation": (
                len(correlations) > 0
                and not unresolved
            ),
        }

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        output.write_text(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    except CorrelationError as exc:
        print(
            f"POSTMAN CORRELATION ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print("=" * 72)
    print("POSTMAN CORRELATION RESOLUTION")
    print("=" * 72)
    print(
        f"Candidate    : {args.candidate_id}"
    )
    print(
        f"Correlations : {len(correlations)}"
    )
    print(
        f"Resolved     : "
        f"{payload['summary']['resolved_count']}"
    )
    print(
        f"Unresolved   : "
        f"{payload['summary']['unresolved_count']}"
    )

    for item in correlations:
        print()
        print(
            f"- {item['runtime_variable']} "
            f"<- {item['producer']} "
            f"{item['json_path']}"
        )
        print(
            f"  source     : {item['source']}"
        )
        print(
            f"  consumers  : "
            f"{', '.join(item.get('consumers', [])) or 'NONE'}"
        )

    print()
    print(f"Output       : {output}")
    print("=" * 72)
    print(
        "CORRELATIONS READY"
        if payload["ready_for_compilation"]
        else "CORRELATIONS REQUIRE REVIEW"
    )

    return (
        0
        if payload["ready_for_compilation"]
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
