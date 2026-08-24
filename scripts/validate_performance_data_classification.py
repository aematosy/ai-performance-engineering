#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ALLOWED_SCHEMA_VERSIONS = {"1.0", "1.1"}

ALLOWED_CLASSES = {
    "CONFIGURATION",
    "TEST_DATA_CANDIDATE",
    "RUNTIME_CORRELATED",
    "SECRET",
}


class DataRequirementsValidationError(RuntimeError):
    pass


def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DataRequirementsValidationError(
            f"File not found: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise DataRequirementsValidationError(
            f"Invalid JSON: line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(data, dict):
        raise DataRequirementsValidationError(
            "Root must be a JSON object."
        )
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate classified performance-data model."
    )
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    path = Path(args.input).expanduser().resolve()

    try:
        data = load(path)

        schema_version = data.get("schema_version")
        if schema_version not in ALLOWED_SCHEMA_VERSIONS:
            raise DataRequirementsValidationError(
                f"Unsupported schema_version: {schema_version}"
            )

        classification = data.get("classification")
        if not isinstance(classification, dict):
            raise DataRequirementsValidationError(
                "classification must be an object."
            )

        total = 0
        names_by_section: dict[str, set[str]] = {}

        for section in (
            "configuration",
            "test_data",
            "runtime_correlated",
            "secrets",
        ):
            values = classification.get(section)
            if not isinstance(values, list):
                raise DataRequirementsValidationError(
                    f"classification.{section} must be a list."
                )

            names: set[str] = set()

            for index, item in enumerate(values):
                if not isinstance(item, dict):
                    raise DataRequirementsValidationError(
                        f"{section}[{index}] must be an object."
                    )

                name = item.get("name")
                classification_name = item.get("classification")

                if not isinstance(name, str) or not name:
                    raise DataRequirementsValidationError(
                        f"{section}[{index}] requires name."
                    )

                if classification_name not in ALLOWED_CLASSES:
                    raise DataRequirementsValidationError(
                        f"Unsupported classification: {classification_name}"
                    )

                if name in names:
                    raise DataRequirementsValidationError(
                        f"Duplicate name in {section}: {name}"
                    )

                names.add(name)
                total += 1

            names_by_section[section] = names

        test_names = names_by_section["test_data"]

        forbidden_overlap = (
            test_names & names_by_section["secrets"]
        ) | (
            test_names & names_by_section["runtime_correlated"]
        ) | (
            test_names & names_by_section["configuration"]
        )

        if forbidden_overlap:
            raise DataRequirementsValidationError(
                "TEST_DATA overlaps with non-CSV classifications: "
                + ", ".join(sorted(forbidden_overlap))
            )

        print("=" * 72)
        print("PERFORMANCE DATA CLASSIFICATION VALIDATION")
        print("=" * 72)
        print("Status : PASS")
        print(f"Schema : {schema_version}")
        print(f"Items  : {total}")
        print("=" * 72)
        return 0

    except DataRequirementsValidationError as exc:
        print("=" * 72)
        print("PERFORMANCE DATA CLASSIFICATION VALIDATION")
        print("=" * 72)
        print("Status : FAIL")
        print(f"Error  : {exc}")
        print("=" * 72)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
