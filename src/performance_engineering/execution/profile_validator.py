#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


ALLOWED_MODES = {"DURATION", "ITERATIONS"}
ALLOWED_SHARING = {
    "all_threads",
    "current_thread_group",
    "current_thread",
}
ALLOWED_ROW_CONSUMPTION = {
    "PER_ITERATION",
    "PER_THREAD",
}


class ExecutionProfileError(RuntimeError):
    pass


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(
            path.read_text(
                encoding="utf-8",
            )
        )
    except FileNotFoundError as exc:
        raise ExecutionProfileError(
            f"File not found: {path}"
        ) from exc
    except yaml.YAMLError as exc:
        raise ExecutionProfileError(
            f"Invalid YAML: {exc}"
        ) from exc

    if not isinstance(
        data,
        dict,
    ):
        raise ExecutionProfileError(
            "Profile root must be an object."
        )

    return data


def require_int(
    section: dict[str, Any],
    key: str,
    *,
    minimum: int = 0,
) -> int:
    value = section.get(key)

    if not isinstance(value, int):
        raise ExecutionProfileError(
            f"{key} must be an integer."
        )

    if value < minimum:
        raise ExecutionProfileError(
            f"{key} must be >= {minimum}."
        )

    return value


def require_number(
    section: dict[str, Any],
    key: str,
    *,
    minimum: float = 0.0,
) -> float:
    value = section.get(key)

    if not isinstance(
        value,
        (int, float),
    ):
        raise ExecutionProfileError(
            f"{key} must be numeric."
        )

    value = float(value)

    if value < minimum:
        raise ExecutionProfileError(
            f"{key} must be >= {minimum}."
        )

    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a deterministic "
            "performance execution profile."
        )
    )

    parser.add_argument(
        "--profile",
        required=True,
    )

    args = parser.parse_args()

    path = (
        Path(args.profile)
        .expanduser()
        .resolve()
    )

    try:
        data = load_yaml(path)

        if data.get(
            "schema_version"
        ) != "1.0":
            raise ExecutionProfileError(
                "schema_version must be '1.0'."
            )

        profile = data.get("profile")
        if not isinstance(
            profile,
            dict,
        ):
            raise ExecutionProfileError(
                "profile must be an object."
            )

        name = profile.get("name")
        if not isinstance(
            name,
            str,
        ) or not name.strip():
            raise ExecutionProfileError(
                "profile.name is required."
            )

        execution = data.get(
            "execution"
        )
        if not isinstance(
            execution,
            dict,
        ):
            raise ExecutionProfileError(
                "execution must be an object."
            )

        mode = execution.get(
            "mode"
        )

        if mode not in ALLOWED_MODES:
            raise ExecutionProfileError(
                "execution.mode must be "
                "DURATION or ITERATIONS."
            )

        threads = require_int(
            execution,
            "threads",
            minimum=1,
        )

        ramp = require_int(
            execution,
            "ramp_time_seconds",
            minimum=0,
        )

        pacing = require_number(
            execution,
            "pacing_seconds",
            minimum=0.0,
        )

        duration = execution.get(
            "duration_seconds"
        )
        iterations = execution.get(
            "iterations"
        )

        if mode == "DURATION":
            if not isinstance(
                duration,
                int,
            ) or duration < 1:
                raise ExecutionProfileError(
                    "DURATION mode requires "
                    "duration_seconds >= 1."
                )

            if iterations is not None:
                raise ExecutionProfileError(
                    "DURATION mode requires "
                    "iterations: null."
                )

        if mode == "ITERATIONS":
            if not isinstance(
                iterations,
                int,
            ) or iterations < 1:
                raise ExecutionProfileError(
                    "ITERATIONS mode requires "
                    "iterations >= 1."
                )

            if duration is not None:
                raise ExecutionProfileError(
                    "ITERATIONS mode requires "
                    "duration_seconds: null."
                )

        data_section = data.get(
            "data"
        )
        if not isinstance(
            data_section,
            dict,
        ):
            raise ExecutionProfileError(
                "data must be an object."
            )

        recycle = data_section.get(
            "recycle"
        )

        if not isinstance(
            recycle,
            bool,
        ):
            raise ExecutionProfileError(
                "data.recycle must be boolean."
            )

        stop_on_eof = data_section.get(
            "stop_thread_on_eof"
        )

        if not isinstance(
            stop_on_eof,
            bool,
        ):
            raise ExecutionProfileError(
                "data.stop_thread_on_eof "
                "must be boolean."
            )

        sharing = data_section.get(
            "sharing_mode"
        )

        if (
            sharing
            not in ALLOWED_SHARING
        ):
            raise ExecutionProfileError(
                "Unsupported data.sharing_mode."
            )

        row_consumption = data_section.get(
            "row_consumption"
        )

        if (
            row_consumption
            not in ALLOWED_ROW_CONSUMPTION
        ):
            raise ExecutionProfileError(
                "data.row_consumption must be "
                "PER_ITERATION or PER_THREAD."
            )

        if recycle and stop_on_eof:
            raise ExecutionProfileError(
                "data.recycle=true and "
                "stop_thread_on_eof=true are "
                "contradictory."
            )

        timeouts = data.get(
            "timeouts"
        )
        if not isinstance(
            timeouts,
            dict,
        ):
            raise ExecutionProfileError(
                "timeouts must be an object."
            )

        connect_timeout = require_int(
            timeouts,
            "connect_timeout_ms",
            minimum=1,
        )

        response_timeout = require_int(
            timeouts,
            "response_timeout_ms",
            minimum=1,
        )

        observability = data.get(
            "observability"
        )
        if not isinstance(
            observability,
            dict,
        ):
            raise ExecutionProfileError(
                "observability must be an object."
            )

        prometheus_port = require_int(
            observability,
            "prometheus_port",
            minimum=1,
        )

        if prometheus_port > 65535:
            raise ExecutionProfileError(
                "prometheus_port must be <= 65535."
            )

    except ExecutionProfileError as exc:
        print("=" * 72)
        print(
            "PERFORMANCE EXECUTION PROFILE "
            "VALIDATION"
        )
        print("=" * 72)
        print("Status : FAIL")
        print(f"Error  : {exc}")
        print("=" * 72)
        return 2

    print("=" * 72)
    print(
        "PERFORMANCE EXECUTION PROFILE "
        "VALIDATION"
    )
    print("=" * 72)
    print("Status      : PASS")
    print(f"Profile     : {name}")
    print(f"Mode        : {mode}")
    print(f"Threads     : {threads}")
    print(f"Ramp-up     : {ramp}s")

    if mode == "DURATION":
        print(
            f"Duration    : "
            f"{duration}s"
        )
    else:
        print(
            f"Iterations  : "
            f"{iterations}"
        )

    print(
        f"Pacing      : "
        f"{pacing}s"
    )
    print(
        f"Recycle CSV : "
        f"{recycle}"
    )
    print(
        f"Sharing     : "
        f"{sharing}"
    )
    print(
        f"Connect TO  : "
        f"{connect_timeout}ms"
    )
    print(
        f"Response TO : "
        f"{response_timeout}ms"
    )
    print(
        f"Prometheus  : "
        f"{prometheus_port}"
    )
    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
