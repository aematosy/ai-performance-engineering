from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from performance_engineering.analysis.locust_analyzer import (
    write_analysis,
)
from performance_engineering.reporting.locust_jtl_adapter import (
    convert_locust_history,
)


ROOT = Path(__file__).resolve().parents[3]


def newest_locust_results(
    results_root: Path,
) -> Path:
    candidates = [
        path
        for path in results_root.iterdir()
        if path.is_dir()
        and (path / "locust_stats.csv").is_file()
    ]

    if not candidates:
        raise FileNotFoundError(
            "No Locust results were found."
        )

    return max(
        candidates,
        key=lambda path: path.stat().st_mtime,
    )


def _response_code_from_error(
    error: str,
) -> str | None:
    match = re.search(
        r"received\s+(\d{3})",
        error or "",
    )

    return (
        match.group(1)
        if match
        else None
    )


def _build_locust_time_series(
    history_path: Path,
) -> list[dict[str, Any]]:
    if not history_path.is_file():
        return []

    with history_path.open(
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        rows = list(csv.DictReader(handle))

    aggregated = [
        row
        for row in rows
        if row.get("Name") == "Aggregated"
    ]

    if not aggregated:
        return []

    origin = None
    previous_requests = 0
    previous_failures = 0
    result = []

    for row in aggregated:
        try:
            timestamp = int(
                float(row.get("Timestamp") or 0)
            )
        except (TypeError, ValueError):
            continue

        if origin is None:
            origin = timestamp

        total_requests = int(
            float(
                row.get(
                    "Total Request Count"
                )
                or 0
            )
        )

        total_failures = int(
            float(
                row.get(
                    "Total Failure Count"
                )
                or 0
            )
        )

        delta_requests = max(
            total_requests
            - previous_requests,
            0,
        )

        delta_failures = max(
            total_failures
            - previous_failures,
            0,
        )

        previous_requests = total_requests
        previous_failures = total_failures

        average = row.get(
            "Total Average Response Time"
        )

        try:
            average_value = round(
                float(average),
                2,
            )
        except (TypeError, ValueError):
            average_value = None

        requests_per_sec = row.get(
            "Requests/s"
        )

        try:
            throughput = round(
                float(requests_per_sec),
                3,
            )
        except (TypeError, ValueError):
            throughput = float(
                delta_requests
            )

        error_rate = (
            delta_failures
            / delta_requests
            * 100.0
            if delta_requests
            else 0.0
        )

        result.append(
            {
                "second": (
                    timestamp - origin
                ),
                "samples": delta_requests,
                "avg_response_ms":
                    average_value,
                "throughput_req_per_sec":
                    throughput,
                "error_rate_pct": round(
                    error_rate,
                    3,
                ),
            }
        )

    return result


def _normalize_analysis_contract(
    analysis: dict[str, Any],
    history_path: Path,
) -> dict[str, Any]:
    metrics = analysis["metrics"]

    time_series = (
        _build_locust_time_series(
            history_path
        )
    )

    metrics["time_series"] = (
        time_series
    )

    failures_by_transaction = {}
    global_error_codes = {}

    for detail in metrics.get(
        "error_details",
        [],
    ):
        name = str(
            detail.get("name")
            or "unknown"
        )

        failures_by_transaction.setdefault(
            name,
            [],
        ).append(detail)

        code = _response_code_from_error(
            str(
                detail.get("error")
                or ""
            )
        )

        if code:
            global_error_codes[code] = (
                global_error_codes.get(
                    code,
                    0,
                )
                + int(
                    detail.get(
                        "occurrences",
                        0,
                    )
                )
            )

    metrics[
        "errors_by_response_code"
    ] = global_error_codes

    common_error_details = []

    transactions = metrics.get(
        "transactions",
        [],
    )

    for tx in transactions:
        label = str(
            tx.get("label")
            or "unknown"
        )

        samples = int(
            tx.get(
                "total_requests",
                tx.get(
                    "samples",
                    0,
                ),
            )
        )

        success_count = int(
            tx.get(
                "success_count",
                0,
            )
        )

        error_count = int(
            tx.get(
                "error_count",
                0,
            )
        )

        tx["samples"] = samples

        tx["success_rate_pct"] = (
            round(
                success_count
                / samples
                * 100.0,
                3,
            )
            if samples
            else 0.0
        )

        response_codes = {}

        if success_count:
            response_codes[
                "2xx"
            ] = success_count

        error_codes = {}
        failure_messages = {}

        for detail in (
            failures_by_transaction.get(
                label,
                [],
            )
        ):
            occurrences = int(
                detail.get(
                    "occurrences",
                    0,
                )
            )

            message = str(
                detail.get("error")
                or "Locust failure"
            )

            code = (
                _response_code_from_error(
                    message
                )
            )

            if code:
                error_codes[code] = (
                    error_codes.get(
                        code,
                        0,
                    )
                    + occurrences
                )

                response_codes[code] = (
                    response_codes.get(
                        code,
                        0,
                    )
                    + occurrences
                )

            failure_messages[
                message
            ] = (
                failure_messages.get(
                    message,
                    0,
                )
                + occurrences
            )

        tx["response_codes"] = (
            response_codes
        )

        tx[
            "error_response_codes"
        ] = error_codes

        tx[
            "failure_messages"
        ] = failure_messages

        tx["time_series"] = (
            time_series
        )

        tx["status"] = (
            "PASS"
            if error_count == 0
            else "FAIL"
        )

        if error_count > 0:
            common_error_details.append(
                {
                    "label": label,
                    "samples": samples,
                    "error_count":
                        error_count,
                    "error_rate_pct":
                        tx.get(
                            "error_rate_pct",
                            0.0,
                        ),
                    "error_response_codes":
                        error_codes,
                    "failure_messages":
                        failure_messages,
                }
            )

    metrics["error_details"] = (
        common_error_details
    )

    return analysis

def _derive_identity(
    results: Path,
) -> tuple[str, str]:
    metadata_path = (
        results
        / "metadata.json"
    )

    if metadata_path.is_file():
        metadata = json.loads(
            metadata_path.read_text(
                encoding="utf-8"
            )
        )

        scenario = str(
            metadata.get(
                "scenario"
            )
            or results.name
        )

        target = str(
            metadata.get(
                "target"
            )
            or "Not specified"
        )

        return scenario, target

    stats = results / "locust_stats.csv"

    scenario = results.name

    if scenario.startswith("locust-"):
        scenario = scenario[len("locust-"):]

    target = "Not specified"

    if stats.is_file():
        with stats.open(
            newline="",
            encoding="utf-8-sig",
        ) as handle:
            rows = list(
                csv.DictReader(handle)
            )

        for row in rows:
            if (
                row.get("Name")
                and row.get("Name")
                != "Aggregated"
            ):
                method = (
                    row.get("Type")
                    or ""
                ).strip()

                name = (
                    row.get("Name")
                    or ""
                ).strip()

                target = (
                    name
                    if (
                        method
                        and name.upper().startswith(
                            method.upper() + " "
                        )
                    )
                    else (
                        f"{method} {name}"
                    ).strip()
                )

                break

    return scenario, target



def _generate_professional_bundle(
    *,
    analysis_path: Path,
    jtl_path: Path,
    report_dir: Path,
    report_path: Path,
    scenario: str,
    target: str,
    workload_path: Path | None = None,
) -> Path | None:
    builder = (
        ROOT
        / ".gemini"
        / "skills"
        / "performance-report-interpreter"
        / "scripts"
        / "build_report_bundle.py"
    )

    if not builder.is_file():
        print(
            "Professional report bundle: "
            "SKIPPED - builder not found."
        )
        return None

    command = [
        sys.executable,
        str(builder),
        "--analysis",
        str(analysis_path),
        "--jtl",
        str(jtl_path),
        "--output-dir",
        str(report_dir),
        "--scenario",
        scenario,
        "--target",
        target,
        "--html-report",
        str(report_path),
    ]

    if (
        workload_path is not None
        and workload_path.is_file()
    ):
        command.extend(
            [
                "--workload",
                str(workload_path),
            ]
        )

    print()
    print("=" * 72)
    print("PROFESSIONAL REPORT BUNDLE")
    print("=" * 72)
    print("Engine : LOCUST")

    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
    )

    if completed.returncode != 0:
        print(
            "Status : FAILED "
            f"({completed.returncode})"
        )
        print(
            "Deterministic Locust results "
            "remain valid."
        )
        print("=" * 72)
        return None

    pdf = (
        report_dir
        / "executive-report.pdf"
    )

    if not pdf.is_file():
        print("Status : PDF NOT GENERATED")
        print("=" * 72)
        return None

    print("Status : COMPLETE")
    print("PDF    :", pdf)
    print("=" * 72)

    return pdf


