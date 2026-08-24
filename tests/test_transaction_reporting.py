import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(
        name,
        path,
    )

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(module)

    return module


ANALYZER = load_module(
    "transaction_analyzer",
    ROOT / "scripts" / "analyze_results.py",
)


class TransactionReportingTests(
    unittest.TestCase
):
    def write_jtl(self, rows):
        tmp = tempfile.NamedTemporaryFile(
            suffix=".jtl",
            delete=False,
            mode="w",
            newline="",
        )

        with tmp:
            writer = csv.DictWriter(
                tmp,
                fieldnames=[
                    "timeStamp",
                    "elapsed",
                    "label",
                    "success",
                    "responseCode",
                    "responseMessage",
                ],
            )

            writer.writeheader()

            for row in rows:
                writer.writerow(row)

        return Path(tmp.name)

    def test_arbitrary_labels_are_supported(self):
        path = self.write_jtl(
            [
                {
                    "timeStamp": "1000",
                    "elapsed": "100",
                    "label": "Customer/Search",
                    "success": "true",
                    "responseCode": "200",
                    "responseMessage": "OK",
                },
                {
                    "timeStamp": "1100",
                    "elapsed": "150",
                    "label": "Order/Create",
                    "success": "false",
                    "responseCode": "500",
                    "responseMessage": "Server Error",
                },
            ]
        )

        metrics = ANALYZER.analyze(path)

        labels = [
            tx["label"]
            for tx
            in metrics["transactions"]
        ]

        self.assertEqual(
            labels,
            [
                "Customer/Search",
                "Order/Create",
            ],
        )

    def test_transaction_error_rate(self):
        path = self.write_jtl(
            [
                {
                    "timeStamp": "1000",
                    "elapsed": "100",
                    "label": "Service-A",
                    "success": "true",
                    "responseCode": "200",
                    "responseMessage": "OK",
                },
                {
                    "timeStamp": "1100",
                    "elapsed": "200",
                    "label": "Service-A",
                    "success": "false",
                    "responseCode": "503",
                    "responseMessage": "Unavailable",
                },
            ]
        )

        metrics = ANALYZER.analyze(path)

        tx = metrics["transactions"][0]

        self.assertEqual(
            tx["samples"],
            2,
        )

        self.assertEqual(
            tx["error_count"],
            1,
        )

        self.assertEqual(
            tx["error_rate_pct"],
            50.0,
        )

    def test_response_codes_are_generic(self):
        path = self.write_jtl(
            [
                {
                    "timeStamp": "1000",
                    "elapsed": "100",
                    "label": "Anything",
                    "success": "true",
                    "responseCode": "207",
                    "responseMessage": "Multi-Status",
                },
                {
                    "timeStamp": "1100",
                    "elapsed": "100",
                    "label": "Anything",
                    "success": "false",
                    "responseCode": "429",
                    "responseMessage": "Too Many Requests",
                },
            ]
        )

        metrics = ANALYZER.analyze(path)

        tx = metrics["transactions"][0]

        self.assertEqual(
            tx["response_codes"],
            {
                "207": 1,
                "429": 1,
            },
        )

    def test_percentiles_exist_per_transaction(self):
        rows = []

        for index, elapsed in enumerate(
            [100, 110, 120, 130, 140]
        ):
            rows.append(
                {
                    "timeStamp": str(
                        1000 + index * 100
                    ),
                    "elapsed": str(elapsed),
                    "label": "Generic/API",
                    "success": "true",
                    "responseCode": "200",
                    "responseMessage": "OK",
                }
            )

        path = self.write_jtl(rows)

        metrics = ANALYZER.analyze(path)

        rt = (
            metrics["transactions"][0]
            ["response_time_ms"]
        )

        self.assertIsNotNone(rt["p90"])
        self.assertIsNotNone(rt["p95"])
        self.assertIsNotNone(rt["p99"])


if __name__ == "__main__":
    unittest.main()


