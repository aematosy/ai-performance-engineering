from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NaturalExecutionHandoffTests(
    unittest.TestCase
):

    def test_runner_uses_single_public_entrypoint(
        self,
    ):
        text = (
            ROOT
            / ".axet-code/skills/performance-test-runner/SKILL.md"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "scripts/natural_performance_execute.sh --scenario",
            text,
        )

    def test_runner_forbids_direct_approval_script(
        self,
    ):
        text = (
            ROOT
            / ".axet-code/skills/performance-test-runner/SKILL.md"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "NO invoques",
            text,
        )

        self.assertIn(
            "scripts/approve_test_plan.py",
            text,
        )

    def test_natural_execution_syncs_state(
        self,
    ):
        text = (
            ROOT
            / "scripts/natural_performance_execute.sh"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "finalize_execution_state.py",
            text,
        )

    def test_natural_execution_requests_professional_report(
        self,
    ):
        text = (
            ROOT
            / "scripts/natural_performance_execute.sh"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "PERF_AUTO_PROFESSIONAL_REPORT",
            text,
        )

    def test_reporting_does_not_use_latest_directory_guess(
        self,
    ):
        text = (
            ROOT
            / "Makefile"
        ).read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            "LATEST_REPORT_DIR",
            text,
        )

        self.assertIn(
            "CURRENT_REPORT_DIR",
            text,
        )


if __name__ == "__main__":
    unittest.main()
