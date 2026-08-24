#!/usr/bin/env python3
from __future__ import annotations

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
    / "validate_execution_against_plan.py"
)


def plan(
    *,
    status="APPROVED",
    workload_status="APPROVED",
    threads=5,
    ramp=10,
    duration=60,
    iterations=None,
    pacing=1.0,
):
    parameters = {
        "threads": threads,
        "ramp_time_seconds": ramp,
        "duration_seconds": duration,
        "pacing_seconds": pacing,
    }

    if iterations is not None:
        parameters["duration_seconds"] = None
        parameters["iterations"] = iterations

    return {
        "scenario": {
            "name": "demo",
        },
        "status": status,
        "workload": {
            "status": workload_status,
            "parameters": parameters,
        },
        "authorization": {
            "status": "PENDING",
        },
    }


def profile(
    *,
    mode="DURATION",
    threads=5,
    ramp=10,
    duration=60,
    iterations=None,
    pacing=1.0,
):
    return {
        "schema_version": "1.0",
        "profile": {
            "name": "test",
        },
        "execution": {
            "mode": mode,
            "threads": threads,
            "ramp_time_seconds": ramp,
            "duration_seconds": duration,
            "iterations": iterations,
            "pacing_seconds": pacing,
        },
        "data": {
            "recycle": True,
            "stop_thread_on_eof": False,
            "sharing_mode": "all_threads",
            "row_consumption": "PER_ITERATION",
        },
        "timeouts": {
            "connect_timeout_ms": 5000,
            "response_timeout_ms": 10000,
        },
        "observability": {
            "prometheus_port": 9270,
        },
    }


class ExecutionAgainstPlanTests(
    unittest.TestCase
):
    def run_case(
        self,
        plan_payload,
        profile_payload,
    ):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)

            plan_path = tmp / "plan.yaml"
            profile_path = tmp / "profile.yaml"

            plan_path.write_text(
                yaml.safe_dump(
                    plan_payload,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            profile_path.write_text(
                yaml.safe_dump(
                    profile_payload,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            return subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--plan",
                    str(plan_path),
                    "--profile",
                    str(profile_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

    def test_exact_approved_profile_passes(
        self,
    ):
        result = self.run_case(
            plan(),
            profile(),
        )

        self.assertEqual(
            result.returncode,
            0,
            result.stdout + result.stderr,
        )

    def test_lower_load_passes(
        self,
    ):
        result = self.run_case(
            plan(),
            profile(
                threads=2,
                ramp=20,
                duration=30,
                pacing=2.0,
            ),
        )

        self.assertEqual(
            result.returncode,
            0,
            result.stdout + result.stderr,
        )

    def test_more_threads_blocked(
        self,
    ):
        result = self.run_case(
            plan(),
            profile(
                threads=6,
            ),
        )

        self.assertNotEqual(
            result.returncode,
            0,
        )

        self.assertIn(
            "WORKLOAD-CONCURRENCY-ESCALATION",
            result.stdout,
        )

    def test_faster_ramp_blocked(
        self,
    ):
        result = self.run_case(
            plan(),
            profile(
                ramp=5,
            ),
        )

        self.assertNotEqual(
            result.returncode,
            0,
        )

        self.assertIn(
            "WORKLOAD-RAMP-ESCALATION",
            result.stdout,
        )

    def test_longer_duration_blocked(
        self,
    ):
        result = self.run_case(
            plan(),
            profile(
                duration=61,
            ),
        )

        self.assertNotEqual(
            result.returncode,
            0,
        )

        self.assertIn(
            "WORKLOAD-DURATION-ESCALATION",
            result.stdout,
        )

    def test_faster_pacing_blocked(
        self,
    ):
        result = self.run_case(
            plan(),
            profile(
                pacing=0.5,
            ),
        )

        self.assertNotEqual(
            result.returncode,
            0,
        )

        self.assertIn(
            "WORKLOAD-PACING-ESCALATION",
            result.stdout,
        )

    def test_mode_mismatch_blocked(
        self,
    ):
        result = self.run_case(
            plan(),
            profile(
                mode="ITERATIONS",
                duration=None,
                iterations=3,
            ),
        )

        self.assertNotEqual(
            result.returncode,
            0,
        )

        self.assertIn(
            "WORKLOAD-MODE-MISMATCH",
            result.stdout,
        )

    def test_unapproved_workload_blocked(
        self,
    ):
        result = self.run_case(
            plan(
                workload_status="PROPOSED",
            ),
            profile(),
        )

        self.assertNotEqual(
            result.returncode,
            0,
        )

        self.assertIn(
            "Workload must be APPROVED",
            result.stdout,
        )


if __name__ == "__main__":
    unittest.main()
