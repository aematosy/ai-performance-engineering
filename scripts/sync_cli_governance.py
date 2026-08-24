#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


class GovernanceSyncError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8")
        )
    except FileNotFoundError as exc:
        raise GovernanceSyncError(
            f"JSON file not found: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise GovernanceSyncError(
            f"Invalid JSON: {path}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise GovernanceSyncError(
            f"JSON root must be an object: {path}"
        )

    return payload


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(
            path.read_text(encoding="utf-8")
        )
    except FileNotFoundError as exc:
        raise GovernanceSyncError(
            f"YAML file not found: {path}"
        ) from exc
    except yaml.YAMLError as exc:
        raise GovernanceSyncError(
            f"Invalid YAML: {path}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise GovernanceSyncError(
            f"YAML root must be a mapping: {path}"
        )

    return payload


def atomic_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    temporary.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    json.loads(
        temporary.read_text(
            encoding="utf-8"
        )
    )

    temporary.replace(path)


def atomic_yaml(
    path: Path,
    payload: dict[str, Any],
) -> None:
    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    temporary.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            width=1000,
        ),
        encoding="utf-8",
    )

    yaml.safe_load(
        temporary.read_text(
            encoding="utf-8"
        )
    )

    temporary.replace(path)


def scenario_identity(
    normalized: dict[str, Any],
) -> tuple[str, str]:
    source = normalized.get("source")

    if not isinstance(source, dict):
        raise GovernanceSyncError(
            "Normalized model source is missing."
        )

    source_type = str(
        source.get("type", "")
    ).strip().upper()

    if source_type != "CLI":
        raise GovernanceSyncError(
            "sync_cli_governance.py only accepts "
            "normalized CLI models."
        )

    scenarios = normalized.get("scenarios")

    if (
        not isinstance(scenarios, list)
        or len(scenarios) != 1
        or not isinstance(scenarios[0], dict)
    ):
        raise GovernanceSyncError(
            "Normalized CLI model must contain "
            "exactly one scenario."
        )

    scenario = str(
        scenarios[0].get("name", "")
    ).strip()

    if not scenario:
        raise GovernanceSyncError(
            "Normalized scenario name is missing."
        )

    transactions = scenarios[0].get(
        "transactions"
    )

    if (
        not isinstance(transactions, list)
        or not transactions
    ):
        raise GovernanceSyncError(
            "Normalized scenario has no transactions."
        )

    candidate_type = (
        "SINGLE_REQUEST"
        if len(transactions) == 1
        else "MULTI_REQUEST"
    )

    return scenario, candidate_type


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize CLI governance identity "
            "across normalized model, plan and "
            "data requirements."
        )
    )

    parser.add_argument(
        "--normalized",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--plan",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--data-requirements",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    normalized_path = (
        args.normalized.expanduser().resolve()
    )
    plan_path = (
        args.plan.expanduser().resolve()
    )
    requirements_path = (
        args.data_requirements
        .expanduser()
        .resolve()
    )

    try:
        normalized = load_json(
            normalized_path
        )
        plan = load_yaml(
            plan_path
        )
        requirements = load_json(
            requirements_path
        )

        scenario, candidate_type = (
            scenario_identity(
                normalized
            )
        )

        metadata = plan.get("metadata")

        if not isinstance(metadata, dict):
            raise GovernanceSyncError(
                "Plan metadata is missing."
            )

        plan_scenario = str(
            metadata.get("name", "")
        ).strip()

        if plan_scenario != scenario:
            raise GovernanceSyncError(
                "Plan/normalized scenario mismatch: "
                f"{plan_scenario} != {scenario}"
            )

        source = normalized["source"]

        artifact = source.get("artifact")

        source_binding = {
            "candidate_id": scenario,
            "source_type": "CLI",
        }

        if artifact:
            source_binding[
                "artifact"
            ] = str(artifact)

        # Root-level binding is already supported by
        # validate_execution_bundle.py.
        plan["source_binding"] = (
            source_binding
        )

        requirements["scenario"] = scenario
        requirements[
            "scenario_candidate"
        ] = {
            "id": scenario,
            "type": candidate_type,
        }

        atomic_yaml(
            plan_path,
            plan,
        )

        atomic_json(
            requirements_path,
            requirements,
        )

    except (
        GovernanceSyncError,
        OSError,
    ) as exc:
        print(
            f"CLI GOVERNANCE SYNC ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print("=" * 72)
    print("CLI GOVERNANCE SYNCHRONIZATION")
    print("=" * 72)
    print(f"Scenario       : {scenario}")
    print(f"Candidate type : {candidate_type}")
    print("source_binding : SYNCHRONIZED")
    print("data contract  : SYNCHRONIZED")
    print("Postman        : NOT MODIFIED")
    print("JMX            : NOT MODIFIED")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
