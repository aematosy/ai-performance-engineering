from __future__ import annotations

import unittest
from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)


class LocustCompletionSemanticsTests(
    unittest.TestCase
):
    def test_execute_post_processing_does_not_require_jmx(
        self,
    ):
        text = (
            ROOT
            / "scripts"
            / "performance_workflow.py"
        ).read_text(
            encoding="utf-8"
        )

        main = text[
            text.index(
                "def main()"
            ):
        ]

        self.assertNotIn(
            '''resolve_path(
                            args.jmx''',
            main,
        )

        self.assertIn(
            "args.artifact",
            main,
        )

    def test_locust_exporter_has_finish_endpoint(
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
            'self.path != "/finish"',
            text,
        )

        self.assertIn(
            "self.finished = True",
            text,
        )

        self.assertIn(
            '"locust_metrics_up": 0.0',
            text,
        )

    def test_wrapper_flushes_metrics_before_shutdown(
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
            "http://localhost:9271/finish",
            text,
        )

        self.assertIn(
            "sleep 4",
            text,
        )

    def test_dashboard_uses_execution_metric_for_status(
        self,
    ):
        text = (
            ROOT
            / "grafana"
            / "dashboards"
            / "ai-performance-locust.json"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            '"expr": "locust_metrics_up"',
            text,
        )


if __name__ == "__main__":
    unittest.main()
