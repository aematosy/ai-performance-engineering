#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


class ScenarioCsvError(RuntimeError):
    pass


def load_json(
    path: Path,
) -> dict[str, Any]:
    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8",
            )
        )
    except FileNotFoundError as exc:
        raise ScenarioCsvError(
            f"File not found: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ScenarioCsvError(
            f"Invalid JSON in {path}: "
            f"line {exc.lineno}, "
            f"column {exc.colno}"
        ) from exc

    if not isinstance(
        data,
        dict,
    ):
        raise ScenarioCsvError(
            "JSON root must be an object."
        )

    return data


def normalize_csv_value(
    value: Any,
) -> str:
    if value is None:
        return ""

    if isinstance(
        value,
        bool,
    ):
        return (
            "true"
            if value
            else "false"
        )

    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate scenario-scoped CSV "
            "and data requirements."
        )
    )
    parser.add_argument(
        "--scenario-data",
        required=True,
    )
    parser.add_argument(
        "--csv",
        required=True,
    )
    parser.add_argument(
        "--requirements",
        required=True,
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=1,
    )

    args = parser.parse_args()

    scenario_data_path = (
        Path(
            args.scenario_data
        )
        .expanduser()
        .resolve()
    )
    csv_path = (
        Path(args.csv)
        .expanduser()
        .resolve()
    )
    requirements_path = (
        Path(
            args.requirements
        )
        .expanduser()
        .resolve()
    )

    try:
        if args.rows < 1:
            raise ScenarioCsvError(
                "--rows must be >= 1."
            )

        data = load_json(
            scenario_data_path
        )

        test_data = data.get(
            "test_data",
            [],
        )
        if not isinstance(
            test_data,
            list,
        ):
            raise ScenarioCsvError(
                "test_data must be a list."
            )

        columns: list[
            dict[str, Any]
        ] = []

        for item in test_data:
            if not isinstance(
                item,
                dict,
            ):
                continue

            if not item.get(
                "parameterizable",
                False,
            ):
                continue

            column = str(
                item.get(
                    "scenario_column_name",
                    "",
                )
            ).strip()

            if not column:
                raise ScenarioCsvError(
                    "Every parameterizable item "
                    "requires scenario_column_name."
                )

            columns.append(
                {
                    "name": column,
                    "type": item.get(
                        "type",
                        "STRING",
                    ),
                    "required": True,
                    "source": item.get(
                        "source"
                    ),
                    "request_id": item.get(
                        "request_id"
                    ),
                    "location": item.get(
                        "location"
                    ),
                    "example_value": item.get(
                        "example_value"
                    ),
                }
            )

        if not columns:
            raise ScenarioCsvError(
                "No scenario-scoped "
                "parameterizable test data "
                "was found."
            )

        csv_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with csv_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as fh:
            writer = (
                csv.DictWriter(
                    fh,
                    fieldnames=[
                        item["name"]
                        for item
                        in columns
                    ],
                )
            )

            writer.writeheader()

            for _ in range(
                args.rows
            ):
                writer.writerow(
                    {
                        item["name"]:
                        normalize_csv_value(
                            item.get(
                                "example_value"
                            )
                        )
                        for item
                        in columns
                    }
                )

        candidate = data.get(
            "scenario_candidate",
            {},
        )
        if not isinstance(
            candidate,
            dict,
        ):
            candidate = {}

        requirements = {
            "schema_version": "1.1",
            "scenario_candidate": {
                "id": candidate.get(
                    "id"
                ),
                "type": candidate.get(
                    "type"
                ),
            },
            "data_strategy": "CSV",
            "csv": {
                "file": str(
                    csv_path
                ),
                "delimiter": ",",
                "encoding": "utf-8",
                "recycle": None,
                "stop_thread_on_eof": None,
                "sharing_mode": None,
            },
            "parameters": [
                {
                    key: value
                    for key, value
                    in item.items()
                    if key
                    != "example_value"
                }
                for item in columns
            ],
            "governance": {
                "recycle_policy": (
                    "REQUIRES_EXECUTION_PROFILE"
                ),
                "row_capacity_validation": (
                    "REQUIRED_BEFORE_EXECUTION"
                ),
                "secrets_in_csv": False,
                "runtime_correlations_in_csv": False,
                "configuration_in_csv": False,
                "scenario_scoped": True,
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

    except ScenarioCsvError as exc:
        print(
            "SCENARIO CSV ERROR: "
            f"{exc}",
            file=sys.stderr,
        )
        return 2

    print("=" * 72)
    print(
        "SCENARIO CSV TEMPLATE GENERATION"
    )
    print("=" * 72)
    print(
        "Candidate    :",
        requirements[
            "scenario_candidate"
        ]["id"],
    )
    print(
        "Columns      :",
        len(columns),
    )
    print(
        "Example rows :",
        args.rows,
    )
    print(
        "CSV          :",
        csv_path,
    )
    print(
        "Requirements :",
        requirements_path,
    )
    print("=" * 72)
    print(
        "SCENARIO CSV TEMPLATE READY"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
