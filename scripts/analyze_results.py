#!/usr/bin/env python3
"""
Analiza resultados JMeter en formato CSV/JTL y evalúa los SLA configurados.

Uso:
  python3 scripts/analyze_results.py \
    --input results/results.jtl \
    --sla config/sla.json \
    --output results/analysis.json
"""

import argparse
import csv
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path


REQUIRED_COLUMNS = {
    "timeStamp",
    "elapsed",
    "label",
    "success",
    "responseCode",
}


def percentile(sorted_values, percentile_value):
    if not sorted_values:
        return None

    if len(sorted_values) == 1:
        return float(sorted_values[0])

    position = (len(sorted_values) - 1) * percentile_value / 100
    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return float(sorted_values[lower])

    lower_weight = upper - position
    upper_weight = position - lower

    return (
        sorted_values[lower] * lower_weight
        + sorted_values[upper] * upper_weight
    )


def parse_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def load_rows(input_path):
    if not input_path.exists():
        raise FileNotFoundError("No existe el archivo: {}".format(input_path))

    with input_path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError("El JTL no contiene una cabecera CSV.")

        missing_columns = REQUIRED_COLUMNS.difference(reader.fieldnames)

        if missing_columns:
            raise ValueError(
                "Faltan columnas requeridas en el JTL: {}".format(
                    ", ".join(sorted(missing_columns))
                )
            )

        rows = list(reader)

    if not rows:
        raise ValueError(
            "El archivo '{}' no contiene muestras.".format(input_path)
        )

    return rows



def calculate_duration_and_throughput(rows):
    """
    Calculate observed duration and sample throughput for any
    arbitrary group of JMeter samples.

    This works for:
    - complete executions,
    - individual HTTP samplers,
    - transaction controllers,
    - imported JMX labels,
    - Postman-generated labels,
    - CLI-generated scenarios.
    """
    samples = []

    for row in rows:
        timestamp = parse_int(
            row.get("timeStamp")
        )
        elapsed = parse_int(
            row.get("elapsed")
        )

        if (
            timestamp is not None
            and elapsed is not None
        ):
            samples.append(
                (timestamp, elapsed)
            )

    if not samples:
        return None, None

    start_timestamp = min(
        timestamp
        for timestamp, _ in samples
    )

    end_timestamp = max(
        timestamp + elapsed
        for timestamp, elapsed in samples
    )

    duration_sec = max(
        (
            end_timestamp
            - start_timestamp
        ) / 1000.0,
        0.001,
    )

    throughput = (
        len(rows)
        / duration_sec
    )

    return (
        round(duration_sec, 3),
        round(throughput, 3),
    )


def response_time_metrics(rows):
    """
    Calculate latency statistics for an arbitrary sample group.
    """
    values = []

    for row in rows:
        elapsed = parse_int(
            row.get("elapsed")
        )

        if (
            elapsed is not None
            and elapsed >= 0
        ):
            values.append(elapsed)

    values.sort()

    if not values:
        return {
            "min": None,
            "avg": None,
            "p50": None,
            "p90": None,
            "p95": None,
            "p99": None,
            "max": None,
        }

    return {
        "min": values[0],
        "avg": round(
            statistics.mean(values),
            2,
        ),
        "p50": round(
            percentile(values, 50),
            2,
        ),
        "p90": round(
            percentile(values, 90),
            2,
        ),
        "p95": round(
            percentile(values, 95),
            2,
        ),
        "p99": round(
            percentile(values, 99),
            2,
        ),
        "max": values[-1],
    }



