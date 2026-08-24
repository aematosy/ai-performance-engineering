#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ALLOWED_SCHEMA_VERSIONS = {"1.0", "1.1", "1.2"}
ALLOWED_TYPES = {
    "AUTH",
    "HEALTH",
    "READ_ONLY",
    "WRITE",
    "DEPENDENCY_FLOW",
    "E2E_CANDIDATE",
}
ALLOWED_CONFIDENCE = {"LOW", "MEDIUM", "HIGH"}


class CandidateValidationError(RuntimeError):
    pass


def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CandidateValidationError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CandidateValidationError(
            f"Invalid JSON: line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(data, dict):
        raise CandidateValidationError("Root must be a JSON object.")
    return data


def expect(
    obj: dict[str, Any],
    key: str,
    expected_type: type,
) -> Any:
    if key not in obj:
        raise CandidateValidationError(f"Missing field: {key}")

    value = obj[key]

    if not isinstance(value, expected_type):
        raise CandidateValidationError(
            f"{key} must be {expected_type.__name__}, "
            f"got {type(value).__name__}"
        )

    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate deterministic Postman scenario candidates."
    )
    parser.add_argument("--input", required=True)
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Fail if any candidate contains unsupported features "
            "or unresolved variables."
        ),
    )
    args = parser.parse_args()

    path = Path(args.input).expanduser().resolve()

    try:
        data = load(path)

        schema_version = data.get("schema_version")
        if schema_version not in ALLOWED_SCHEMA_VERSIONS:
            raise CandidateValidationError(
                f"Unsupported schema_version: {schema_version}"
            )

        candidates = expect(data, "candidates", list)

        if data.get("candidate_count") != len(candidates):
            raise CandidateValidationError(
                "candidate_count does not match candidates length."
            )

        ids: set[str] = set()
        unsupported_total = 0
        unresolved_total = 0

        for index, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                raise CandidateValidationError(
                    f"candidates[{index}] must be an object."
                )

            candidate_id = expect(candidate, "id", str)

            if candidate_id in ids:
                raise CandidateValidationError(
                    f"Duplicate candidate id: {candidate_id}"
                )
            ids.add(candidate_id)

            candidate_type = expect(candidate, "type", str)
            if candidate_type not in ALLOWED_TYPES:
                raise CandidateValidationError(
                    f"Unsupported candidate type: {candidate_type}"
                )

            request_ids = expect(candidate, "requests", list)
            if (
                not request_ids
                or not all(
                    isinstance(item, str) and item
                    for item in request_ids
                )
            ):
                raise CandidateValidationError(
                    f"Candidate {candidate_id} must contain "
                    "non-empty request ids."
                )

            expect(candidate, "required_runtime_variables", list)

            if schema_version == "1.2":
                unresolved = expect(
                    candidate,
                    "unresolved_variables",
                    list,
                )
                unresolved_total += len(unresolved)

            expect(candidate, "requires_correlation", bool)
            expect(candidate, "warnings", list)
            expect(candidate, "risks", list)

            unsupported = expect(
                candidate,
                "unsupported_features",
                list,
            )
            unsupported_total += len(unsupported)

            confidence = expect(
                candidate,
                "confidence",
                str,
            )
            if confidence not in ALLOWED_CONFIDENCE:
                raise CandidateValidationError(
                    f"Invalid confidence for {candidate_id}: {confidence}"
                )

            expect(candidate, "rationale", str)

        status = (
            "FAIL"
            if args.strict
            and (unsupported_total or unresolved_total)
            else "PASS"
        )

    except CandidateValidationError as exc:
        print("=" * 72)
        print("POSTMAN SCENARIO CANDIDATE VALIDATION")
        print("=" * 72)
        print("Status : FAIL")
        print(f"Error  : {exc}")
        print("=" * 72)
        return 2

    print("=" * 72)
    print("POSTMAN SCENARIO CANDIDATE VALIDATION")
    print("=" * 72)
    print(f"Status      : {status}")
    print(f"Schema      : {schema_version}")
    print(f"Candidates  : {len(candidates)}")
    print(f"Unresolved  : {unresolved_total}")
    print(f"Unsupported : {unsupported_total}")
    print("=" * 72)

    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
