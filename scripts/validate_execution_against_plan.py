#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


class ExecutionPlanValidationError(RuntimeError):
    pass


THREAD_KEYS = (
    "threads",
    "users",
    "virtual_users",
    "concurrent_users",
)

RAMP_KEYS = (
    "ramp_time_seconds",
    "ramp_up_seconds",
    "ramp_seconds",
)

DURATION_KEYS = (
    "duration_seconds",
    "duration",
)

ITERATION_KEYS = (
    "iterations",
    "loop_count",
)

PACING_KEYS = (
    "pacing_seconds",
    "pacing",
    "think_time_seconds",
)


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(
            path.read_text(encoding="utf-8")
        )
    except FileNotFoundError as exc:
        raise ExecutionPlanValidationError(
            f"File not found: {path}"
        ) from exc
    except yaml.YAMLError as exc:
        raise ExecutionPlanValidationError(
            f"Invalid YAML in {path}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ExecutionPlanValidationError(
            f"YAML root must be an object: {path}"
        )

    return data


def first_value(
    obj: dict[str, Any],
    keys: tuple[str, ...],
) -> tuple[str | None, Any]:
    for key in keys:
        if key in obj:
            return key, obj[key]
    return None, None


def normalize_status(value: Any) -> str:
    return str(value or "").strip().upper()


def resolve_plan_status(plan: dict[str, Any]) -> str:
    for path in (
        ("status",),
        ("plan", "status"),
        ("metadata", "status"),
    ):
        current: Any = plan
        valid = True
        for key in path:
            if not isinstance(current, dict) or key not in current:
                valid = False
                break
            current = current[key]
        if valid:
            return normalize_status(current)

    return ""