def build_time_series(
    rows,
    bucket_seconds=1,
    origin_timestamp=None,
):
    """
    Build generic time-series buckets for any JMeter sample group.

    The same function is used for:
    - the complete execution,
    - HTTP samplers,
    - business transactions,
    - imported JMX labels,
    - Postman requests,
    - CLI-generated labels.

    A shared origin can be supplied so every transaction uses the
    same X axis as the global execution.
    """
    valid = []

    for row in rows:
        timestamp = parse_int(
            row.get("timeStamp")
        )

        if timestamp is None:
            continue

        valid.append(
            (
                timestamp,
                row,
            )
        )

    if not valid:
        return []

    if origin_timestamp is None:
        origin_timestamp = min(
            timestamp
            for timestamp, _
            in valid
        )

    buckets = {}

    for timestamp, row in valid:
        bucket = max(
            0,
            (
                timestamp
                - origin_timestamp
            )
            // (
                bucket_seconds
                * 1000
            ),
        )

        if bucket not in buckets:
            buckets[bucket] = {
                "elapsed": [],
                "samples": 0,
                "errors": 0,
            }

        current = buckets[bucket]
        current["samples"] += 1

        elapsed = parse_int(
            row.get("elapsed")
        )

        if (
            elapsed is not None
            and elapsed >= 0
        ):
            current["elapsed"].append(
                elapsed
            )

        success = str(
            row.get("success", "")
        ).strip().lower()

        if success != "true":
            current["errors"] += 1

    max_bucket = max(
        buckets.keys()
    )

    result = []

    for bucket in range(
        max_bucket + 1
    ):
        current = buckets.get(
            bucket,
            {
                "elapsed": [],
                "samples": 0,
                "errors": 0,
            },
        )

        samples = current["samples"]
        elapsed_values = (
            current["elapsed"]
        )

        average = (
            sum(elapsed_values)
            / len(elapsed_values)
            if elapsed_values
            else None
        )

        error_rate = (
            current["errors"]
            / samples
            * 100
            if samples
            else 0.0
        )

        result.append(
            {
                "second": (
                    bucket
                    * bucket_seconds
                ),
                "samples": samples,
                "avg_response_ms": (
                    round(
                        average,
                        2,
                    )
                    if average is not None
                    else None
                ),
                "throughput_req_per_sec": round(
                    samples
                    / float(
                        bucket_seconds
                    ),
                    3,
                ),
                "error_rate_pct": round(
                    error_rate,
                    3,
                ),
            }
        )

    return result



def analyze_transaction_group(
    label,
    rows,
    origin_timestamp=None,
):
    """
    Analyze one JMeter label without assuming anything about
    the application or protocol semantics.

    `label` can represent:
    - an endpoint,
    - a service,
    - a business transaction,
    - a Postman request,
    - a JMeter Transaction Controller.
    """
    total = len(rows)

    failed_rows = [
        row
        for row in rows
        if str(
            row.get("success", "")
        ).strip().lower()
        != "true"
    ]

    error_count = len(failed_rows)
    success_count = (
        total - error_count
    )

    error_rate = (
        error_count
        / total
        * 100
        if total
        else 0.0
    )

    success_rate = (
        100.0 - error_rate
    )

    duration_sec, throughput = (
        calculate_duration_and_throughput(
            rows
        )
    )

    response_codes = Counter(
        str(
            row.get("responseCode")
            or "unknown"
        )
        for row in rows
    )

    error_codes = Counter(
        str(
            row.get("responseCode")
            or "unknown"
        )
        for row in failed_rows
    )

    failure_messages = Counter()

    for row in failed_rows:
        code = str(
            row.get("responseCode")
            or "unknown"
        )

        message = str(
            row.get("responseMessage")
            or ""
        ).strip()

        if message:
            key = (
                f"{code} | {message}"
            )
        else:
            key = code

        failure_messages[key] += 1

    return {
        "label": str(label),
        "samples": total,
        "success_count": success_count,
        "error_count": error_count,
        "success_rate_pct": round(
            success_rate,
            3,
        ),
        "error_rate_pct": round(
            error_rate,
            3,
        ),
        "duration_sec": duration_sec,
        "throughput_req_per_sec": throughput,
        "response_time_ms": (
            response_time_metrics(
                rows
            )
        ),
        "response_codes": dict(
            response_codes
        ),
        "error_response_codes": dict(
            error_codes
        ),
        "failure_messages": dict(
            failure_messages
        ),
        "time_series": build_time_series(
            rows,
            bucket_seconds=1,
            origin_timestamp=origin_timestamp,
        ),
        "status": (
            "PASS"
            if error_count == 0
            else "FAIL"
        ),
    }


