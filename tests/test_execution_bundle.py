#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_execution_bundle.py"


class ExecutionBundleTests(unittest.TestCase):
    def write_yaml(self, path: Path, payload) -> None:
        path.write_text(
            yaml.safe_dump(payload, sort_keys=False),
            encoding="utf-8",
        )

    def write_json(self, path: Path, payload) -> None:
        path.write_text(
            json.dumps(payload),
            encoding="utf-8",
        )

    def run_bundle(self, args: list[str]):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                *args,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def test_real_plan_shape_metadata_name_is_supported(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            plan = tmp / "plan.yaml"
            jmx = tmp / "create-post-demo.jmx"
            metadata = Path(str(jmx) + ".meta.json")

            self.write_yaml(
                plan,
                {
                    "metadata": {
                        "name": "create-post-demo",
                        "version": "1.0",
                        "description": "fixture",
                    },
                    "status": "APPROVED",
                },
            )

            jmx.write_text("<jmeterTestPlan/>", encoding="utf-8")

            self.write_json(
                metadata,
                {
                    "scenario": "create-post-demo",
                },
            )

            result = self.run_bundle(
                [
                    "--plan",
                    str(plan),
                    "--jmx",
                    str(jmx),
                ]
            )

            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            self.assertIn(
                "Plan scenario       : create-post-demo",
                result.stdout,
            )

    def test_context_and_data_candidate_match(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)

            plan = tmp / "plan.yaml"
            context = tmp / "context.json"
            reqs = tmp / "reqs.json"

            self.write_yaml(
                plan,
                {
                    "metadata": {
                        "name": "booking-update",
                    },
                    "source_binding": {
                        "source_type": "POSTMAN",
                        "candidate_id": "booking-update-flow",
                    },
                },
            )

            self.write_json(
                context,
                {
                    "scenario_candidate": {
                        "id": "booking-update-flow",
                    }
                },
            )

            self.write_json(
                reqs,
                {
                    "scenario_candidate": {
                        "id": "booking-update-flow",
                    }
                },
            )

            result = self.run_bundle(
                [
                    "--plan",
                    str(plan),
                    "--design-context",
                    str(context),
                    "--data-requirements",
                    str(reqs),
                    "--require-explicit-source-binding",
                ]
            )

            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )

    def test_context_and_data_candidate_mismatch_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)

            plan = tmp / "plan.yaml"
            context = tmp / "context.json"
            reqs = tmp / "reqs.json"

            self.write_yaml(
                plan,
                {
                    "metadata": {
                        "name": "booking-update",
                    },
                    "source_binding": {
                        "candidate_id": "booking-update-flow",
                    },
                },
            )

            self.write_json(
                context,
                {
                    "scenario_candidate": {
                        "id": "booking-update-flow",
                    }
                },
            )

            self.write_json(
                reqs,
                {
                    "scenario_candidate": {
                        "id": "booking-create-flow",
                    }
                },
            )

            result = self.run_bundle(
                [
                    "--plan",
                    str(plan),
                    "--design-context",
                    str(context),
                    "--data-requirements",
                    str(reqs),
                    "--require-explicit-source-binding",
                ]
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "BUNDLE-CONTEXT-DATA-CANDIDATE-MISMATCH",
                result.stdout,
            )

    def test_missing_explicit_plan_binding_blocks_when_required(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)

            plan = tmp / "plan.yaml"
            context = tmp / "context.json"

            self.write_yaml(
                plan,
                {
                    "metadata": {
                        "name": "booking-update",
                    },
                },
            )

            self.write_json(
                context,
                {
                    "scenario_candidate": {
                        "id": "booking-update-flow",
                    }
                },
            )

            result = self.run_bundle(
                [
                    "--plan",
                    str(plan),
                    "--design-context",
                    str(context),
                    "--require-explicit-source-binding",
                ]
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "BUNDLE-PLAN-SOURCE-BINDING-MISSING",
                result.stdout,
            )

    def test_plan_jmx_scenario_mismatch_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)

            plan = tmp / "plan.yaml"
            jmx = tmp / "demo.jmx"
            metadata = Path(str(jmx) + ".meta.json")

            self.write_yaml(
                plan,
                {
                    "metadata": {
                        "name": "scenario-a",
                    },
                },
            )

            jmx.write_text("<jmeterTestPlan/>", encoding="utf-8")

            self.write_json(
                metadata,
                {
                    "scenario": "scenario-b",
                },
            )

            result = self.run_bundle(
                [
                    "--plan",
                    str(plan),
                    "--jmx",
                    str(jmx),
                ]
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "BUNDLE-PLAN-JMX-SCENARIO-MISMATCH",
                result.stdout,
            )


if __name__ == "__main__":
    unittest.main()
