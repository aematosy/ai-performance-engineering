#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

import yaml


class DataCapacityError(RuntimeError):
    pass


def load_yaml(
    path: Path,
) -> dict[str, Any]:
    try:
        data = yaml.safe_load(
            path.read_text(
                encoding="utf-8",
            )
        )
    except FileNotFoundError as exc:
        raise DataCapacityError(
            f"File not found: {path}"
        ) from exc
    except yaml.YAMLError as exc:
        raise DataCapacityError(
            f"Invalid YAML: {exc}"
        ) from exc

    if not isinstance(
        data,
        dict,
    ):
        raise DataCapacityError(
            "Profile root must be an object."
        )

    return data


def count_csv_rows(
    path: Path,
) -> tuple[int, int]:
    try:
        with path.open(
            newline="",
            encoding="utf-8",
        ) as fh:
            reader = csv.reader(
                fh
            )

            try:
                header = next(
                    reader
                )
            except StopIteration:
                return 0, 0

            data_rows = sum(
                1
                for row in reader
                if any(
                    str(value).strip()
                    for value in row
                )
            )

            return (
                len(header),
                data_rows,
            )

    except FileNotFoundError as exc:
        raise DataCapacityError(
            f"CSV not found: {path}"
        ) from exc


def required_rows(
    profile: dict[str, Any],
) -> tuple[
    int | None,
    str,
]:
    execution = profile.get(
        "execution",
        {},
    )

    data = profile.get(
        "data",
        {},
    )

    threads = execution.get(
        "threads"
    )
    mode = execution.get(
        "mode"
    )
    iterations = execution.get(
        "iterations"
    )
    row_consumption = data.get(
        "row_consumption"
    )
    sharing = data.get(
        "sharing_mode"
    )

    if not isinstance(
        threads,
        int,
    ) or threads < 1:
        raise DataCapacityError(
            "Invalid execution.threads."
        )

    if row_consumption == "PER_THREAD":
        return (
            threads,
            "one row per thread",
        )

    if row_consumption != "PER_ITERATION":
        raise DataCapacityError(
            "Unsupported row consumption."
        )

    if mode == "ITERATIONS":
        if not isinstance(
            iterations,
            int,
        ) or iterations < 1:
            raise DataCapacityError(
                "ITERATIONS mode requires "
                "iterations >= 1."
            )

        if sharing == "current_thread":
            return (
                iterations,
                (
                    "rows required per thread "
                    "because sharing_mode="
                    "current_thread"
                ),
            )

        return (
            threads * iterations,
            "threads × iterations",
        )

    if mode == "DURATION":
        return (
            None,
            (
                "duration-based PER_ITERATION "
                "consumption cannot be bounded "
                "deterministically without "
                "recycling"
            ),
        )

    raise DataCapacityError(
        f"Unsupported execution mode: {mode}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate CSV row capacity against "
            "an execution profile."
        )
    )

    parser.add_argument(
        "--profile",
        required=True,
    )
    parser.add_argument(
        "--csv",
        required=True,
    )
    parser.add_argument(
        "--execution-ready",
        action="store_true",
        help=(
            "Fail when capacity cannot be "
            "proven for execution."
        ),
    )

    args = parser.parse_args()

    profile_path = (
        Path(args.profile)
        .expanduser()
        .resolve()
    )
    csv_path = (
        Path(args.csv)
        .expanduser()
        .resolve()
    )

    try:
        profile = load_yaml(
            profile_path
        )

        columns, rows = count_csv_rows(
            csv_path
        )

        data = profile.get(
            "data",
            {},
        )

        recycle = data.get(
            "recycle"
        )

        if not isinstance(
            recycle,
            bool,
        ):
            raise DataCapacityError(
                "data.recycle must be boolean."
            )

        required, reason = required_rows(
            profile
        )

        if recycle:
            status = "PASS"
            capacity_state = "RECYCLING_ENABLED"

        elif required is None:
            status = (
                "FAIL"
                if args.execution_ready
                else "WARN"
            )
            capacity_state = (
                "CAPACITY_NOT_PROVABLE"
            )

        elif rows < required:
            status = "FAIL"
            capacity_state = (
                "INSUFFICIENT_ROWS"
            )

        else:
            status = "PASS"
            capacity_state = (
                "SUFFICIENT_ROWS"
            )

    except DataCapacityError as exc:
        print("=" * 72)
        print(
            "PERFORMANCE CSV CAPACITY "
            "VALIDATION"
        )
        print("=" * 72)
        print("Status : FAIL")
        print(f"Error  : {exc}")
        print("=" * 72)
        return 2

    print("=" * 72)
    print(
        "PERFORMANCE CSV CAPACITY "
        "VALIDATION"
    )
    print("=" * 72)
    print(
        f"Status         : "
        f"{status}"
    )
    print(
        f"Capacity state : "
        f"{capacity_state}"
    )
    print(
        f"CSV columns    : "
        f"{columns}"
    )
    print(
        f"CSV rows       : "
        f"{rows}"
    )
    print(
        f"Recycle        : "
        f"{recycle}"
    )
    print(
        f"Required rows  : "
        f"{required if required is not None else 'UNKNOWN'}"
    )
    print(
        f"Rule           : "
        f"{reason}"
    )
    print("=" * 72)

    return (
        0
        if status in {
            "PASS",
            "WARN",
        }
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