def analyze_transactions(
    rows,
    origin_timestamp=None,
):
    """
    Group all samples by JMeter label while preserving their
    first-seen execution order.
    """
    grouped = {}

    for row in rows:
        label = str(
            row.get("label")
            or "unknown"
        )

        if label not in grouped:
            grouped[label] = []

        grouped[label].append(row)

    return [
        analyze_transaction_group(
            label,
            samples,
            origin_timestamp=origin_timestamp,
        )
        for label, samples
        in grouped.items()
    ]


def build_error_details(
    transactions,
):
    """
    Produce a compact failure-oriented view suitable for
    reports and intelligence engines.
    """
    result = []

    for transaction in transactions:
        if (
            transaction[
                "error_count"
            ]
            <= 0
        ):
            continue

        result.append(
            {
                "label": (
                    transaction["label"]
                ),
                "samples": (
                    transaction["samples"]
                ),
                "error_count": (
                    transaction[
                        "error_count"
                    ]
                ),
                "error_rate_pct": (
                    transaction[
                        "error_rate_pct"
                    ]
                ),
                "error_response_codes": (
                    transaction[
                        "error_response_codes"
                    ]
                ),
                "failure_messages": (
                    transaction[
                        "failure_messages"
                    ]
                ),
            }
        )

    return result




def build_failure_causality(
    rows,
    cascade_window_ms=15000,
):
    """
    Conservative generic failure-causality heuristic.

    Rules:

    - Failures are evaluated independently per JMeter thread.
    - A failure starts a PRIMARY incident when no active primary
      exists for that thread.
    - Later failures in the same thread and temporal window are
      classified as CASCADE.
    - A successful sample after failures closes the active incident.
    - Transport failures always start a new PRIMARY incident.
    - Incidents never cross thread boundaries.

    This reports likely execution causality, not guaranteed
    application root cause.
    """

    transport_markers = (
        "non http response code",
        "nohttpresponseexception",
        "socketexception",
        "connection reset",
        "connection refused",
        "failed to respond",
        "connectexception",
        "unknownhostexception",
        "ssl",
        "timed out",
        "timeout",
        "broken pipe",
    )

    events = []
    summary = {
        "primary": 0,
        "cascade": 0,
        "independent": 0,
    }

    state = {}

    for index, row in enumerate(rows):
        thread = str(
            row.get("threadName")
            or "<UNKNOWN>"
        )

        timestamp = parse_int(
            row.get("timeStamp")
        )

        success = (
            str(
                row.get(
                    "success",
                    "",
                )
            )
            .strip()
            .lower()
            == "true"
        )

        current = state.setdefault(
            thread,
            {
                "primary": None,
            },
        )

        if success:
            # A successful sample after an incident demonstrates
            # recovery and closes the previous causal chain.
            if current["primary"] is not None:
                current["primary"] = None

            continue

        label = str(
            row.get("label")
            or "unknown"
        )

        code = str(
            row.get("responseCode")
            or ""
        )

        response_message = str(
            row.get("responseMessage")
            or ""
        )

        failure_message = str(
            row.get("failureMessage")
            or ""
        )

        combined = (
            code
            + " "
            + response_message
            + " "
            + failure_message
        ).lower()

        transport_failure = (
            code.lower().startswith(
                "non http response code"
            )
            or any(
                marker in combined
                for marker in transport_markers
            )
        )

        primary = current["primary"]

        within_window = False

        if primary is not None:
            primary_timestamp = (
                primary.get("timestamp")
            )

            if (
                timestamp is not None
                and primary_timestamp is not None
            ):
                within_window = (
                    0
                    <= (
                        timestamp
                        - primary_timestamp
                    )
                    <= cascade_window_ms
                )
            else:
                within_window = True

        if (
            transport_failure
            or primary is None
            or not within_window
        ):
            classification = "PRIMARY"
            related_to = None

            primary = {
                "index": index,
                "timestamp": timestamp,
                "label": label,
                "response_code": code,
            }

            current["primary"] = primary

        else:
            classification = "CASCADE"

            related_to = {
                "label": primary["label"],
                "response_code": (
                    primary["response_code"]
                ),
            }

        summary[
            classification.lower()
        ] += 1

        events.append(
            {
                "classification": classification,
                "thread": thread,
                "label": label,
                "response_code": code,
                "response_message": (
                    response_message
                ),
                "related_to": related_to,
            }
        )

    return {
        "method": (
            "THREAD_EXECUTION_CHAIN_HEURISTIC"
        ),
        "cascade_window_ms": (
            cascade_window_ms
        ),
        "summary": summary,
        "events": events,
    }


