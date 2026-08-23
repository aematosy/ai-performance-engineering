#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

from validate_jmx_artifact import ArtifactValidationError
from validate_test_plan import PlanValidationError, load_plan, validate_plan


def target_string(plan: dict[str, Any]) -> str:
    tx = plan["transactions"][0]
    target = plan["target"]
    port = int(target["port"])
    protocol = str(target["protocol"])
    default_port = 443 if protocol == "https" else 80
    port_part = "" if port == default_port else f":{port}"
    return f"{str(tx['method']).upper()} {protocol}://{target['host']}{port_part}{tx['path']}"


def validate_artifact(project_root: Path, plan_path: Path, jmx_path: Path) -> None:
    command = [
        sys.executable,
        str(project_root / "scripts" / "validate_jmx_artifact.py"),
        "--plan",
        str(plan_path),
        "--jmx",
        str(jmx_path),
    ]
    result = subprocess.run(command, cwd=project_root)
    if result.returncode != 0:
        raise ArtifactValidationError("JMX artifact validation failed.")


def print_preflight(plan: dict[str, Any], plan_path: Path, jmx_path: Path) -> None:
    workload = plan["workload"]["parameters"]
    print("=" * 70)
    print("CONTROLLED PERFORMANCE EXECUTION PREFLIGHT")
    print("=" * 70)
    print(f"Scenario      : {plan['metadata']['name']}")
    print(f"Target        : {target_string(plan)}")
    print(f"Environment   : {plan['environment']}")
    print(f"Users         : {workload['threads']}")
    print(f"Ramp-up       : {workload['ramp_time_seconds']} s")
    print(f"Duration      : {workload['duration_seconds']} s")
    print(f"Pacing        : {workload.get('pacing_seconds', 0)} s")
    print(f"Plan          : {plan_path}")
    print(f"JMX           : {jmx_path}")
    print(f"Plan status   : {plan['status']}")
    print(f"Workload      : {plan['workload']['status']}")
    print(f"Authorization : {plan['authorization']['status']}")
    print("JMX artifact  : VALID")
    print("=" * 70)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run an approved Performance Test Plan using only the workload and "
            "target stored in the plan. No CLI workload overrides are accepted."
        )
    )
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--jmx", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--authorized", action="store_true")
    args = parser.parse_args()

    try:
        plan_path = args.plan.expanduser().resolve()
        jmx_path = args.jmx.expanduser().resolve()
        project_root = Path(__file__).resolve().parents[1]
        plan = load_plan(plan_path)
        validate_plan(plan, plan_path)

        if str(plan["status"]).upper() != "APPROVED":
            raise PlanValidationError("Plan must be APPROVED.")
        if str(plan["workload"]["status"]).upper() != "APPROVED":
            raise PlanValidationError("Workload must be APPROVED.")

        validate_artifact(project_root, plan_path, jmx_path)
        print_preflight(plan, plan_path, jmx_path)

        if args.preflight:
            print("EXECUTION NOT STARTED - EXPLICIT AUTHORIZATION REQUIRED")
            return 0

        workload = plan["workload"]["parameters"]
        command = [
            sys.executable,
            str(project_root / "scripts" / "run_test.py"),
            "--jmx",
            str(jmx_path),
            "--scenario",
            str(plan["metadata"]["name"]),
            "--target",
            target_string(plan),
            "--environment",
            str(plan["environment"]),
            "--threads",
            str(int(workload["threads"])),
            "--ramp-time",
            str(int(workload["ramp_time_seconds"])),
            "--duration",
            str(int(workload["duration_seconds"])),
            "--authorized",
        ]
        print("Executing approved plan with immutable plan parameters...")
        return subprocess.run(command, cwd=project_root).returncode

    except (PlanValidationError, ArtifactValidationError, KeyError, TypeError, ValueError, OSError) as exc:
        print(f"CONTROLLED EXECUTION ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
