#!/usr/bin/env python3
from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]

VALIDATOR = (
    ROOT
    / "scripts"
    / "validate_execution_profile.py"
)

CAPACITY = (
    ROOT
    / "scripts"
    / "validate_data_capacity.py"
)


def profile(
    *,
    mode="ITERATIONS",
    threads=2,
    duration=None,
    iterations=3,
    recycle=False,
    stop_thread_on_eof=True,
    sharing_mode="all_threads",
    row_consumption="PER_ITERATION",
):
    return {
        "schema_version": "1.0",
        "profile": {
            "name": "test",
            "description": "test",
        },
        "execution": {
            "mode": mode,
            "threads": threads,
            "ramp_time_seconds": 5,
            "duration_seconds": duration,
            "iterations": iterations,
            "pacing_seconds": 1.0,
        },
        "data": {
            "recycle": recycle,
            "stop_thread_on_eof": stop_thread_on_eof,
            "sharing_mode": sharing_mode,
            "row_consumption": row_consumption,
        },
        "timeouts": {
            "connect_timeout_ms": 5000,
            "response_timeout_ms": 10000,
        },
        "observability": {
            "prometheus_port": 9270,
        },
    }


class ExecutionProfileTests(
    unittest.TestCase
):
    def write_profile(
        self,
        tmp: Path,
        payload,
    ) -> Path:
        p = tmp / "profile.yaml"
        p.write_text(
            yaml.safe_dump(
                payload,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        return p

    def write_csv(
        self,
        tmp: Path,
        rows: int,
    ) -> Path:
        p = tmp / "data.csv"

        with p.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as fh:
            writer = csv.writer(
                fh
            )
            writer.writerow(
                [
                    "firstname",
                    "lastname",
                ]
            )

            for i in range(
                rows
            ):
                writer.writerow(
                    [
                        f"name{i}",
                        f"last{i}",
                    ]
                )

        return p

    def test_valid_iteration_profile(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)

            p = self.write_profile(
                tmp,
                profile(),
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--profile",
                    str(p),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(
                result.returncode,
                0,
                result.stdout
                + result.stderr,
            )

    def test_mode_mutual_exclusion(
        self,
    ):
        payload = profile()
        payload[
            "execution"
        ]["duration_seconds"] = 60

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            p = self.write_profile(
                tmp,
                payload,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--profile",
                    str(p),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(
                result.returncode,
                0,
            )

    def test_insufficient_rows_fail(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)

            p = self.write_profile(
                tmp,
                profile(
                    threads=2,
                    iterations=3,
                ),
            )
            csv_path = self.write_csv(
                tmp,
                rows=5,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(CAPACITY),
                    "--profile",
                    str(p),
                    "--csv",
                    str(csv_path),
                    "--execution-ready",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(
                result.returncode,
                0,
            )

            self.assertIn(
                "INSUFFICIENT_ROWS",
                result.stdout,
            )

    def test_exact_rows_pass(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)

            p = self.write_profile(
                tmp,
                profile(
                    threads=2,
                    iterations=3,
                ),
            )
            csv_path = self.write_csv(
                tmp,
                rows=6,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(CAPACITY),
                    "--profile",
                    str(p),
                    "--csv",
                    str(csv_path),
                    "--execution-ready",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(
                result.returncode,
                0,
                result.stdout
                + result.stderr,
            )

    def test_duration_without_recycle_is_not_provable(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)

            p = self.write_profile(
                tmp,
                profile(
                    mode="DURATION",
                    duration=60,
                    iterations=None,
                    recycle=False,
                    stop_thread_on_eof=True,
                ),
            )
            csv_path = self.write_csv(
                tmp,
                rows=100,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(CAPACITY),
                    "--profile",
                    str(p),
                    "--csv",
                    str(csv_path),
                    "--execution-ready",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(
                result.returncode,
                0,
            )

            self.assertIn(
                "CAPACITY_NOT_PROVABLE",
                result.stdout,
            )


if __name__ == "__main__":
    unittest.main()
