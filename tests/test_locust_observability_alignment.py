from __future__ import annotations

import unittest
from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)


class LocustObservabilityAlignmentTests(
    unittest.TestCase
):
    def test_public_runner_imports_real_module(
        self,
    ):
        text = (
            ROOT
            / "scripts"
            / "run_governed_engine.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "performance_engineering.execution.governed_engine_runner",
            text,
        )

        self.assertNotIn(
            "exec(",
            text,
        )

        self.assertNotIn(
            "compile(",
            text,
        )

    def test_natural_wrapper_passes_project_results_root(
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
            '--results-root "${ROOT}/results"',
            text,
        )

        self.assertIn(
            '--scenario "${SCENARIO}"',
            text,
        )

    def test_exporter_is_scenario_scoped(
        self,
    ):
        text = (
            ROOT
            / "scripts"
            / "locust_metrics_exporter.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'f"locust-{self.scenario}"',
            text,
        )

        self.assertIn(
            '"locust_stats_history.csv"',
            text,
        )


if __name__ == "__main__":
    unittest.main()
