#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import threading
import time
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from pathlib import Path


class LocustMetrics:
    def __init__(
        self,
        results_root: Path,
        scenario: str,
        started_at: float,
    ) -> None:
        self.results_root = (
            results_root
            .expanduser()
            .resolve()
        )

        self.scenario = scenario
        self.started_at = started_at

        self.lock = threading.Lock()

        self.finished = False
        self.sampler_values: dict[tuple[str, str], dict[str, float]] = {}

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

    @property
    def execution_dir(
        self,
    ) -> Path:
        return (
            self.results_root
            / f"locust-{self.scenario}"
        )

    @property
    def history_file(
        self,
    ) -> Path:
        return (
            self.execution_dir
            / "locust_stats_history.csv"
        )

    def _history_is_current(
        self,
    ) -> bool:
        path = self.history_file

        if not path.exists():
            return False

        try:
            modified = (
                path.stat()
                .st_mtime
            )
        except OSError:
            return False

        return (
            modified
            >= self.started_at - 2
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
                pass

        return 0.0

    def _load_latest_rows(
        self,
    ) -> list[dict[str, str]]:
        path = self.history_file

        if not self._history_is_current():
            return []

        try:
            with path.open(
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
            return []

        if not rows:
            return []

        latest_timestamp = str(
            rows[-1].get(
                "Timestamp",
                "",
            )
        ).strip()

        if not latest_timestamp:
            return [rows[-1]]

        return [
            row
            for row in rows
            if str(
                row.get(
                    "Timestamp",
                    "",
                )
            ).strip() == latest_timestamp
        ]

    @staticmethod
    def _aggregated_row(
        rows: list[dict[str, str]],
    ) -> dict[str, str] | None:
        for row in reversed(rows):
            if str(
                row.get(
                    "Name",
                    "",
                )
            ).strip() in (
                "",
                "Aggregated",
            ):
                return row

        return rows[-1] if rows else None

    def _samplers_from_rows(
        self,
        rows: list[dict[str, str]],
    ) -> dict[tuple[str, str], dict[str, float]]:
        samplers: dict[tuple[str, str], dict[str, float]] = {}

        for row in rows:
            name = str(
                row.get(
                    "Name",
                    "",
                )
            ).strip()

            method = str(
                row.get(
                    "Type",
                    "",
                )
            ).strip()

            if not name or name == "Aggregated":
                continue

            samplers[(method, name)] = {
                "requests_per_second": self._number(
                    row,
                    "Requests/s",
                ),
                "failures_per_second": self._number(
                    row,
                    "Failures/s",
                ),
                "total_requests": self._number(
                    row,
                    "Total Request Count",
                ),
                "total_failures": self._number(
                    row,
                    "Total Failure Count",
                ),
            }

        return samplers

    def _reset_runtime_values(
        self,
    ) -> None:
        self.values.update(
            {
                "locust_metrics_up": 0.0,
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
        )

    def refresh(
        self,
    ) -> None:
        with self.lock:
            if self.finished:
                self._reset_runtime_values()
                self.sampler_values = {}
                return

        rows = self._load_latest_rows()
        row = self._aggregated_row(
            rows
        )

        with self.lock:
            if row is None:
                self._reset_runtime_values()
                self.sampler_values = {}
                return

            self.sampler_values = (
                self._samplers_from_rows(
                    rows
                )
            )

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

            self.values.update(
                {
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
            )

    def finish(
        self,
    ) -> None:
        with self.lock:
            self.finished = True
            self._reset_runtime_values()


    def render(
        self,
    ) -> bytes:
        self.refresh()

        with self.lock:
            values = dict(
                self.values
            )
            sampler_values = dict(
                self.sampler_values
            )

        lines = []

        for name, value in values.items():
            lines.append(
                f"# TYPE {name} gauge"
            )
            lines.append(
                f"{name} {value}"
            )


        if sampler_values:
            lines.append(
                "# TYPE locust_sampler_requests_per_second gauge"
            )
            for (method, name), metrics in sorted(
                sampler_values.items()
            ):
                escaped_method = method.replace(
                    "\\", "\\\\"
                ).replace(
                    '"', '\\"'
                )
                escaped_name = name.replace(
                    "\\", "\\\\"
                ).replace(
                    '"', '\\"'
                )
                labels = (
                    f'method="{escaped_method}",'
                    f'name="{escaped_name}"'
                )
                lines.append(
                    "locust_sampler_requests_per_second"
                    f"{{{labels}}} "
                    f"{metrics['requests_per_second']}"
                )

            lines.append(
                "# TYPE locust_sampler_failures_per_second gauge"
            )
            for (method, name), metrics in sorted(
                sampler_values.items()
            ):
                escaped_method = method.replace(
                    "\\", "\\\\"
                ).replace(
                    '"', '\\"'
                )
                escaped_name = name.replace(
                    "\\", "\\\\"
                ).replace(
                    '"', '\\"'
                )
                labels = (
                    f'method="{escaped_method}",'
                    f'name="{escaped_name}"'
                )
                lines.append(
                    "locust_sampler_failures_per_second"
                    f"{{{labels}}} "
                    f"{metrics['failures_per_second']}"
                )

        return (
            "\n".join(
                lines
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
        required=True,
    )

    parser.add_argument(
        "--scenario",
        required=True,
    )

    parser.add_argument(
        "--port",
        type=int,
        default=9271,
    )

    args = parser.parse_args()

    started_at = time.time()

    metrics = LocustMetrics(
        results_root=args.results_root,
        scenario=args.scenario,
        started_at=started_at,
    )

    class Handler(
        BaseHTTPRequestHandler
    ):
        def do_GET(
            self,
        ) -> None:
            if self.path not in (
                "/",
                "/metrics",
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
                "text/plain; version=0.0.4",
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

        def do_POST(
            self,
        ) -> None:
            if self.path != "/finish":
                self.send_response(
                    404
                )
                self.end_headers()
                return

            metrics.finish()

            body = b"OK\n"

            self.send_response(
                200
            )

            self.send_header(
                "Content-Type",
                "text/plain",
            )

            self.send_header(
                "Content-Length",
                str(
                    len(body)
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
        "Locust metrics exporter"
    )

    print(
        "Scenario:",
        args.scenario,
    )

    print(
        "Execution directory:",
        metrics.execution_dir,
    )

    print(
        "Metrics:",
        f"http://localhost:{args.port}/metrics",
    )

    server.serve_forever()

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
