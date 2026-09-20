from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NaturalExecutionDualIdentityTests(
    unittest.TestCase
):

    def test_wrapper_preserves_requested_scenario(
        self,
    ):
        text = (
            ROOT
            / "scripts"
            / "natural_performance_execute.sh"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'PERF_REQUESTED_SCENARIO="${REQUESTED_SCENARIO:-}"',
            text,
        )

    def test_orchestrator_separates_workspace_identity(
        self,
    ):
        text = (
            ROOT
            / "scripts"
            / "natural_performance_execute.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            '"PERF_REQUESTED_SCENARIO"',
            text,
        )

        self.assertIn(
            '/ requested_scenario',
            text,
        )

        self.assertIn(
            '/ scenario',
            text,
        )

    def test_existing_artifact_is_reused(
        self,
    ):
        text = (
            ROOT
            / "scripts"
            / "natural_performance_execute.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'if artifact.is_file():',
            text,
        )

        self.assertIn(
            'Se reutilizará sin regenerarlo.',
            text,
        )


if __name__ == "__main__":
    unittest.main()
