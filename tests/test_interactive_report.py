import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

GENERATOR = (
    ROOT
    / "scripts"
    / "generate_report.py"
)


class InteractiveReportContractTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls):
        cls.source = GENERATOR.read_text()

    def test_theme_toggle_exists(self):
        self.assertIn(
            'id="theme-toggle"',
            self.source,
        )

    def test_light_theme_exists(self):
        self.assertIn(
            'html[data-theme="light"]',
            self.source,
        )

    def test_service_selector_exists(self):
        self.assertIn(
            'id="service-selector"',
            self.source,
        )

    def test_service_charts_exist(self):
        for chart_id in (
            "service-response-chart",
            "service-throughput-chart",
            "service-error-chart",
        ):
            self.assertIn(
                chart_id,
                self.source,
            )

    def test_all_transactions_is_supported(self):
        self.assertIn(
            "All Transactions",
            self.source,
        )

    def test_dashboard_uses_runtime_labels(self):
        self.assertIn(
            "payload.transactions",
            self.source,
        )

    def test_report_has_no_demo_service_hardcoding(self):
        forbidden = (
            "Booking/CreateBooking",
            "Auth/CreateToken",
            "restful-booker.herokuapp.com",
        )

        for value in forbidden:
            self.assertNotIn(
                value,
                self.source,
            )

    def test_theme_uses_semantic_tokens(self):
        required = (
            "--report-bg",
            "--report-panel",
            "--report-text",
            "--report-border",
            "--report-response",
            "--report-throughput",
            "--report-error",
        )

        for value in required:
            self.assertIn(
                value,
                self.source,
            )


if __name__ == "__main__":
    unittest.main()
