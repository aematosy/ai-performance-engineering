#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ALLOWED_SCHEMA_VERSIONS = {
    "1.0",
    "1.1",
    "1.2",
}

ALLOWED_CANDIDATE_TYPES = {
    "AUTH",
    "HEALTH",
    "READ_ONLY",
    "WRITE",
    "DEPENDENCY_FLOW",
    "E2E_CANDIDATE",
}

BLOCKING_EXECUTION_STATUSES = {
    "REQUIRED_NOT_DEFINED",
    "REVIEW_REQUIRED",
    "EXTRACTION_STRATEGY_REQUIRED",
}


class ContextValidationError(RuntimeError):
    pass


def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8",
            )
        )
    except FileNotFoundError as exc:
        raise ContextValidationError(
            f"File not found: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ContextValidationError(
            f"Invalid JSON: line {exc.lineno}, "
            f"column {exc.colno}"
        ) from exc

    if not isinstance(data, dict):
        raise ContextValidationError(
            "Root must be a JSON object."
        )

    return data


def expect(
    obj: dict[str, Any],
    key: str,
    expected_type: type,
) -> Any:
    if key not in obj:
        raise ContextValidationError(
            f"Missing field: {key}"
        )

    value = obj[key]

    if not isinstance(
        value,
        expected_type,
    ):
        raise ContextValidationError(
            f"{key} must be "
            f"{expected_type.__name__}, got "
            f"{type(value).__name__}"
        )

    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate deterministic Postman "
            "design-context model."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
    )

    parser.add_argument(
        "--execution-ready",
        action="store_true",
    )

    args = parser.parse_args()

    path = (
        Path(args.input)
        .expanduser()
        .resolve()
    )

    try:
        data = load(path)

        schema_version = data.get(
            "schema_version"
        )

        if (
            schema_version
            not in ALLOWED_SCHEMA_VERSIONS
        ):
            raise ContextValidationError(
                "Unsupported schema_version: "
                f"{schema_version}"
            )

        expect(data, "source", dict)
        expect(data, "collection", dict)
        expect(data, "environment", dict)

        candidate = expect(
            data,
            "scenario_candidate",
            dict,
        )

        candidate_id = expect(
            candidate,
            "id",
            str,
        )

        candidate_type = expect(
            candidate,
            "type",
            str,
        )

        if (
            candidate_type
            not in ALLOWED_CANDIDATE_TYPES
        ):
            raise ContextValidationError(
                f"Unsupported candidate type: "
                f"{candidate_type}"
            )

        requests = expect(
            data,
            "requests",
            list,
        )

        if not requests:
            raise ContextValidationError(
                "Design context requires "
                "at least one request."
            )

        request_ids: set[str] = set()

        for index, request in enumerate(
            requests
        ):
            if not isinstance(
                request,
                dict,
            ):
                raise ContextValidationError(
                    f"requests[{index}] "
                    "must be an object."
                )

            request_id = expect(
                request,
                "id",
                str,
            )

            if (
                request_id
                in request_ids
            ):
                raise ContextValidationError(
                    "Duplicate request id: "
                    f"{request_id}"
                )

            request_ids.add(
                request_id
            )

            expect(
                request,
                "method",
                str,
            )
            expect(
                request,
                "url",
                dict,
            )
            expect(
                request,
                "headers",
                list,
            )
            expect(
                request,
                "auth",
                dict,
            )
            expect(
                request,
                "body",
                dict,
            )

        dependencies = expect(
            data,
            "dependencies",
            list,
        )

        for dependency in dependencies:
            if not isinstance(
                dependency,
                dict,
            ):
                raise ContextValidationError(
                    "Dependency must be "
                    "an object."
                )

            producer = expect(
                dependency,
                "producer",
                str,
            )
            consumer = expect(
                dependency,
                "consumer",
                str,
            )

            if producer not in request_ids:
                raise ContextValidationError(
                    "Dependency producer not "
                    "in selected requests: "
                    f"{producer}"
                )

            if consumer not in request_ids:
                raise ContextValidationError(
                    "Dependency consumer not "
                    "in selected requests: "
                    f"{consumer}"
                )

        expect(
            data,
            "runtime_variables",
            list,
        )

        correlations = expect(
            data,
            "correlation_requirements",
            list,
        )

        for index, item in enumerate(
            correlations
        ):
            if not isinstance(
                item,
                dict,
            ):
                raise ContextValidationError(
                    "correlation_requirements"
                    f"[{index}] must be "
                    "an object."
                )

            expect(
                item,
                "type",
                str,
            )
            expect(
                item,
                "status",
                str,
            )

        expect(
            data,
            "candidate_assertions",
            list,
        )

        unresolved = expect(
            data,
            "unresolved_variables",
            list,
        )

        unsupported = expect(
            data,
            "unsupported_features",
            list,
        )

        readiness = expect(
            data,
            "design_readiness",
            dict,
        )

        design_ready = expect(
            readiness,
            "ready_for_design",
            bool,
        )

        execution_ready = expect(
            readiness,
            "ready_for_execution",
            bool,
        )

        expected_design_ready = (
            not unresolved
            and not unsupported
        )

        if (
            design_ready
            != expected_design_ready
        ):
            raise ContextValidationError(
                "ready_for_design is "
                "inconsistent with "
                "unresolved/unsupported "
                "findings."
            )

        expected_execution_ready = (
            expected_design_ready
            and not any(
                isinstance(item, dict)
                and item.get("status")
                in BLOCKING_EXECUTION_STATUSES
                for item in correlations
            )
        )

        if (
            execution_ready
            != expected_execution_ready
        ):
            raise ContextValidationError(
                "ready_for_execution is "
                "inconsistent with blocking "
                "correlation/resource "
                "requirements."
            )

        status = (
            "FAIL"
            if args.execution_ready
            and not execution_ready
            else "PASS"
        )

    except ContextValidationError as exc:
        print("=" * 72)
        print(
            "POSTMAN DESIGN CONTEXT "
            "VALIDATION"
        )
        print("=" * 72)
        print("Status : FAIL")
        print(f"Error  : {exc}")
        print("=" * 72)
        return 2

    print("=" * 72)
    print(
        "POSTMAN DESIGN CONTEXT "
        "VALIDATION"
    )
    print("=" * 72)
    print(
        f"Status          : {status}"
    )
    print(
        f"Schema          : "
        f"{schema_version}"
    )
    print(
        f"Candidate       : "
        f"{candidate_id}"
    )
    print(
        f"Candidate type  : "
        f"{candidate_type}"
    )
    print(
        f"Requests        : "
        f"{len(requests)}"
    )
    print(
        f"Dependencies    : "
        f"{len(dependencies)}"
    )
    print(
        f"Correlations    : "
        f"{len(correlations)}"
    )
    print(
        f"Unresolved      : "
        f"{len(unresolved)}"
    )
    print(
        f"Unsupported     : "
        f"{len(unsupported)}"
    )
    print(
        f"Design ready    : "
        f"{design_ready}"
    )
    print(
        f"Execution ready : "
        f"{execution_ready}"
    )
    print("=" * 72)

    return (
        0
        if status == "PASS"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
