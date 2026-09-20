#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import threading
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from pathlib import Path


class LocustMetrics:
    def __init__(
        self,
        results_root: Path,
    ) -> None:
        self.results_root = (
            results_root
            .expanduser()
            .resolve()
        )

        self.lock = threading.Lock()

        self.values = {
            "locust_metrics_up": 1.0,
            "locust_active_users": 0.0,
            "locust_requests_per_second": 0.0,
            "locust_failures_per_second": 0.0,
            "locust_total_requests": 0.0,
            "locust_total_failures": 0.0,
            "locust_error_rate_pct": 0.0,
            "locust_response_time_avg_ms": 0.0,
            "locust_response_time_p50_ms": 0.0,
            "locust_response_time_p95_ms": 0.0,
            "locust_response_time_p99_ms": 0.0,
            "locust_response_time_max_ms": 0.0,
        }

    def _latest_history(
        self,
    ) -> Path | None:
        if not self.results_root.exists():
            return None

        candidates = list(
            self.results_root.rglob(
                "*_stats_history.csv"
            )
        )

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda item: (
                item.stat().st_mtime
            ),
        )

    @staticmethod
    def _number(
        row: dict[str, str],
        *keys: str,
    ) -> float:
        for key in keys:
            value = row.get(
                key
            )

            if value in (
                None,
                "",
            ):
                continue

            try:
                return float(
                    value
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

        return 0.0

    def _load_latest_row(
        self,
    ) -> dict[str, str] | None:
        history = (
            self._latest_history()
        )

        if history is None:
            return None

        try:
            with history.open(
                "r",
                encoding="utf-8",
                newline="",
            ) as stream:
                rows = list(
                    csv.DictReader(
                        stream
                    )
                )
        except (
            OSError,
            csv.Error,
        ):
            return None

        if not rows:
            return None

        aggregated = [
            row
            for row in rows
            if str(
                row.get(
                    "Name",
                    ""
                )
            ).strip()
            in (
                "",
                "Aggregated",
            )
        ]

        if aggregated:
            return aggregated[-1]

        return rows[-1]

    def refresh(
        self,
    ) -> None:
        row = (
            self._load_latest_row()
        )

        if row is None:
            return

        requests = self._number(
            row,
            "Total Request Count",
        )

        failures = self._number(
            row,
            "Total Failure Count",
        )

        error_rate = (
            failures
            / requests
            * 100.0
            if requests > 0
            else 0.0
        )

        values = {
            "locust_metrics_up": 1.0,

            "locust_active_users":
                self._number(
                    row,
                    "User Count",
                ),

            "locust_requests_per_second":
                self._number(
                    row,
                    "Requests/s",
                ),

            "locust_failures_per_second":
                self._number(
                    row,
                    "Failures/s",
                ),

            "locust_total_requests":
                requests,

            "locust_total_failures":
                failures,

            "locust_error_rate_pct":
                error_rate,

            "locust_response_time_avg_ms":
                self._number(
                    row,
                    "Total Average Response Time",
                    "Average Response Time",
                ),

            "locust_response_time_p50_ms":
                self._number(
                    row,
                    "50%",
                ),

            "locust_response_time_p95_ms":
                self._number(
                    row,
                    "95%",
                ),

            "locust_response_time_p99_ms":
                self._number(
                    row,
                    "99%",
                ),

            "locust_response_time_max_ms":
                self._number(
                    row,
                    "Total Max Response Time",
                    "Max Response Time",
                ),
        }

        with self.lock:
            self.values.update(
                values
            )

    def render(
        self,
    ) -> bytes:
        self.refresh()

        with self.lock:
            values = dict(
                self.values
            )

        output = []

        for name, value in values.items():
            output.append(
                f"# TYPE {name} gauge"
            )
            output.append(
                f"{name} {value}"
            )

        return (
            "\n".join(
                output
            )
            + "\n"
        ).encode(
            "utf-8"
        )


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--results-root",
        type=Path,
        default=Path(
            "results"
        ),
    )

    parser.add_argument(
        "--port",
        type=int,
        default=9271,
    )

    args = parser.parse_args()

    metrics = LocustMetrics(
        args.results_root
    )

    class Handler(
        BaseHTTPRequestHandler
    ):
        def do_GET(
            self,
        ) -> None:
            if self.path not in (
                "/metrics",
                "/",
            ):
                self.send_response(
                    404
                )
                self.end_headers()
                return

            body = metrics.render()

            self.send_response(
                200
            )
            self.send_header(
                "Content-Type",
                "text/plain; "
                "version=0.0.4; "
                "charset=utf-8",
            )
            self.send_header(
                "Content-Length",
                str(
                    len(
                        body
                    )
                ),
            )
            self.end_headers()
            self.wfile.write(
                body
            )

        def log_message(
            self,
            format: str,
            *args,
        ) -> None:
            return

    server = ThreadingHTTPServer(
        (
            "0.0.0.0",
            args.port,
        ),
        Handler,
    )

    print(
        "Locust Prometheus metrics available at "
        f"http://localhost:{args.port}/metrics",
        flush=True,
    )

    server.serve_forever()

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
