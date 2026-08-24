#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_approved_plan.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "run_approved_plan_v2",
        RUNNER,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ControlledRunnerV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def authorized_plan(self):
        return {
            "metadata": {
                "name": "demo",
            },
            "status": "APPROVED",
            "environment": "demo",
            "target": {
                "protocol": "https",
                "host": "example.test",
                "port": 443,
            },
            "transactions": [
                {
                    "method": "GET",
                    "path": "/health",
                }
            ],
            "workload": {
                "status": "APPROVED",
                "parameters": {
                    "threads": 5,
                    "ramp_time_seconds": 10,
                    "duration_seconds": 60,
                    "pacing_seconds": 1.0,
                },
            },
            "authorization": {
                "status": "AUTHORIZED",
                "authorized_by": "Adrian Matos",
                "authorized_at": "2026-08-23T00:00:00-05:00",
            },
            "approval": {
                "execution_authorized": True,
            },
        }

    def profile(self):
        return {
            "execution": {
                "mode": "DURATION",
                "threads": 5,
                "ramp_time_seconds": 10,
                "duration_seconds": 60,
                "pacing_seconds": 1.0,
            },
            "observability": {
                "prometheus_port": 9270,
            },
        }

    def test_pending_authorization_is_blocked(self):
        plan = self.authorized_plan()
        plan["authorization"]["status"] = "PENDING"
        plan["authorization"]["authorized_by"] = None
        plan["authorization"]["authorized_at"] = None
        plan["approval"]["execution_authorized"] = False

        with self.assertRaises(
            self.module.ControlledExecutionError
        ):
            self.module.validate_execution_authorization(
                plan
            )

    def test_authorized_plan_passes_authorization_gate(self):
        result = (
            self.module
            .validate_execution_authorization(
                self.authorized_plan()
            )
        )

        self.assertEqual(
            result["status"],
            "AUTHORIZED",
        )

    def test_generic_authorizer_is_rejected(self):
        plan = self.authorized_plan()
        plan["authorization"]["authorized_by"] = "User"

        with self.assertRaises(
            self.module.ControlledExecutionError
        ):
            self.module.validate_execution_authorization(
                plan
            )

    def test_iteration_profile_is_blocked_for_now(self):
        profile = self.profile()
        profile["execution"]["mode"] = "ITERATIONS"
        profile["execution"]["duration_seconds"] = None
        profile["execution"]["iterations"] = 3

        with self.assertRaises(
            self.module.ControlledExecutionError
        ):
            self.module.profile_runtime(
                profile,
                self.authorized_plan(),
            )

    def test_pacing_change_is_blocked_until_runtime_support_exists(self):
        profile = self.profile()
        profile["execution"]["pacing_seconds"] = 2.0

        with self.assertRaises(
            self.module.ControlledExecutionError
        ):
            self.module.profile_runtime(
                profile,
                self.authorized_plan(),
            )

    def test_runtime_comes_from_profile(self):
        runtime = self.module.profile_runtime(
            self.profile(),
            self.authorized_plan(),
        )

        self.assertEqual(
            runtime["threads"],
            5,
        )
        self.assertEqual(
            runtime["duration_seconds"],
            60,
        )
        self.assertEqual(
            runtime["prometheus_port"],
            9270,
        )

    def test_manifest_hash_change_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            artifact = tmp / "artifact.txt"
            artifact.write_text(
                "before",
                encoding="utf-8",
            )

            manifest = {
                "inputs": {
                    "plan": {
                        "path": str(artifact),
                        "sha256": self.module.sha256(
                            artifact
                        ),
                    }
                }
            }

            artifact.write_text(
                "after",
                encoding="utf-8",
            )

            with self.assertRaises(
                self.module.ControlledExecutionError
            ):
                self.module.verify_manifest_artifact(
                    manifest,
                    "plan",
                    artifact,
                )

    def test_no_public_workload_override_flags(self):
        source = RUNNER.read_text(
            encoding="utf-8",
        )

        self.assertNotIn(
            'parser.add_argument("--threads"',
            source,
        )
        self.assertNotIn(
            'parser.add_argument("--duration"',
            source,
        )
        self.assertNotIn(
            'parser.add_argument("--ramp-time"',
            source,
        )
        self.assertNotIn(
            'mode.add_argument("--authorized"',
            source,
        )


if __name__ == "__main__":
    unittest.main()
