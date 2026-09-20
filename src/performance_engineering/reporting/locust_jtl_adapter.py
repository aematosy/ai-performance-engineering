from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


JTL_COLUMNS = [
    "timeStamp",
    "elapsed",
    "label",
    "responseCode",
    "responseMessage",
    "threadName",
    "dataType",
    "success",
    "failureMessage",
    "bytes",
    "sentBytes",
    "grpThreads",
    "allThreads",
    "URL",
    "Latency",
    "IdleTime",
    "Connect",
]


def _int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def convert_history(
    history_path: Path,
    output_path: Path,
) -> Path:
    """
    Convert Locust cumulative history into a JTL-compatible
    sample stream used only by the common report charts.

    Locust history may contain only Aggregated rows.
    We therefore calculate request/failure deltas between
    consecutive cumulative snapshots.
    """

    if not history_path.is_file():
        raise FileNotFoundError(
            f"Locust history not found: {history_path}"
        )

    with history_path.open(
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        rows = list(csv.DictReader(handle))

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    previous_requests = 0
    previous_failures = 0

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=JTL_COLUMNS,
        )
        writer.writeheader()

        for row in rows:
            # Current Locust export contains Aggregated rows.
            if row.get("Name") != "Aggregated":
                continue

            total_requests = _int(
                row.get("Total Request Count")
            )
            total_failures = _int(
                row.get("Total Failure Count")
            )

            delta_requests = max(
                total_requests - previous_requests,
                0,
            )
            delta_failures = max(
                total_failures - previous_failures,
                0,
            )

            previous_requests = total_requests
            previous_failures = total_failures

            if delta_requests == 0:
                continue

            delta_failures = min(
                delta_failures,
                delta_requests,
            )

            delta_success = (
                delta_requests
                - delta_failures
            )

            timestamp_ms = int(
                _float(row.get("Timestamp")) * 1000
            )

            elapsed = max(
                int(
                    _float(
                        row.get(
                            "Total Average Response Time"
                        )
                    )
                ),
                0,
            )

            users = _int(
                row.get("User Count")
            )

            base = {
                "timeStamp": timestamp_ms,
                "elapsed": elapsed,
                "label": "All Transactions",
                "threadName": "Locust",
                "dataType": "text",
                "bytes": 0,
                "sentBytes": 0,
                "grpThreads": users,
                "allThreads": users,
                "URL": "",
                "Latency": elapsed,
                "IdleTime": 0,
                "Connect": 0,
            }

            for _ in range(delta_success):
                writer.writerow(
                    {
                        **base,
                        "responseCode": "2xx",
                        "responseMessage": "Success",
                        "success": "true",
                        "failureMessage": "",
                    }
                )

            for _ in range(delta_failures):
                writer.writerow(
                    {
                        **base,
                        "responseCode": "ERROR",
                        "responseMessage": "Locust failure",
                        "success": "false",
                        "failureMessage": "Locust failure",
                    }
                )

    return output_path


def convert_locust_history(
    *,
    history_path: Path,
    output_path: Path,
) -> Path:
    return convert_history(
        history_path,
        output_path,
    )


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--history",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    result = convert_history(
        args.history,
        args.output,
    )

    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
