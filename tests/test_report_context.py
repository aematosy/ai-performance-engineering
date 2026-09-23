from __future__ import annotations

import unittest
from pathlib import Path

from performance_engineering.reporting.report_context import (
    format_percentage,
    format_throughput,
    resolve_report_scope,
    resolve_report_target,
)


ROOT = Path(__file__).resolve().parents[1]


class ReportContextTests(
    unittest.TestCase
):

    def test_resolves_current_dummyjson_target(
        self,
    ):
        target = resolve_report_target(
            project_root=ROOT,
            scenario="locust-dummyjson-final-e2e-v3",
        )

        self.assertEqual(
            target,
            "POST https://dummyjson.com/products/add",
        )


    def test_multi_transaction_scenario_uses_base_target(
        self,
    ):
        scope = resolve_report_scope(
            project_root=ROOT,
            scenario="booking-e2e",
        )

        self.assertEqual(
            scope.target,
            "https://restful-booker.herokuapp.com",
        )
        self.assertEqual(
            scope.transaction_count,
            7,
        )
        self.assertEqual(
            scope.scope_label,
            "7 transacciones",
        )
        self.assertEqual(
            scope.system,
            "RestFull Booker_test",
        )
        self.assertEqual(
            scope.objective,
            "Validar el comportamiento de performance "
            "del escenario booking-e2e bajo el workload aprobado.",
        )

    def test_single_transaction_scenario_keeps_method_and_endpoint(
        self,
    ):
        scope = resolve_report_scope(
            project_root=ROOT,
            scenario="get-post-ai-demo",
        )

        self.assertEqual(
            scope.target,
            "GET https://jsonplaceholder.typicode.com/posts/1",
        )
        self.assertEqual(
            scope.scope_label,
            "1 transacción",
        )
        self.assertEqual(
            scope.objective,
            "Validar el comportamiento de performance de GET /posts/1.",
        )

    def test_percentage_uses_two_decimals(
        self,
    ):
        self.assertEqual(
            format_percentage(
                100.0
            ),
            "100.00",
        )

        self.assertEqual(
            format_percentage(
                0.267
            ),
            "0.27",
        )

    def test_throughput_keeps_three_decimals(
        self,
    ):
        self.assertEqual(
            format_throughput(
                3.171
            ),
            "3.171",
        )


if __name__ == "__main__":
    unittest.main()