def generate(
    *,
    results: Path,
    scenario: str | None,
    target: str | None,
    open_report: bool,
) -> Path:
    stats = results / "locust_stats.csv"
    history = (
        results
        / "locust_stats_history.csv"
    )
    failures = (
        results
        / "locust_failures.csv"
    )

    analysis_path = (
        results
        / "analysis.json"
    )

    report_input = (
        results
        / "report-input.jtl"
    )

    report_dir = (
        ROOT
        / "reports"
        / results.name
    )

    report = (
        report_dir
        / "executive-report.html"
    )

    derived_scenario, derived_target = (
        _derive_identity(results)
    )

    scenario = (
        scenario
        or derived_scenario
    )

    target = (
        target
        or derived_target
    )

    analysis = write_analysis(
        stats_path=stats,
        failures_path=(
            failures
            if failures.is_file()
            else None
        ),
        sla_path=(
            ROOT
            / "config"
            / "sla.json"
        ),
        output_path=analysis_path,
    )

    analysis = (
        _normalize_analysis_contract(
            analysis,
            history,
        )
    )

    analysis_path.write_text(
        json.dumps(
            analysis,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    convert_locust_history(
        history_path=history,
        output_path=report_input,
    )

    report_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        sys.executable,
        str(
            ROOT
            / "scripts"
            / "generate_report.py"
        ),
        "--analysis",
        str(analysis_path),
        "--jtl",
        str(report_input),
        "--output",
        str(report),
        "--scenario",
        scenario,
        "--target",
        target,
    ]

    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "Common report generation failed "
            f"with exit code "
            f"{completed.returncode}."
        )

    if not report.is_file():
        raise RuntimeError(
            f"Report was not generated: {report}"
        )

    metadata_path = (
        results
        / "metadata.json"
    )

    workload_path = None

    if metadata_path.is_file():
        try:
            metadata = json.loads(
                metadata_path.read_text(
                    encoding="utf-8"
                )
            )

            raw_profile = metadata.get(
                "profile"
            )

            if raw_profile:
                candidate = Path(
                    raw_profile
                ).expanduser()

                if candidate.is_file():
                    workload_path = (
                        candidate.resolve()
                    )

            if workload_path is None:
                metadata_scenario = str(
                    metadata.get("scenario")
                    or ""
                ).strip()

                if metadata_scenario:
                    candidate = (
                        ROOT
                        / "workspaces"
                        / metadata_scenario
                        / "execution-profile.yaml"
                    )

                    if candidate.is_file():
                        workload_path = (
                            candidate.resolve()
                        )

        except (
            OSError,
            json.JSONDecodeError,
        ):
            workload_path = None

    _generate_professional_bundle(
        analysis_path=analysis_path,
        jtl_path=report_input,
        report_dir=report_dir,
        report_path=report,
        scenario=scenario,
        target=target,
        workload_path=workload_path,
    )

    print()
    print("=" * 72)
    print("COMMON PERFORMANCE REPORT")
    print("=" * 72)
    print("Engine   : LOCUST")
    print("Scenario :", scenario)
    print("Target   :", target)
    print("Results  :", results)
    print("Analysis :", analysis_path)
    print("Report   :", report)
    print("=" * 72)

    if open_report:
        subprocess.run(
            ["open", str(report)],
            check=False,
        )

    return report


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--results",
        type=Path,
    )

    parser.add_argument(
        "--scenario",
    )

    parser.add_argument(
        "--target",
    )

    parser.add_argument(
        "--open",
        action="store_true",
    )

    args = parser.parse_args()

    result_dir = (
        args.results.expanduser().resolve()
        if args.results
        else newest_locust_results(
            ROOT / "results"
        )
    )

    generate(
        results=result_dir,
        scenario=args.scenario,
        target=args.target,
        open_report=args.open,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
