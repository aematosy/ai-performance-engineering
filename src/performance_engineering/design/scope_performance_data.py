#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class ScenarioDataScopeError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ScenarioDataScopeError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ScenarioDataScopeError(
            f"Invalid JSON in {path}: line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(data, dict):
        raise ScenarioDataScopeError("JSON root must be an object.")
    return data


def selected_request_ids_from_context(
    context: dict[str, Any],
) -> list[str]:
    requests = context.get("requests", [])
    if not isinstance(requests, list):
        raise ScenarioDataScopeError(
            "design-context.requests must be a list."
        )

    result: list[str] = []

    for item in requests:
        if not isinstance(item, dict):
            continue

        request_id = item.get("id")
        if isinstance(request_id, str) and request_id:
            result.append(request_id)

    if not result:
        raise ScenarioDataScopeError(
            "No selected request ids were found in design context."
        )

    return result


def compact_column_name(
    item: dict[str, Any],
    duplicate_leaf_names: set[str],
) -> str:
    original = str(
        item.get("original_name")
        or item.get("name")
        or ""
    ).strip()

    if (
        original
        and original.lower()
        not in duplicate_leaf_names
    ):
        return original.lower()

    return str(item.get("name", "")).strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scope classified performance data to one selected "
            "scenario/design context."
        )
    )
    parser.add_argument(
        "--classification",
        required=True,
    )
    parser.add_argument(
        "--design-context",
        required=True,
    )
    parser.add_argument(
        "--output",
        required=True,
    )

    args = parser.parse_args()

    classification_path = (
        Path(args.classification)
        .expanduser()
        .resolve()
    )
    context_path = (
        Path(args.design_context)
        .expanduser()
        .resolve()
    )
    output_path = (
        Path(args.output)
        .expanduser()
        .resolve()
    )

    try:
        classification = load_json(
            classification_path
        )
        context = load_json(
            context_path
        )

        selected_request_ids = (
            selected_request_ids_from_context(
                context
            )
        )
        selected_set = set(
            selected_request_ids
        )

        sections = classification.get(
            "classification"
        )
        if not isinstance(
            sections,
            dict,
        ):
            raise ScenarioDataScopeError(
                "classification.classification "
                "must be an object."
            )

        all_test_data = sections.get(
            "test_data",
            [],
        )
        if not isinstance(
            all_test_data,
            list,
        ):
            raise ScenarioDataScopeError(
                "classification.test_data "
                "must be a list."
            )

        selected: list[
            dict[str, Any]
        ] = []

        for item in all_test_data:
            if not isinstance(
                item,
                dict,
            ):
                continue

            request_id = item.get(
                "request_id"
            )

            # Collection/environment-level test data has no request_id.
            # Include it only when it is explicitly a TEST_DATA_CANDIDATE.
            if request_id is None:
                selected.append(
                    dict(item)
                )
                continue

            if (
                isinstance(
                    request_id,
                    str,
                )
                and request_id
                in selected_set
            ):
                selected.append(
                    dict(item)
                )

        original_names = [
            str(
                item.get(
                    "original_name",
                    ""
                )
            ).strip().lower()
            for item in selected
            if str(
                item.get(
                    "original_name",
                    ""
                )
            ).strip()
        ]

        duplicate_leaf_names = {
            name
            for name in original_names
            if original_names.count(
                name
            ) > 1
        }

        used_columns: set[str] = set()

        for item in selected:
            compact = compact_column_name(
                item,
                duplicate_leaf_names,
            )

            if not compact:
                raise ScenarioDataScopeError(
                    "Unable to derive column name "
                    f"for item: {item}"
                )

            final_name = compact
            suffix = 2

            while final_name in used_columns:
                final_name = (
                    f"{compact}_{suffix}"
                )
                suffix += 1

            used_columns.add(
                final_name
            )

            item[
                "scenario_column_name"
            ] = final_name

        candidate = context.get(
            "scenario_candidate",
            {},
        )
        if not isinstance(
            candidate,
            dict,
        ):
            candidate = {}

        result = {
            "schema_version": "1.0",
            "scenario_candidate": {
                "id": candidate.get(
                    "id"
                ),
                "type": candidate.get(
                    "type"
                ),
            },
            "selected_requests": (
                selected_request_ids
            ),
            "test_data": selected,
            "configuration": (
                sections.get(
                    "configuration",
                    [],
                )
            ),
            "runtime_correlated": (
                sections.get(
                    "runtime_correlated",
                    [],
                )
            ),
            "secrets": (
                sections.get(
                    "secrets",
                    [],
                )
            ),
            "summary": {
                "selected_request_count": (
                    len(
                        selected_request_ids
                    )
                ),
                "test_data_count": (
                    len(selected)
                ),
                "csv_column_count": (
                    len(selected)
                ),
            },
        }

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        output_path.write_text(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    except ScenarioDataScopeError as exc:
        print(
            f"SCENARIO DATA SCOPE ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print("=" * 72)
    print(
        "SCENARIO-SCOPED PERFORMANCE DATA"
    )
    print("=" * 72)
    print(
        "Candidate :",
        result[
            "scenario_candidate"
        ]["id"],
    )
    print(
        "Requests  :",
        result["summary"][
            "selected_request_count"
        ],
    )
    print(
        "Test data :",
        result["summary"][
            "test_data_count"
        ],
    )
    print(
        "CSV cols  :",
        result["summary"][
            "csv_column_count"
        ],
    )
    print(
        "Output    :",
        output_path,
    )
    print("=" * 72)
    print(
        "SCENARIO DATA SCOPE READY"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
