from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)


class LocustDashboardUXTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(
        cls,
    ):
        path = (
            ROOT
            / "grafana"
            / "dashboards"
            / "ai-performance-locust.json"
        )

        cls.dashboard = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        cls.panels = {
            panel.get("title"): panel
            for panel in cls.dashboard.get(
                "panels",
                [],
            )
        }

    def test_matches_jmeter_conceptual_layout(
        self,
    ):
        expected = {
            "Current Throughput",
            "Current p95",
            "Error Rate",
            "Active Virtual Users",
            "Locust Metrics",
            "Throughput by Sampler",
            "Response Time Percentiles",
            "Virtual Users Over Time",
            "Errors by Sampler",
            "Total Requests",
            "Información",
        }

        self.assertTrue(
            expected.issubset(
                self.panels.keys()
            )
        )

    def test_total_requests_preserves_execution_total(
        self,
    ):
        panel = self.panels[
            "Total Requests"
        ]

        expressions = {
            target.get(
                "expr"
            )
            for target in panel.get(
                "targets",
                [],
            )
        }

        self.assertIn(
            "max_over_time(locust_total_requests[$__range])",
            expressions,
        )

    def test_status_uses_execution_state_metric(
        self,
    ):
        panel = self.panels[
            "Locust Metrics"
        ]

        expressions = {
            target.get(
                "expr"
            )
            for target in panel.get(
                "targets",
                [],
            )
        }

        self.assertIn(
            "locust_metrics_up",
            expressions,
        )


if __name__ == "__main__":
    unittest.main()
