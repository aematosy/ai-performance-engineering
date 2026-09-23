from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReportBundleEngineSemanticsTests(unittest.TestCase):
    def test_html_enhancer_preserves_objective_and_target_semantics(self):
        source = (
            ROOT
            / "scripts"
            / "reporting"
            / "enhance_html_report.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn('"Target": "Objetivo"', source)
        self.assertNotIn("updateTargetCard", source)

    def test_bundle_uses_locust_metrics_port_for_locust(self):
        source = (
            ROOT
            / "scripts"
            / "reporting"
            / "build_report_bundle.py"
        ).read_text(encoding="utf-8")

        self.assertIn('self.engine == "LOCUST"', source)
        self.assertIn('http://localhost:9271/metrics', source)

    def test_locust_reporting_passes_engine_identity(self):
        source = (
            ROOT
            / "src"
            / "performance_engineering"
            / "reporting"
            / "locust_reporting.py"
        ).read_text(encoding="utf-8")

        self.assertIn('"--engine",', source)
        self.assertIn('"LOCUST",', source)


if __name__ == "__main__":
    unittest.main()