def analyze(input_path):
    rows = load_rows(input_path)

    valid_samples = []
    response_times = []

    for row in rows:
        timestamp = parse_int(row.get("timeStamp"))
        elapsed = parse_int(row.get("elapsed"))

        if elapsed is not None and elapsed >= 0:
            response_times.append(elapsed)

        if timestamp is not None and elapsed is not None:
            valid_samples.append((timestamp, elapsed))

    response_times.sort()

    total_requests = len(rows)

    failed_rows = [
        row
        for row in rows
        if str(row.get("success", "")).strip().lower() != "true"
    ]

    error_count = len(failed_rows)
    success_count = total_requests - error_count
    error_rate = error_count / total_requests * 100

    duration_sec = None
    throughput = None

    if valid_samples:
        start_timestamp = min(timestamp for timestamp, _ in valid_samples)
        end_timestamp = max(
            timestamp + elapsed
            for timestamp, elapsed in valid_samples
        )

        duration_sec = max(
            (end_timestamp - start_timestamp) / 1000.0,
            0.001,
        )

        throughput = total_requests / duration_sec

    errors_by_code = Counter(
        row.get("responseCode") or "unknown"
        for row in failed_rows
    )

    errors_by_label = Counter(
        row.get("label") or "unknown"
        for row in failed_rows
    )

    origin_timestamp = (
        min(
            timestamp
            for timestamp, _
            in valid_samples
        )
        if valid_samples
        else None
    )

    transactions = (
        analyze_transactions(
            rows,
            origin_timestamp=origin_timestamp,
        )
    )

    global_time_series = (
        build_time_series(
            rows,
            bucket_seconds=1,
            origin_timestamp=origin_timestamp,
        )
    )

    error_details = (
        build_error_details(
            transactions
        )
    )

    failure_causality = (
        build_failure_causality(
            rows
        )
    )

    return {
        "total_requests": total_requests,
        "success_count": success_count,
        "error_count": error_count,
        "success_rate_pct": round(100 - error_rate, 3),
        "error_rate_pct": round(error_rate, 3),
        "duration_sec": (
            round(duration_sec, 3)
            if duration_sec is not None
            else None
        ),
        "throughput_req_per_sec": (
            round(throughput, 3)
            if throughput is not None
            else None
        ),
        "response_time_ms": {
            "min": response_times[0] if response_times else None,
            "max": response_times[-1] if response_times else None,
            "avg": (
                round(statistics.mean(response_times), 2)
                if response_times
                else None
            ),
            "p50": (
                round(percentile(response_times, 50), 2)
                if response_times
                else None
            ),
            "p90": (
                round(percentile(response_times, 90), 2)
                if response_times
                else None
            ),
            "p95": (
                round(percentile(response_times, 95), 2)
                if response_times
                else None
            ),
            "p99": (
                round(percentile(response_times, 99), 2)
                if response_times
                else None
            ),
        },
        "errors_by_response_code": dict(errors_by_code),
        "errors_by_label": dict(errors_by_label),
        "transaction_count": len(transactions),
        "transactions": transactions,
        "time_series": global_time_series,
        "error_details": error_details,
        "failure_causality": failure_causality,
    }


