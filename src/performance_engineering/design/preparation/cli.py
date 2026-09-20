#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = PROJECT_ROOT / "scripts"
PLANS = PROJECT_ROOT / "tests" / "plans"
GENERATED = PROJECT_ROOT / "tests" / "generated"
SLA = PROJECT_ROOT / "config" / "sla.json"


class CliDesignError(RuntimeError):
    pass


def run(
    command: list[str],
    stage: str,
) -> None:
    print()
    print("=" * 78)
    print(f"CLI DESIGN STAGE: {stage}")
    print("=" * 78)

    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        raise CliDesignError(
            f"Stage failed: {stage} "
            f"(exit code {completed.returncode})"
        )


def require_file(
    path: Path,
    description: str,
) -> Path:
    path = (
        path
        .expanduser()
        .resolve()
    )

    if not path.is_file():
        raise CliDesignError(
            f"{description} not found: {path}"
        )

    return path


def load_json(
    path: Path,
    description: str,
) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        raise CliDesignError(
            f"Unable to read {description}: {exc}"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise CliDesignError(
            f"{description} must contain a JSON object."
        )

    return payload


def safe_scenario_name(
    normalized: dict[str, Any],
) -> str:
    scenarios = normalized.get(
        "scenarios",
        [],
    )

    if (
        not isinstance(scenarios, list)
        or len(scenarios) != 1
        or not isinstance(
            scenarios[0],
            dict,
        )
    ):
        raise CliDesignError(
            "Normalized model must contain exactly one scenario."
        )

    value = str(
        scenarios[0].get(
            "name",
            "",
        )
    ).strip()

    if not value:
        raise CliDesignError(
            "Normalized scenario has no name."
        )

    allowed = set(
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789-_."
    )

    normalized_name = "".join(
        char
        if char in allowed
        else "-"
        for char in value
    ).strip("-._")

    if not normalized_name:
        raise CliDesignError(
            "Scenario name becomes empty after normalization."
        )

    return normalized_name


def ensure_profile_matches_workspace(
    profile: Path,
    workspace: Path,
) -> None:
    expected = (
        workspace
        / "execution-profile.yaml"
    ).resolve()

    if profile.resolve() != expected:
        raise CliDesignError(
            "CLI governed design requires the materialized "
            "workspace execution profile. "
            f"Expected: {expected}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a complete governed performance design "
            "from CLI/API input without executing load."
        )
    )

    parser.add_argument(
        "--input",
    )

    parser.add_argument(
        "--target",
    )

    parser.add_argument(
        "--method",
    )

    parser.add_argument(
        "--workspace",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--profile",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    workspace = (
        args.workspace
        .expanduser()
        .resolve()
    )

    profile = require_file(
        args.profile,
        "Execution profile",
    )

    workspace.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        ensure_profile_matches_workspace(
            profile,
            workspace,
        )

        intake_command = [
            sys.executable,
            str(
                SCRIPTS
                / "performance_intake.py"
            ),
            "--input-type",
            "cli",
            "--workspace",
            str(workspace),
        ]

        if args.input:
            input_path = require_file(
                Path(args.input),
                "CLI input",
            )

            intake_command.extend(
                [
                    "--input",
                    str(input_path),
                ]
            )

        elif args.target:
            intake_command.extend(
                [
                    "--target",
                    args.target,
                ]
            )

            if args.method:
                intake_command.extend(
                    [
                        "--method",
                        args.method,
                    ]
                )

        else:
            raise CliDesignError(
                "CLI design requires either --input "
                "or --target."
            )

        run(
            intake_command,
            "INTAKE",
        )

        normalized = require_file(
            workspace
            / "normalized-performance-model.json",
            "Normalized performance model",
        )

        manifest = require_file(
            workspace
            / "intake-manifest.json",
            "Intake manifest",
        )

        normalized_payload = load_json(
            normalized,
            "Normalized performance model",
        )

        manifest_payload = load_json(
            manifest,
            "Intake manifest",
        )

        if (
            str(
                manifest_payload.get(
                    "status",
                    "",
                )
            ).upper()
            != "INTAKE_READY"
        ):
            raise CliDesignError(
                "Intake manifest is not INTAKE_READY."
            )

        scenario = safe_scenario_name(
            normalized_payload
        )

        plan_directory = (
            PLANS
            / scenario
        )

        plan_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        plan = (
            plan_directory
            / "test-plan.yaml"
        )

        requirements = (
            plan_directory
            / "data-requirements.json"
        )

        executable = (
            workspace
            / "executable-model.json"
        )

        jmx = (
            GENERATED
            / f"{scenario}.jmx"
        )

        GENERATED.mkdir(
            parents=True,
            exist_ok=True,
        )

        run(
            [
                sys.executable,
                str(
                    SCRIPTS
                    / "compile_normalized_test_plan.py"
                ),
                "--input",
                str(normalized),
                "--profile",
                str(profile),
                "--sla",
                str(SLA),
                "--output",
                str(plan),
                "--data-requirements",
                str(requirements),
            ],
            "COMPILE_GOVERNED_PLAN",
        )

        run(
            [
                sys.executable,
                str(
                    SCRIPTS
                    / "sync_cli_governance.py"
                ),
                "--normalized",
                str(normalized),
                "--plan",
                str(plan),
                "--data-requirements",
                str(requirements),
            ],
            "SYNC_GOVERNANCE",
        )

        run(
            [
                sys.executable,
                str(
                    SCRIPTS
                    / "validate_test_plan.py"
                ),
                "--plan",
                str(plan),
            ],
            "VALIDATE_PLAN",
        )

        run(
            [
                sys.executable,
                str(
                    SCRIPTS
                    / "review_test_plan.py"
                ),
                "--plan",
                str(plan),
                "--strict",
            ],
            "REVIEW_PLAN",
        )

        run(
            [
                sys.executable,
                str(
                    SCRIPTS
                    / "compile_normalized_executable_model.py"
                ),
                "--input",
                str(normalized),
                "--output",
                str(executable),
            ],
            "COMPILE_EXECUTABLE_MODEL",
        )

        run(
            [
                sys.executable,
                str(
                    SCRIPTS
                    / "generate_postman_jmx.py"
                ),
                "--model",
                str(executable),
                "--profile",
                str(profile),
                "--output",
                str(jmx),
            ],
            "GENERATE_JMX",
        )

        require_file(
            plan,
            "Generated test plan",
        )

        require_file(
            plan.with_suffix(
                ".md"
            ),
            "Generated Markdown plan",
        )

        require_file(
            requirements,
            "Generated data requirements",
        )

        require_file(
            executable,
            "Generated executable model",
        )

        require_file(
            jmx,
            "Generated JMX",
        )

        design_manifest = {
            "schema_version": "1.0",
            "scenario": scenario,
            "source_type": "CLI",
            "status": "READY_FOR_HUMAN_REVIEW",
            "artifacts": {
                "workspace": str(
                    workspace
                ),
                "execution_profile": str(
                    profile
                ),
                "normalized_model": str(
                    normalized
                ),
                "intake_manifest": str(
                    manifest
                ),
                "test_plan": str(
                    plan
                ),
                "test_plan_markdown": str(
                    plan.with_suffix(
                        ".md"
                    )
                ),
                "data_requirements": str(
                    requirements
                ),
                "executable_model": str(
                    executable
                ),
                "jmx": str(
                    jmx
                ),
            },
            "governance": {
                "plan_status": "DRAFT",
                "workload_status": "PROPOSED",
                "authorization_status": "PENDING",
                "load_executed": False,
            },
        }

        design_manifest_path = (
            workspace
            / "design-manifest.json"
        )

        temporary = (
            design_manifest_path
            .with_suffix(
                ".json.tmp"
            )
        )

        temporary.write_text(
            json.dumps(
                design_manifest,
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

        temporary.replace(
            design_manifest_path
        )

    except (
        CliDesignError,
        OSError,
    ) as exc:
        print(
            f"CLI DESIGN ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print()
    print("=" * 78)
    print("GOVERNED CLI PERFORMANCE DESIGN")
    print("=" * 78)
    print(
        f"Scenario           : {scenario}"
    )
    print(
        f"Workspace          : {workspace}"
    )
    print(
        f"Execution profile  : {profile}"
    )
    print(
        f"Normalized model   : {normalized}"
    )
    print(
        f"Executable model   : {executable}"
    )
    print(
        f"Test plan          : {plan}"
    )
    print(
        f"Data requirements  : {requirements}"
    )
    print(
        f"JMX                : {jmx}"
    )
    print(
        f"Design manifest    : {design_manifest_path}"
    )
    print("-" * 78)
    print("Plan status        : DRAFT")
    print("Workload status    : PROPOSED")
    print("Authorization      : PENDING")
    print("JMeter executed    : NO")
    print("=" * 78)
    print("READY FOR HUMAN REVIEW")
    print("=" * 78)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
