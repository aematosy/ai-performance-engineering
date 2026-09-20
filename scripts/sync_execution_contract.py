#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


class ContractSyncError(RuntimeError):
    pass


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(data, dict):
        raise ContractSyncError(
            f"Invalid YAML object: {path}"
        )

    return data


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(data, dict):
        raise ContractSyncError(
            f"Invalid JSON object: {path}"
        )

    return data


def plan_contract(
    plan: dict[str, Any],
) -> list[dict[str, Any]]:
    transactions = plan.get(
        "transactions",
        [],
    )

    result = []

    for transaction in transactions:
        expected = transaction.get(
            "expected_status"
        )

        if expected in (
            None,
            "",
            "UNRESOLVED",
        ):
            raise ContractSyncError(
                "Execution contract is unresolved for "
                f"{transaction.get('method')} "
                f"{transaction.get('path')}"
            )

        result.append(
            {
                "method": str(
                    transaction.get(
                        "method",
                        ""
                    )
                ).upper(),
                "path": str(
                    transaction.get(
                        "path",
                        ""
                    )
                ),
                "expected_status": int(
                    expected
                ),
            }
        )

    if not result:
        raise ContractSyncError(
            "Plan contains no transactions."
        )

    return result


def apply_to_normalized_model(
    model: dict[str, Any],
    contract: list[dict[str, Any]],
) -> bool:
    changed = False

    by_key = {
        (
            item["method"],
            item["path"],
        ): item["expected_status"]
        for item in contract
    }

    for scenario in model.get(
        "scenarios",
        [],
    ):
        for transaction in scenario.get(
            "transactions",
            [],
        ):
            method = str(
                transaction.get(
                    "method",
                    ""
                )
            ).upper()

            target = str(
                transaction.get(
                    "target",
                    transaction.get(
                        "path",
                        "",
                    ),
                )
            )

            path = target

            if "://" in target:
                from urllib.parse import urlparse

                parsed = urlparse(
                    target
                )

                path = parsed.path or "/"

            key = (
                method,
                path,
            )

            if key not in by_key:
                continue

            expected = by_key[key]

            if (
                transaction.get(
                    "expected_status"
                )
                != expected
            ):
                transaction[
                    "expected_status"
                ] = expected

                changed = True

    return changed


def apply_to_executable_model(
    model: dict[str, Any],
    contract: list[dict[str, Any]],
) -> bool:
    changed = False

    by_key = {
        (
            item["method"],
            item["path"],
        ): item["expected_status"]
        for item in contract
    }

    requests = model.get(
        "requests",
        [],
    )

    for request in requests:
        key = (
            str(
                request.get(
                    "method",
                    ""
                )
            ).upper(),
            str(
                request.get(
                    "path",
                    ""
                )
            ),
        )

        if key not in by_key:
            continue

        expected = by_key[key]

        if (
            request.get(
                "expected_status"
            )
            != expected
        ):
            request[
                "expected_status"
            ] = expected

            changed = True

    return changed


def write_json(
    path: Path,
    data: dict[str, Any],
) -> None:
    path.write_text(
        json.dumps(
            data,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--plan",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--workspace",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    plan_path = (
        args.plan
        .expanduser()
        .resolve()
    )

    workspace = (
        args.workspace
        .expanduser()
        .resolve()
    )

    plan = load_yaml(
        plan_path
    )

    contract = plan_contract(
        plan
    )

    normalized = (
        workspace
        / "normalized-performance-model.json"
    )

    executable = (
        workspace
        / "executable-model.json"
    )

    touched = []

    if normalized.is_file():
        model = load_json(
            normalized
        )

        if apply_to_normalized_model(
            model,
            contract,
        ):
            write_json(
                normalized,
                model,
            )

            touched.append(
                normalized
            )

    if executable.is_file():
        model = load_json(
            executable
        )

        if apply_to_executable_model(
            model,
            contract,
        ):
            write_json(
                executable,
                model,
            )

            touched.append(
                executable
            )

    print("=" * 70)
    print("EXECUTION CONTRACT SYNCHRONIZATION")
    print("=" * 70)

    for item in contract:
        print(
            f"{item['method']} "
            f"{item['path']} "
            f"-> HTTP "
            f"{item['expected_status']}"
        )

    if touched:
        print()
        print("Updated:")

        for path in touched:
            print(
                f"- {path}"
            )

    else:
        print()
        print(
            "Execution models already synchronized."
        )

    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