def resolve_workload_section(
    plan: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    workload = plan.get("workload")

    if not isinstance(workload, dict):
        raise ExecutionPlanValidationError(
            "Plan does not contain a workload object."
        )

    parameters = workload.get("parameters")

    if isinstance(parameters, dict):
        return parameters, normalize_status(
            workload.get("status")
        )

    return workload, normalize_status(
        workload.get("status")
    )


def resolve_authorization_status(
    plan: dict[str, Any],
) -> str:
    authorization = plan.get("authorization")

    if isinstance(authorization, str):
        return normalize_status(authorization)

    if isinstance(authorization, dict):
        for key in (
            "status",
            "execution_status",
            "state",
        ):
            if key in authorization:
                return normalize_status(
                    authorization[key]
                )

    return ""


def require_positive_int(
    value: Any,
    label: str,
    *,
    minimum: int = 1,
) -> int:
    if not isinstance(value, int):
        raise ExecutionPlanValidationError(
            f"{label} must be an integer."
        )

    if value < minimum:
        raise ExecutionPlanValidationError(
            f"{label} must be >= {minimum}."
        )

    return value


def require_nonnegative_int(
    value: Any,
    label: str,
) -> int:
    return require_positive_int(
        value,
        label,
        minimum=0,
    )


def require_nonnegative_number(
    value: Any,
    label: str,
) -> float:
    if not isinstance(value, (int, float)):
        raise ExecutionPlanValidationError(
            f"{label} must be numeric."
        )

    value = float(value)

    if value < 0:
        raise ExecutionPlanValidationError(
            f"{label} must be >= 0."
        )

    return value


def normalize_profile(
    profile: dict[str, Any],
) -> dict[str, Any]:
    execution = profile.get("execution")

    if not isinstance(execution, dict):
        raise ExecutionPlanValidationError(
            "Execution profile must contain execution."
        )

    mode = normalize_status(
        execution.get("mode")
    )

    if mode not in {
        "DURATION",
        "ITERATIONS",
    }:
        raise ExecutionPlanValidationError(
            "execution.mode must be DURATION or ITERATIONS."
        )

    threads = require_positive_int(
        execution.get("threads"),
        "profile.execution.threads",
    )

    ramp = require_nonnegative_int(
        execution.get("ramp_time_seconds"),
        "profile.execution.ramp_time_seconds",
    )

    pacing = require_nonnegative_number(
        execution.get("pacing_seconds"),
        "profile.execution.pacing_seconds",
    )

    duration = execution.get(
        "duration_seconds"
    )
    iterations = execution.get(
        "iterations"
    )

    if mode == "DURATION":
        duration = require_positive_int(
            duration,
            "profile.execution.duration_seconds",
        )
        if iterations is not None:
            raise ExecutionPlanValidationError(
                "DURATION profile requires iterations: null."
            )

    if mode == "ITERATIONS":
        iterations = require_positive_int(
            iterations,
            "profile.execution.iterations",
        )
        if duration is not None:
            raise ExecutionPlanValidationError(
                "ITERATIONS profile requires duration_seconds: null."
            )

    profile_meta = profile.get("profile")
    profile_name = (
        profile_meta.get("name")
        if isinstance(profile_meta, dict)
        else None
    )

    return {
        "name": str(profile_name or "unnamed"),
        "mode": mode,
        "threads": threads,
        "ramp_time_seconds": ramp,
        "duration_seconds": duration,
        "iterations": iterations,
        "pacing_seconds": pacing,
    }


def normalize_approved_workload(
    plan: dict[str, Any],
) -> dict[str, Any]:
    parameters, workload_status = (
        resolve_workload_section(plan)
    )

    plan_status = resolve_plan_status(plan)

    if plan_status and plan_status != "APPROVED":
        raise ExecutionPlanValidationError(
            "Plan must be APPROVED before an execution "
            f"profile can be compared. Current plan status: {plan_status}"
        )

    if workload_status and workload_status != "APPROVED":
        raise ExecutionPlanValidationError(
            "Workload must be APPROVED before an execution "
            f"profile can be compared. Current workload status: "
            f"{workload_status}"
        )

    _, threads_raw = first_value(
        parameters,
        THREAD_KEYS,
    )
    _, ramp_raw = first_value(
        parameters,
        RAMP_KEYS,
    )
    _, duration_raw = first_value(
        parameters,
        DURATION_KEYS,
    )
    _, iterations_raw = first_value(
        parameters,
        ITERATION_KEYS,
    )
    _, pacing_raw = first_value(
        parameters,
        PACING_KEYS,
    )

    if threads_raw is None:
        raise ExecutionPlanValidationError(
            "Approved workload does not define concurrency. "
            f"Expected one of: {', '.join(THREAD_KEYS)}"
        )

    threads = require_positive_int(
        threads_raw,
        "approved workload concurrency",
    )

    ramp = (
        require_nonnegative_int(
            ramp_raw,
            "approved workload ramp-up",
        )
        if ramp_raw is not None
        else None
    )

    pacing = (
        require_nonnegative_number(
            pacing_raw,
            "approved workload pacing",
        )
        if pacing_raw is not None
        else None
    )

    duration = None
    iterations = None

    if duration_raw is not None:
        duration = require_positive_int(
            duration_raw,
            "approved workload duration",
        )

    if iterations_raw is not None:
        iterations = require_positive_int(
            iterations_raw,
            "approved workload iterations",
        )

    if duration is not None and iterations is not None:
        raise ExecutionPlanValidationError(
            "Approved workload defines both duration and iterations. "
            "Execution semantics are ambiguous."
        )

    if duration is not None:
        mode = "DURATION"
    elif iterations is not None:
        mode = "ITERATIONS"
    else:
        raise ExecutionPlanValidationError(
            "Approved workload must define duration or iterations."
        )

    return {
        "mode": mode,
        "threads": threads,
        "ramp_time_seconds": ramp,
        "duration_seconds": duration,
        "iterations": iterations,
        "pacing_seconds": pacing,
        "plan_status": plan_status or "UNKNOWN",
        "workload_status": workload_status or "UNKNOWN",
        "authorization_status": resolve_authorization_status(
            plan
        ) or "UNKNOWN",
    }


def compare(
    approved: dict[str, Any],
    requested: dict[str, Any],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    def block(
        code: str,
        message: str,
    ) -> None:
        findings.append(
            {
                "severity": "ERROR",
                "code": code,
                "message": message,
            }
        )

    def info(
        code: str,
        message: str,
    ) -> None:
        findings.append(
            {
                "severity": "INFO",
                "code": code,
                "message": message,
            }
        )

    if requested["mode"] != approved["mode"]:
        block(
            "WORKLOAD-MODE-MISMATCH",
            "Requested execution mode "
            f"{requested['mode']} differs from approved mode "
            f"{approved['mode']}.",
        )

    if requested["threads"] > approved["threads"]:
        block(
            "WORKLOAD-CONCURRENCY-ESCALATION",
            "Requested threads "
            f"{requested['threads']} exceed approved concurrency "
            f"{approved['threads']}.",
        )
    elif requested["threads"] < approved["threads"]:
        info(
            "WORKLOAD-CONCURRENCY-LOWER",
            "Requested threads are below the approved maximum.",
        )

    approved_ramp = approved[
        "ramp_time_seconds"
    ]

    if approved_ramp is not None:
        if requested["ramp_time_seconds"] < approved_ramp:
            block(
                "WORKLOAD-RAMP-ESCALATION",
                "Requested ramp-up "
                f"{requested['ramp_time_seconds']}s is faster than "
                f"approved ramp-up {approved_ramp}s.",
            )
        elif requested["ramp_time_seconds"] > approved_ramp:
            info(
                "WORKLOAD-RAMP-SLOWER",
                "Requested ramp-up is slower than the approved ramp-up.",
            )

    if approved["mode"] == "DURATION":
        approved_duration = approved[
            "duration_seconds"
        ]
        requested_duration = requested[
            "duration_seconds"
        ]

        if (
            requested_duration is not None
            and approved_duration is not None
            and requested_duration > approved_duration
        ):
            block(
                "WORKLOAD-DURATION-ESCALATION",
                "Requested duration "
                f"{requested_duration}s exceeds approved duration "
                f"{approved_duration}s.",
            )
        elif (
            requested_duration is not None
            and approved_duration is not None
            and requested_duration < approved_duration
        ):
            info(
                "WORKLOAD-DURATION-LOWER",
                "Requested duration is below the approved maximum.",
            )

    if approved["mode"] == "ITERATIONS":
        approved_iterations = approved[
            "iterations"
        ]
        requested_iterations = requested[
            "iterations"
        ]

        if (
            requested_iterations is not None
            and approved_iterations is not None
            and requested_iterations > approved_iterations
        ):
            block(
                "WORKLOAD-ITERATION-ESCALATION",
                "Requested iterations "
                f"{requested_iterations} exceed approved iterations "
                f"{approved_iterations}.",
            )
        elif (
            requested_iterations is not None
            and approved_iterations is not None
            and requested_iterations < approved_iterations
        ):
            info(
                "WORKLOAD-ITERATION-LOWER",
                "Requested iterations are below the approved maximum.",
            )

    approved_pacing = approved[
        "pacing_seconds"
    ]

    if approved_pacing is not None:
        if requested["pacing_seconds"] < approved_pacing:
            block(
                "WORKLOAD-PACING-ESCALATION",
                "Requested pacing "
                f"{requested['pacing_seconds']}s is lower/faster than "
                f"approved pacing {approved_pacing}s.",
            )
        elif requested["pacing_seconds"] > approved_pacing:
            info(
                "WORKLOAD-PACING-SLOWER",
                "Requested pacing is slower than the approved minimum.",
            )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare an execution profile against the workload "
            "approved in a Performance Test Plan."
        )
    )

    parser.add_argument(
        "--plan",
        required=True,
    )
    parser.add_argument(
        "--profile",
        required=True,
    )

    args = parser.parse_args()

    plan_path = (
        Path(args.plan)
        .expanduser()
        .resolve()
    )
    profile_path = (
        Path(args.profile)
        .expanduser()
        .resolve()
    )

    try:
        plan = load_yaml(plan_path)
        profile = load_yaml(profile_path)

        approved = normalize_approved_workload(
            plan
        )
        requested = normalize_profile(
            profile
        )
        findings = compare(
            approved,
            requested,
        )

        errors = [
            item
            for item in findings
            if item["severity"] == "ERROR"
        ]

        infos = [
            item
            for item in findings
            if item["severity"] == "INFO"
        ]

        status = (
            "BLOCKED"
            if errors
            else "PASS"
        )

    except ExecutionPlanValidationError as exc:
        print("=" * 72)
        print(
            "EXECUTION PROFILE VS APPROVED PLAN"
        )
        print("=" * 72)
        print("Status : BLOCKED")
        print(f"Error  : {exc}")
        print("=" * 72)
        return 2

    print("=" * 72)
    print(
        "EXECUTION PROFILE VS APPROVED PLAN"
    )
    print("=" * 72)
    print(f"Status              : {status}")
    print(
        f"Profile             : "
        f"{requested['name']}"
    )
    print(
        f"Approved mode       : "
        f"{approved['mode']}"
    )
    print(
        f"Requested mode      : "
        f"{requested['mode']}"
    )
    print(
        f"Approved threads    : "
        f"{approved['threads']}"
    )
    print(
        f"Requested threads   : "
        f"{requested['threads']}"
    )
    print(
        f"Approved ramp-up    : "
        f"{approved['ramp_time_seconds']}"
    )
    print(
        f"Requested ramp-up   : "
        f"{requested['ramp_time_seconds']}"
    )

    if approved["mode"] == "DURATION":
        print(
            f"Approved duration   : "
            f"{approved['duration_seconds']}"
        )
        print(
            f"Requested duration  : "
            f"{requested['duration_seconds']}"
        )
    else:
        print(
            f"Approved iterations : "
            f"{approved['iterations']}"
        )
        print(
            f"Requested iterations: "
            f"{requested['iterations']}"
        )

    print(
        f"Approved pacing     : "
        f"{approved['pacing_seconds']}"
    )
    print(
        f"Requested pacing    : "
        f"{requested['pacing_seconds']}"
    )
    print(
        f"Plan status         : "
        f"{approved['plan_status']}"
    )
    print(
        f"Workload status     : "
        f"{approved['workload_status']}"
    )
    print(
        f"Authorization       : "
        f"{approved['authorization_status']} "
        "(not changed by this validation)"
    )
    print(
        f"Errors              : "
        f"{len(errors)}"
    )
    print(
        f"Info                : "
        f"{len(infos)}"
    )

    for item in findings:
        print()
        print(
            f"[{item['severity']}] "
            f"{item['code']}"
        )
        print(
            f"  {item['message']}"
        )

    print("=" * 72)

    if status == "PASS":
        print(
            "PROFILE IS WITHIN APPROVED WORKLOAD"
        )
        return 0

    print(
        "EXECUTION BLOCKED: PROFILE EXCEEDS "
        "APPROVED WORKLOAD"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
