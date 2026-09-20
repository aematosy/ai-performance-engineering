from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NaturalExecutionScenarioResolutionTests(
    unittest.TestCase
):

    def test_natural_wrapper_uses_scenario_resolver(
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
            "scripts/resolve_execution_scenario.py",
            text,
        )

        self.assertIn(
            "CANONICAL_SCENARIO",
            text,
        )

    def test_existing_orchestrator_is_still_used(
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
            "scripts/natural_performance_execute.py",
            text,
        )

    def test_resolved_arguments_are_delegated(
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
            '"${RESOLVED_ARGS[@]}"',
            text,
        )


if __name__ == "__main__":
    unittest.main()