def load_sla(path):
    with path.open(encoding="utf-8") as file:
        config = json.load(file)

    return {
        "error_rate_threshold_pct": float(
            config.get("error_rate_threshold_pct", 1.0)
        ),
        "p95_threshold_ms": float(
            config.get("p95_threshold_ms", 1000)
        ),
        "p99_threshold_ms": float(
            config.get("p99_threshold_ms", 2000)
        ),
        "min_throughput_req_per_sec": float(
            config.get("min_throughput_req_per_sec", 0)
        ),
    }


def evaluate_sla(metrics, sla):
    checks = []

    checks.append({
        "check": "error_rate",
        "threshold": "<= {} %".format(
            sla["error_rate_threshold_pct"]
        ),
        "actual": "{} %".format(
            metrics["error_rate_pct"]
        ),
        "passed": (
            metrics["error_rate_pct"]
            <= sla["error_rate_threshold_pct"]
        ),
    })

    p95 = metrics["response_time_ms"]["p95"]

    checks.append({
        "check": "p95_response_time",
        "threshold": "<= {} ms".format(
            sla["p95_threshold_ms"]
        ),
        "actual": (
            "{} ms".format(p95)
            if p95 is not None
            else "N/A"
        ),
        "passed": (
            p95 is not None
            and p95 <= sla["p95_threshold_ms"]
        ),
    })

    p99 = metrics["response_time_ms"]["p99"]

    checks.append({
        "check": "p99_response_time",
        "threshold": "<= {} ms".format(
            sla["p99_threshold_ms"]
        ),
        "actual": (
            "{} ms".format(p99)
            if p99 is not None
            else "N/A"
        ),
        "passed": (
            p99 is not None
            and p99 <= sla["p99_threshold_ms"]
        ),
    })

    minimum_throughput = sla["min_throughput_req_per_sec"]

    if minimum_throughput > 0:
        throughput = metrics["throughput_req_per_sec"]

        checks.append({
            "check": "minimum_throughput",
            "threshold": ">= {} req/s".format(
                minimum_throughput
            ),
            "actual": (
                "{} req/s".format(throughput)
                if throughput is not None
                else "N/A"
            ),
            "passed": (
                throughput is not None
                and throughput >= minimum_throughput
            ),
        })

    overall_pass = all(check["passed"] for check in checks)

    return checks, overall_pass


def main():
    parser = argparse.ArgumentParser(
        description="Analiza resultados JMeter y evalúa SLA."
    )

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Archivo JTL de entrada.",
    )

    parser.add_argument(
        "--output",
        default=Path("results/analysis.json"),
        type=Path,
        help="Archivo JSON de salida.",
    )

    parser.add_argument(
        "--sla",
        default=Path("config/sla.json"),
        type=Path,
        help="Archivo JSON con los SLA.",
    )

    args = parser.parse_args()

    try:
        metrics = analyze(args.input)
        sla = load_sla(args.sla)
        checks, overall_pass = evaluate_sla(metrics, sla)

    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print("ERROR: {}".format(error), file=sys.stderr)
        return 2

    result = {
        "source": str(args.input),
        "sla": sla,
        "metrics": metrics,
        "sla_checks": checks,
        "verdict": "PASS" if overall_pass else "FAIL",
    }

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("")
    print("Veredicto: {}".format(result["verdict"]))
    print(
        "Requests: {} | Éxito: {}% | Errores: {}%".format(
            metrics["total_requests"],
            metrics["success_rate_pct"],
            metrics["error_rate_pct"],
        )
    )

    print(
        "Throughput: {} req/s | p95: {} ms | p99: {} ms".format(
            metrics["throughput_req_per_sec"],
            metrics["response_time_ms"]["p95"],
            metrics["response_time_ms"]["p99"],
        )
    )

    for check in checks:
        status = "OK" if check["passed"] else "FAIL"

        print(
            "[{}] {}: {} | SLA {}".format(
                status,
                check["check"],
                check["actual"],
                check["threshold"],
            )
        )

    print("Resultado guardado en: {}".format(args.output))

    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())