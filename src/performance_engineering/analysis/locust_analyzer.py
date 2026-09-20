from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def _float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def _int(value: str | None, default: int = 0) -> int:
    try:
        return int(float(value or default))
    except (TypeError, ValueError):
        return default


def _load_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Locust stats file not found: {path}")

    with path.open(
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        return list(csv.DictReader(handle))


def _find_aggregate(
    rows: list[dict[str, str]],
) -> dict[str, str]:
    for row in rows:
        if row.get("Name") == "Aggregated":
            return row

    raise ValueError(
        "Locust stats CSV does not contain Aggregated row."
    )


def _load_failures(
    path: Path,
) -> list[dict[str, Any]]:
    if not path.is_file():
        return []

    result = []

    with path.open(
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        for row in csv.DictReader(handle):
            result.append(
                {
                    "method": row.get("Method"),
                    "name": row.get("Name"),
                    "error": row.get("Error"),
                    "occurrences": _int(
                        row.get("Occurrences")
                    ),
                }
            )

    return result


def analyze_locust(
    *,
    stats_path: Path,
    failures_path: Path | None,
    sla_path: Path,
) -> dict[str, Any]:
    rows = _load_rows(stats_path)
    aggregate = _find_aggregate(rows)

    with sla_path.open(
        encoding="utf-8"
    ) as handle:
        sla = json.load(handle)

    total = _int(
        aggregate.get("Request Count")
    )

    failures = _int(
        aggregate.get("Failure Count")
    )

    successes = max(
        total - failures,
        0,
    )

    error_rate = (
        failures / total * 100
        if total
        else 0.0
    )

    p50 = _float(
        aggregate.get("50%")
    )
    p90 = _float(
        aggregate.get("90%")
    )
    p95 = _float(
        aggregate.get("95%")
    )
    p99 = _float(
        aggregate.get("99%")
    )

    minimum = _float(
        aggregate.get("Min Response Time")
    )
    maximum = _float(
        aggregate.get("Max Response Time")
    )
    average = _float(
        aggregate.get("Average Response Time")
    )
    throughput = _float(
        aggregate.get("Requests/s")
    )

    error_threshold = float(
        sla.get(
            "error_rate_threshold_pct",
            1.0,
        )
    )

    p95_threshold = float(
        sla.get(
            "p95_threshold_ms",
            1000,
        )
    )

    p99_threshold = float(
        sla.get(
            "p99_threshold_ms",
            2000,
        )
    )

    min_throughput = float(
        sla.get(
            "min_throughput_req_per_sec",
            0,
        )
    )

    checks = [
        {
            "check": "error_rate",
            "threshold": f"<= {error_threshold} %",
            "actual": f"{round(error_rate, 3)} %",
            "passed": error_rate <= error_threshold,
        },
        {
            "check": "p95_response_time",
            "threshold": f"<= {p95_threshold} ms",
            "actual": f"{round(p95, 2)} ms",
            "passed": p95 <= p95_threshold,
        },
        {
            "check": "p99_response_time",
            "threshold": f"<= {p99_threshold} ms",
            "actual": f"{round(p99, 2)} ms",
            "passed": p99 <= p99_threshold,
        },
        {
            "check": "minimum_throughput",
            "threshold": f">= {min_throughput} req/s",
            "actual": f"{round(throughput, 3)} req/s",
            "passed": throughput >= min_throughput,
        },
    ]

    transactions = []

    for row in rows:
        name = row.get("Name")

        if not name or name == "Aggregated":
            continue

        request_count = _int(
            row.get("Request Count")
        )

        failure_count = _int(
            row.get("Failure Count")
        )

        transactions.append(
            {
                "label": name,
                "method": row.get("Type"),
                "total_requests": request_count,
                "error_count": failure_count,
                "success_count": max(
                    request_count - failure_count,
                    0,
                ),
                "error_rate_pct": (
                    round(
                        failure_count
                        / request_count
                        * 100,
                        3,
                    )
                    if request_count
                    else 0.0
                ),
                "throughput_req_per_sec": _float(
                    row.get("Requests/s")
                ),
                "response_time_ms": {
                    "min": _float(
                        row.get("Min Response Time")
                    ),
                    "max": _float(
                        row.get("Max Response Time")
                    ),
                    "avg": _float(
                        row.get("Average Response Time")
                    ),
                    "p50": _float(
                        row.get("50%")
                    ),
                    "p90": _float(
                        row.get("90%")
                    ),
                    "p95": _float(
                        row.get("95%")
                    ),
                    "p99": _float(
                        row.get("99%")
                    ),
                },
            }
        )

    failure_details = _load_failures(
        failures_path
    ) if failures_path else []

    metrics = {
        "engine": "locust",
        "total_requests": total,
        "success_count": successes,
        "error_count": failures,
        "success_rate_pct": round(
            100 - error_rate,
            3,
        ),
        "error_rate_pct": round(
            error_rate,
            3,
        ),
        "duration_sec": None,
        "throughput_req_per_sec": round(
            throughput,
            3,
        ),
        "response_time_ms": {
            "min": minimum,
            "max": maximum,
            "avg": round(
                average,
                2,
            ),
            "p50": p50,
            "p90": p90,
            "p95": p95,
            "p99": p99,
        },
        "errors_by_response_code": {},
        "errors_by_label": {
            item["name"]: item["occurrences"]
            for item in failure_details
            if item.get("name")
        },
        "transaction_count": len(
            transactions
        ),
        "transactions": transactions,
        "time_series": [],
        "error_details": failure_details,
    }

    overall_pass = all(
        item["passed"]
        for item in checks
    )

    return {
        "source": str(stats_path),
        "engine": "locust",
        "sla": {
            "error_rate_threshold_pct":
                error_threshold,
            "p95_threshold_ms":
                p95_threshold,
            "p99_threshold_ms":
                p99_threshold,
            "min_throughput_req_per_sec":
                min_throughput,
        },
        "metrics": metrics,
        "sla_checks": checks,
        "verdict": (
            "PASS"
            if overall_pass
            else "FAIL"
        ),
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Normalize Locust CSV results "
            "into the platform analysis contract."
        )
    )

    parser.add_argument(
        "--stats",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--failures",
        type=Path,
    )

    parser.add_argument(
        "--sla",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    analysis = analyze_locust(
        stats_path=args.stats,
        failures_path=args.failures,
        sla_path=args.sla,
    )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        json.dumps(
            analysis,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    metrics = analysis["metrics"]

    print("=" * 70)
    print("LOCUST ANALYSIS")
    print("=" * 70)
    print("Verdict    :", analysis["verdict"])
    print("Requests   :", metrics["total_requests"])
    print("Success    :", metrics["success_rate_pct"], "%")
    print("Errors     :", metrics["error_rate_pct"], "%")
    print(
        "Throughput :",
        metrics["throughput_req_per_sec"],
        "req/s",
    )
    print(
        "p95        :",
        metrics["response_time_ms"]["p95"],
        "ms",
    )
    print(
        "p99        :",
        metrics["response_time_ms"]["p99"],
        "ms",
    )
    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def write_analysis(
    *,
    stats_path: Path,
    failures_path: Path | None,
    sla_path: Path,
    output_path: Path,
):
    """Persist Locust analysis using the common platform contract."""

    result = analyze_locust(
        stats_path=stats_path,
        failures_path=failures_path,
        sla_path=sla_path,
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return result
