#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

BLOCKING_EXECUTION_STATUSES = {
    "REQUIRED_NOT_DEFINED",
    "REVIEW_REQUIRED",
    "EXTRACTION_STRATEGY_REQUIRED",
}


class DesignContextError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DesignContextError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DesignContextError(
            f"Invalid JSON in {path}: line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(data, dict):
        raise DesignContextError(f"JSON root must be an object: {path}")
    return data


def build_request_map(
    normalized: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    requests = normalized.get("requests", [])
    if not isinstance(requests, list):
        raise DesignContextError("normalized.requests must be a list.")

    result: dict[str, dict[str, Any]] = {}
    for request in requests:
        if not isinstance(request, dict):
            raise DesignContextError(
                "Every normalized request must be an object."
            )

        request_id = request.get("id")
        if not isinstance(request_id, str) or not request_id:
            raise DesignContextError(
                "Every normalized request requires a non-empty id."
            )

        if request_id in result:
            raise DesignContextError(
                f"Duplicate normalized request id: {request_id}"
            )

        result[request_id] = request

    return result


def select_candidate(
    candidates_model: dict[str, Any],
    candidate_id: str,
) -> dict[str, Any]:
    candidates = candidates_model.get("candidates", [])
    if not isinstance(candidates, list):
        raise DesignContextError(
            "scenario-candidates.candidates must be a list."
        )

    matches = [
        item
        for item in candidates
        if isinstance(item, dict)
        and item.get("id") == candidate_id
    ]

    if not matches:
        raise DesignContextError(
            f"Candidate not found: {candidate_id}"
        )

    if len(matches) > 1:
        raise DesignContextError(
            f"Candidate id is not unique: {candidate_id}"
        )

    return matches[0]


def minimize_request(
    request: dict[str, Any],
) -> dict[str, Any]:
    url = request.get("url", {})
    if not isinstance(url, dict):
        url = {}

    body = request.get("body", {})
    if not isinstance(body, dict):
        body = {}

    auth = request.get("auth", {})
    if not isinstance(auth, dict):
        auth = {}

    headers = request.get("headers", [])
    if not isinstance(headers, list):
        headers = []

    return {
        "id": request.get("id"),
        "name": request.get("name"),
        "folder_path": request.get("folder_path", []),
        "method": request.get("method"),
        "url": {
            "raw": url.get("raw"),
            "resolved": url.get("resolved"),
            "protocol": url.get("protocol"),
            "host": url.get("host"),
            "port": url.get("port"),
            "path": url.get("path"),
            "unresolved_variables": url.get(
                "unresolved_variables",
                [],
            ),
        },
        "headers": [
            {
                "key": item.get("key"),
                "value": item.get("value"),
                "sensitive": item.get("sensitive", False),
                "disabled": item.get("disabled", False),
                "variable_references": item.get(
                    "variable_references",
                    [],
                ),
            }
            for item in headers
            if isinstance(item, dict)
        ],
        "query": request.get("query", []),
        "path_variables": request.get(
            "path_variables",
            [],
        ),
        "auth": {
            "type": auth.get("type"),
            "unsupported": auth.get(
                "unsupported",
                False,
            ),
            "details": auth.get("details", []),
        },
        "body": {
            "mode": body.get("mode"),
            "content": body.get("content"),
            "unsupported": body.get(
                "unsupported",
                False,
            ),
        },
        "variable_references": request.get(
            "variable_references",
            [],
        ),
        "variables_created": request.get(
            "variables_created",
            [],
        ),
        "candidate_assertions": request.get(
            "candidate_assertions",
            [],
        ),
        "static_resource_candidates": request.get(
            "static_resource_candidates",
            [],
        ),
        "unsupported_features": request.get(
            "unsupported_features",
            [],
        ),
    }


def select_dependencies(
    normalized: dict[str, Any],
    selected_request_ids: set[str],
) -> list[dict[str, Any]]:
    dependencies = normalized.get("dependencies", [])
    if not isinstance(dependencies, list):
        return []

    return [
        dependency
        for dependency in dependencies
        if isinstance(dependency, dict)
        and dependency.get("producer") in selected_request_ids
        and dependency.get("consumer") in selected_request_ids
    ]


def producer_variable_definition(
    producer_request: dict[str, Any],
    variable: str,
) -> dict[str, Any] | None:
    created = producer_request.get(
        "variables_created",
        [],
    )

    if not isinstance(created, list):
        return None

    for item in created:
        if (
            isinstance(item, dict)
            and item.get("name") == variable
        ):
            return item

    return None


def runtime_dependency_requirement(
    dependency: dict[str, Any],
    requests_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    variable = str(
        dependency.get("variable", "")
    )
    producer = str(
        dependency.get("producer", "")
    )
    consumer = str(
        dependency.get("consumer", "")
    )

    producer_request = requests_by_id[
        producer
    ]

    variable_definition = (
        producer_variable_definition(
            producer_request,
            variable,
        )
    )

    extraction = (
        variable_definition.get("extraction")
        if isinstance(
            variable_definition,
            dict,
        )
        else None
    )

    if (
        isinstance(extraction, dict)
        and extraction.get("type")
        and extraction.get("expression")
    ):
        return {
            "type": "RUNTIME_VARIABLE",
            "variable": variable,
            "producer": producer,
            "consumer": consumer,
            "status": "DETECTED",
            "extraction": extraction,
        }

    return {
        "type": "RUNTIME_VARIABLE",
        "variable": variable,
        "producer": producer,
        "consumer": consumer,
        "status": "EXTRACTION_STRATEGY_REQUIRED",
        "extraction": None,
        "message": (
            "Runtime producer/consumer relationship was "
            "detected, but no deterministic extraction "
            "strategy is present in the normalized model. "
            "Define the extractor before execution."
        ),
    }


def collect_static_resource_findings(
    requests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for request in requests:
        request_id = request.get("id")
        method = str(
            request.get("method", "")
        ).upper()

        for candidate in request.get(
            "static_resource_candidates",
            [],
        ):
            if not isinstance(
                candidate,
                dict,
            ):
                continue

            result.append(
                {
                    "request_id": request_id,
                    "method": method,
                    **candidate,
                }
            )

    return result


def collect_candidate_assertions(
    requests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for request in requests:
        request_id = request.get("id")

        for assertion in request.get(
            "candidate_assertions",
            [],
        ):
            if not isinstance(
                assertion,
                dict,
            ):
                continue

            result.append(
                {
                    "request_id": request_id,
                    **assertion,
                }
            )

    return result


def collect_unsupported(
    requests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for request in requests:
        request_id = request.get("id")

        for feature in request.get(
            "unsupported_features",
            [],
        ):
            result.append(
                {
                    "request_id": request_id,
                    "feature": feature,
                }
            )

    return result


def collect_unresolved(
    requests: list[dict[str, Any]],
) -> list[str]:
    result: set[str] = set()

    for request in requests:
        url = request.get("url", {})
        if not isinstance(url, dict):
            continue

        for variable in url.get(
            "unresolved_variables",
            [],
        ):
            if isinstance(
                variable,
                str,
            ):
                result.add(variable)

    return sorted(result)


def build_correlation_requirements(
    candidate: dict[str, Any],
    requests: list[dict[str, Any]],
    dependencies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []

    requests_by_id = {
        str(request["id"]): request
        for request in requests
    }

    for dependency in dependencies:
        requirements.append(
            runtime_dependency_requirement(
                dependency,
                requests_by_id,
            )
        )

    static_findings = (
        collect_static_resource_findings(
            requests
        )
    )

    mutating_static_findings = [
        item
        for item in static_findings
        if item.get("method")
        in MUTATING_METHODS
    ]

    if candidate.get(
        "requires_correlation"
    ):
        requirements.append(
            {
                "type": "RESOURCE_ID",
                "variable": None,
                "producer": None,
                "consumer": None,
                "status": (
                    "REQUIRED_NOT_DEFINED"
                ),
                "evidence": static_findings,
                "message": (
                    "Scenario requires dynamic "
                    "resource-id correlation before "
                    "reliable E2E execution."
                ),
            }
        )
    elif mutating_static_findings:
        requirements.append(
            {
                "type": (
                    "STATIC_RESOURCE_STRATEGY"
                ),
                "variable": None,
                "producer": None,
                "consumer": None,
                "status": "REVIEW_REQUIRED",
                "evidence": (
                    mutating_static_findings
                ),
                "message": (
                    "Mutating request(s) target "
                    "static resource identifiers. "
                    "Define an explicit resource "
                    "strategy before execution."
                ),
            }
        )

    return requirements


def blocking_execution_requirement(
    requirement: dict[str, Any],
) -> bool:
    return requirement.get("status") in (
        BLOCKING_EXECUTION_STATUSES
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare minimal deterministic design "
            "context for one Postman scenario "
            "candidate."
        )
    )

    parser.add_argument(
        "--normalized",
        required=True,
    )
    parser.add_argument(
        "--candidates",
        required=True,
    )
    parser.add_argument(
        "--candidate-id",
        required=True,
    )
    parser.add_argument(
        "--output",
        required=True,
    )

    args = parser.parse_args()

    normalized_path = (
        Path(args.normalized)
        .expanduser()
        .resolve()
    )
    candidates_path = (
        Path(args.candidates)
        .expanduser()
        .resolve()
    )
    output_path = (
        Path(args.output)
        .expanduser()
        .resolve()
    )

    try:
        normalized = load_json(
            normalized_path
        )
        candidates_model = load_json(
            candidates_path
        )

        if (
            normalized.get("schema_version")
            != "2.0"
        ):
            raise DesignContextError(
                "Normalized Postman model must "
                "use schema_version 2.0."
            )

        if candidates_model.get(
            "schema_version"
        ) not in {"1.0", "1.1"}:
            raise DesignContextError(
                "Scenario candidates model must "
                "use schema_version 1.0 or 1.1."
            )

        candidate = select_candidate(
            candidates_model,
            args.candidate_id,
        )

        request_ids = candidate.get(
            "requests",
            [],
        )

        if (
            not isinstance(
                request_ids,
                list,
            )
            or not request_ids
        ):
            raise DesignContextError(
                "Selected candidate has no "
                "requests."
            )

        requests_by_id = build_request_map(
            normalized
        )

        missing = [
            request_id
            for request_id in request_ids
            if request_id
            not in requests_by_id
        ]

        if missing:
            raise DesignContextError(
                "Candidate references unknown "
                "request ids: "
                + ", ".join(missing)
            )

        selected_requests = [
            minimize_request(
                requests_by_id[
                    request_id
                ]
            )
            for request_id in request_ids
        ]

        dependencies = select_dependencies(
            normalized,
            set(request_ids),
        )

        correlations = (
            build_correlation_requirements(
                candidate,
                selected_requests,
                dependencies,
            )
        )

        unsupported = collect_unsupported(
            selected_requests
        )

        unresolved = collect_unresolved(
            selected_requests
        )

        design_ready = (
            not unsupported
            and not unresolved
        )

        execution_ready = (
            design_ready
            and not any(
                blocking_execution_requirement(
                    item
                )
                for item in correlations
            )
        )

        context = {
            "schema_version": "1.2",
            "source": {
                "normalized_model": str(
                    normalized_path
                ),
                "scenario_candidates": str(
                    candidates_path
                ),
            },
            "collection": normalized.get(
                "collection",
                {},
            ),
            "environment": normalized.get(
                "environment",
                {},
            ),
            "scenario_candidate": {
                "id": candidate.get("id"),
                "type": candidate.get(
                    "type"
                ),
                "confidence": candidate.get(
                    "confidence"
                ),
                "requires_correlation": (
                    candidate.get(
                        "requires_correlation",
                        False,
                    )
                ),
                "warnings": candidate.get(
                    "warnings",
                    [],
                ),
                "risks": candidate.get(
                    "risks",
                    [],
                ),
                "rationale": candidate.get(
                    "rationale",
                    "",
                ),
            },
            "requests": selected_requests,
            "dependencies": dependencies,
            "runtime_variables": candidate.get(
                "required_runtime_variables",
                [],
            ),
            "correlation_requirements": (
                correlations
            ),
            "candidate_assertions": (
                collect_candidate_assertions(
                    selected_requests
                )
            ),
            "unresolved_variables": (
                unresolved
            ),
            "unsupported_features": (
                unsupported
            ),
            "design_readiness": {
                "ready_for_design": (
                    design_ready
                ),
                "ready_for_execution": (
                    execution_ready
                ),
            },
        }

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path.write_text(
            json.dumps(
                context,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    except DesignContextError as exc:
        print(
            f"DESIGN CONTEXT ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print("=" * 72)
    print("POSTMAN DESIGN CONTEXT v1.2")
    print("=" * 72)
    print(
        "Candidate   :",
        context[
            "scenario_candidate"
        ]["id"],
    )
    print(
        "Type        :",
        context[
            "scenario_candidate"
        ]["type"],
    )
    print(
        "Requests    :",
        len(context["requests"]),
    )
    print(
        "Dependencies:",
        len(context["dependencies"]),
    )
    print(
        "Runtime vars:",
        len(context["runtime_variables"]),
    )
    print(
        "Correlations:",
        len(
            context[
                "correlation_requirements"
            ]
        ),
    )
    print(
        "Unsupported :",
        len(
            context[
                "unsupported_features"
            ]
        ),
    )
    print(
        "Unresolved  :",
        len(
            context[
                "unresolved_variables"
            ]
        ),
    )
    print(
        "Design ready:",
        context[
            "design_readiness"
        ]["ready_for_design"],
    )
    print(
        "Exec ready  :",
        context[
            "design_readiness"
        ]["ready_for_execution"],
    )
    print(
        "Output      :",
        output_path,
    )
    print("=" * 72)
    print("DESIGN CONTEXT READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
