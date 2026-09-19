#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


class CsvTemplateError(RuntimeError):
    pass


def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CsvTemplateError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CsvTemplateError(
            f"Invalid JSON: line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(data, dict):
        raise CsvTemplateError("Root must be a JSON object.")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate CSV template from classified performance test data."
        )
    )
    parser.add_argument("--classification", required=True)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--requirements", required=True)
    parser.add_argument(
        "--rows",
        type=int,
        default=1,
        help="Number of example/template rows. Default: 1.",
    )
    args = parser.parse_args()

    classification_path = (
        Path(args.classification).expanduser().resolve()
    )
    csv_path = Path(args.csv).expanduser().resolve()
    requirements_path = (
        Path(args.requirements).expanduser().resolve()
    )

    try:
        if args.rows < 1:
            raise CsvTemplateError("--rows must be >= 1.")

        data = load(classification_path)

        sections = data.get("classification", {})
        if not isinstance(sections, dict):
            raise CsvTemplateError(
                "classification section is missing."
            )

        test_data = sections.get("test_data", [])
        if not isinstance(test_data, list):
            raise CsvTemplateError(
                "classification.test_data must be a list."
            )

        columns: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in test_data:
            if not isinstance(item, dict):
                continue
            if not item.get("parameterizable", False):
                continue

            name = str(item.get("name", "")).strip()
            if not name or name in seen:
                continue
            seen.add(name)

            columns.append(
                {
                    "name": name,
                    "type": item.get("type", "STRING"),
                    "required": True,
                    "source": item.get("source"),
                    "request_id": item.get("request_id"),
                    "location": item.get("location"),
                    "example_value": item.get("example_value"),
                }
            )

        if not columns:
            raise CsvTemplateError(
                "No parameterizable TEST_DATA_CANDIDATE fields were found."
            )

        csv_path.parent.mkdir(parents=True, exist_ok=True)

        with csv_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[item["name"] for item in columns],
            )
            writer.writeheader()

            for _ in range(args.rows):
                writer.writerow(
                    {
                        item["name"]: (
                            ""
                            if item.get("example_value") is None
                            else item.get("example_value")
                        )
                        for item in columns
                    }
                )

        requirements = {
            "schema_version": "1.0",
            "data_strategy": "CSV",
            "csv": {
                "file": str(csv_path),
                "delimiter": ",",
                "encoding": "utf-8",
                "recycle": None,
                "stop_thread_on_eof": None,
                "sharing_mode": None,
            },
            "parameters": [
                {
                    key: value
                    for key, value in item.items()
                    if key != "example_value"
                }
                for item in columns
            ],
            "governance": {
                "recycle_policy": "REQUIRES_EXECUTION_PROFILE",
                "row_capacity_validation": "REQUIRED_BEFORE_EXECUTION",
                "secrets_in_csv": False,
                "runtime_correlations_in_csv": False,
                "configuration_in_csv": False,
            },
        }

        requirements_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        requirements_path.write_text(
            json.dumps(
                requirements,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    except CsvTemplateError as exc:
        print(
            f"CSV TEMPLATE ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print("=" * 72)
    print("PERFORMANCE CSV TEMPLATE GENERATION")
    print("=" * 72)
    print(f"Columns      : {len(columns)}")
    print(f"Example rows : {args.rows}")
    print(f"CSV          : {csv_path}")
    print(f"Requirements : {requirements_path}")
    print("=" * 72)
    print("CSV TEMPLATE READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
