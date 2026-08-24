#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

SCRIPT = (
    ROOT
    / "scripts"
    / "pre_execution_gate.py"
)


class PreExecutionGateV2Tests(
    unittest.TestCase
):
    def test_required_stages_present(
        self,
    ):
        source = SCRIPT.read_text(
            encoding="utf-8",
        )

        for expected in (
            "VALIDATE_TEST_PLAN",
            "VALIDATE_EXECUTION_PROFILE",
            "COMPARE_PROFILE_TO_APPROVED_PLAN",
            "VALIDATE_EXECUTION_BUNDLE",
            "VALIDATE_DATA_CAPACITY",
            "VALIDATE_DESIGN_CONTEXT",
            "VALIDATE_JMX_ARTIFACT",
        ):
            self.assertIn(
                expected,
                source,
            )

    def test_gate_never_executes_or_authorizes(
        self,
    ):
        source = SCRIPT.read_text(
            encoding="utf-8",
        )

        self.assertIn(
            '"execution_performed": False',
            source,
        )
        self.assertIn(
            '"granted_by_gate": False',
            source,
        )
        self.assertNotIn(
            'subprocess.run(["jmeter"',
            source,
        )

    def test_csv_requires_data_requirements(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)

            plan = (
                tmp
                / "plan.yaml"
            )
            profile = (
                tmp
                / "profile.yaml"
            )
            csv_path = (
                tmp
                / "data.csv"
            )

            plan.write_text(
                "metadata:\n"
                "  name: demo\n",
                encoding="utf-8",
            )

            profile.write_text(
                "schema_version: '1.0'\n",
                encoding="utf-8",
            )

            csv_path.write_text(
                "a\n1\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--plan",
                    str(plan),
                    "--profile",
                    str(profile),
                    "--csv",
                    str(csv_path),
                    "--skip-environment",
                    "--skip-plan-review",
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
                "CSV requires --data-requirements",
                result.stderr,
            )

    def test_design_context_requires_data_requirements(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)

            plan = (
                tmp
                / "plan.yaml"
            )
            profile = (
                tmp
                / "profile.yaml"
            )
            context = (
                tmp
                / "context.json"
            )

            plan.write_text(
                "metadata:\n"
                "  name: demo\n",
                encoding="utf-8",
            )

            profile.write_text(
                "schema_version: '1.0'\n",
                encoding="utf-8",
            )

            context.write_text(
                "{}",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--plan",
                    str(plan),
                    "--profile",
                    str(profile),
                    "--design-context",
                    str(context),
                    "--skip-environment",
                    "--skip-plan-review",
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
                "Design context requires --data-requirements",
                result.stderr,
            )

    def test_manifest_schema_is_v2(
        self,
    ):
        source = SCRIPT.read_text(
            encoding="utf-8",
        )
        self.assertIn(
            '"schema_version": "2.0"',
            source,
        )
        self.assertIn(
            '"data_requirements":',
            source,
        )


if __name__ == "__main__":
    unittest.main()