class TransactionTimeSeriesTests(
    unittest.TestCase
):
    def test_series_are_grouped_by_arbitrary_label(self):
        rows = [
            {
                "timeStamp": "1000",
                "elapsed": "100",
                "label": "Service-A",
                "success": "true",
                "responseCode": "200",
                "responseMessage": "OK",
            },
            {
                "timeStamp": "1100",
                "elapsed": "200",
                "label": "Service-B",
                "success": "false",
                "responseCode": "500",
                "responseMessage": "Error",
            },
            {
                "timeStamp": "2000",
                "elapsed": "120",
                "label": "Service-A",
                "success": "true",
                "responseCode": "200",
                "responseMessage": "OK",
            },
        ]

        transactions = (
            ANALYZER.analyze_transactions(
                rows,
                origin_timestamp=1000,
            )
        )

        by_label = {
            tx["label"]: tx
            for tx in transactions
        }

        self.assertIn(
            "Service-A",
            by_label,
        )

        self.assertIn(
            "Service-B",
            by_label,
        )

        self.assertEqual(
            by_label[
                "Service-A"
            ]["time_series"][0]["samples"],
            1,
        )

        self.assertEqual(
            by_label[
                "Service-B"
            ]["time_series"][0][
                "error_rate_pct"
            ],
            100.0,
        )

    def test_shared_origin_preserves_execution_axis(self):
        rows = [
            {
                "timeStamp": "3000",
                "elapsed": "100",
                "label": "Late-Service",
                "success": "true",
                "responseCode": "200",
                "responseMessage": "OK",
            },
        ]

        series = ANALYZER.build_time_series(
            rows,
            bucket_seconds=1,
            origin_timestamp=1000,
        )

        self.assertEqual(
            series[0]["samples"],
            0,
        )

        self.assertEqual(
            series[2]["samples"],
            1,
        )


class FailureCausalityTests(unittest.TestCase):

    def test_transport_failure_is_primary(self):
        rows = [
            {
                "timeStamp": "1000",
                "elapsed": "100",
                "label": "Service-A",
                "threadName": "Thread-1",
                "success": "false",
                "responseCode": (
                    "Non HTTP response code: "
                    "org.apache.http."
                    "NoHttpResponseException"
                ),
                "responseMessage": (
                    "host failed to respond"
                ),
                "failureMessage": "",
            },
        ]

        result = (
            ANALYZER
            .build_failure_causality(
                rows
            )
        )

        self.assertEqual(
            result["summary"]["primary"],
            1,
        )

        self.assertEqual(
            result["events"][0][
                "classification"
            ],
            "PRIMARY",
        )

    def test_later_failure_same_thread_is_cascade(
        self,
    ):
        rows = [
            {
                "timeStamp": "1000",
                "elapsed": "100",
                "label": "Producer",
                "threadName": "Thread-1",
                "success": "false",
                "responseCode": (
                    "Non HTTP response code: "
                    "java.net.SocketException"
                ),
                "responseMessage": (
                    "Connection reset"
                ),
                "failureMessage": "",
            },
            {
                "timeStamp": "2000",
                "elapsed": "100",
                "label": "Consumer",
                "threadName": "Thread-1",
                "success": "false",
                "responseCode": "404",
                "responseMessage": (
                    "Not Found"
                ),
                "failureMessage": "",
            },
        ]

        result = (
            ANALYZER
            .build_failure_causality(
                rows
            )
        )

        self.assertEqual(
            result["summary"]["primary"],
            1,
        )

        self.assertEqual(
            result["summary"]["cascade"],
            1,
        )

        self.assertEqual(
            result["events"][1][
                "related_to"
            ]["label"],
            "Producer",
        )

    def test_different_thread_is_not_cascade(
        self,
    ):
        rows = [
            {
                "timeStamp": "1000",
                "elapsed": "100",
                "label": "Producer",
                "threadName": "Thread-1",
                "success": "false",
                "responseCode": (
                    "Non HTTP response code: "
                    "java.net.SocketException"
                ),
                "responseMessage": (
                    "Connection reset"
                ),
                "failureMessage": "",
            },
            {
                "timeStamp": "2000",
                "elapsed": "100",
                "label": "Other-Service",
                "threadName": "Thread-2",
                "success": "false",
                "responseCode": "500",
                "responseMessage": (
                    "Server Error"
                ),
                "failureMessage": "",
            },
        ]

        result = (
            ANALYZER
            .build_failure_causality(
                rows
            )
        )

        self.assertEqual(
            result["summary"][
                "primary"
            ],
            2,
        )

        self.assertEqual(
            result["summary"][
                "cascade"
            ],
            0,
        )
