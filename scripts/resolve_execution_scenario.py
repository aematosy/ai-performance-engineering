#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def direct_plan(
    scenario: str,
) -> Path:
    return (
        ROOT
        / "tests"
        / "plans"
        / scenario
        / "test-plan.yaml"
    )


def design_manifest(
    scenario: str,
) -> Path:
    return (
        ROOT
        / "workspaces"
        / scenario
        / "design-manifest.json"
    )


def resolve(
    requested_scenario: str,
) -> str:
    requested_scenario = requested_scenario.strip()

    if not requested_scenario:
        raise RuntimeError(
            "scenario is empty"
        )

    # Backward-compatible path.
    #
    # Existing cURL/API scenarios such as DummyJSON already have:
    #
    # tests/plans/<scenario>/test-plan.yaml
    #
    # They must continue working exactly as before.
    if direct_plan(
        requested_scenario
    ).is_file():
        return requested_scenario

    # Postman may discover a canonical scenario different from the
    # external request/workspace id.
    manifest = design_manifest(
        requested_scenario
    )

    if not manifest.is_file():
        raise RuntimeError(
            "No execution plan or design manifest exists for "
            f"scenario '{requested_scenario}'."
        )

    payload = json.loads(
        manifest.read_text(
            encoding="utf-8"
        )
    )

    status = str(
        payload.get(
            "status",
            ""
        )
    ).strip()

    if status != "DESIGN_ARTIFACTS_READY":
        raise RuntimeError(
            f"Design manifest is not ready: {status!r}"
        )

    canonical = str(
        payload.get(
            "scenario",
            ""
        )
    ).strip()

    if not canonical:
        raise RuntimeError(
            "Design manifest does not define canonical scenario."
        )

    canonical_plan = direct_plan(
        canonical
    )

    if not canonical_plan.is_file():
        raise RuntimeError(
            "Canonical plan does not exist: "
            f"{canonical_plan}"
        )

    return canonical


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--scenario",
        required=True,
    )

    args = parser.parse_args()

    print(
        resolve(
            args.scenario
        )
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            main()
        )
    except Exception as exc:
        print(
            f"SCENARIO RESOLUTION ERROR: {exc}",
            file=__import__("sys").stderr,
        )
        raise SystemExit(2)
