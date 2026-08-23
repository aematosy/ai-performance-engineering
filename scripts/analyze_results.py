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