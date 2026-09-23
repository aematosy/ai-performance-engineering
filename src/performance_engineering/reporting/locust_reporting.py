from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from performance_engineering.reporting.report_context import (
    resolve_report_target,
)
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
            or ""
        ).strip()

        if not target:
            target = resolve_report_target(
                project_root=ROOT,
                scenario=scenario,
            )

        return scenario, target

    scenario = results.name

    if scenario.startswith("locust-"):
        scenario = scenario[len("locust-"):]

    target = resolve_report_target(
        project_root=ROOT,
        scenario=scenario,
    )

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
        "--engine",
        "LOCUST",
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_report_metadata(
    *,
    results: Path,
    report_dir: Path,
    report: Path,
    stats: Path,
    analysis_path: Path,
    scenario: str,
) -> None:
    execution_metadata_path = results / "metadata.json"
    execution_metadata: dict[str, Any] = {}

    if execution_metadata_path.is_file():
        try:
            payload = json.loads(
                execution_metadata_path.read_text(encoding="utf-8")
            )
            if isinstance(payload, dict):
                execution_metadata = payload
        except (OSError, json.JSONDecodeError):
            execution_metadata = {}

    payload = {
        "execution_id": execution_metadata.get("execution_id"),
        "scenario": scenario,
        "engine": "LOCUST",
        "results": str(results.resolve()),
        "source_stats": str(stats.resolve()),
        "source_stats_sha256": _sha256(stats) if stats.is_file() else None,
        "analysis": str(analysis_path.resolve()),
        "analysis_sha256": _sha256(analysis_path) if analysis_path.is_file() else None,
        "report": str(report.resolve()),
    }

    (report_dir / "report-metadata.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )



# LOCUST_HISTORY_PIPELINE_V2
def _run_locust_history_pipeline(
    *,
    results: Path,
    analysis_path: Path,
    scenario: str,
    target: str,
) -> None:
    metadata_path = results / "metadata.json"

    if not metadata_path.is_file():
        print(
            "[LOCUST HISTORY] SKIPPED: "
            f"metadata.json no existe: {metadata_path}"
        )
        return

    if not analysis_path.is_file():
        print(
            "[LOCUST HISTORY] SKIPPED: "
            f"analysis.json no existe: {analysis_path}"
        )
        return

    try:
        execution_metadata = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )
        analysis = json.loads(
            analysis_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        print(
            "[LOCUST HISTORY] SKIPPED: "
            f"no se pudo leer metadata/analysis: {exc}"
        )
        return

    if not isinstance(execution_metadata, dict):
        print(
            "[LOCUST HISTORY] SKIPPED: "
            "metadata.json no contiene un objeto JSON."
        )
        return

    if not isinstance(analysis, dict):
        print(
            "[LOCUST HISTORY] SKIPPED: "
            "analysis.json no contiene un objeto JSON."
        )
        return

    execution_id = str(
        execution_metadata.get("execution_id") or ""
    ).strip()

    if not execution_id:
        print(
            "[LOCUST HISTORY] SKIPPED: "
            "metadata.json no contiene execution_id."
        )
        return

    users = execution_metadata.get("users")
    ramp = execution_metadata.get("ramp_time_seconds")
    duration = execution_metadata.get("duration_seconds")

    target_hash = hashlib.sha256(
        target.encode("utf-8")
    ).hexdigest()[:12]

    history_scenario = (
        f"{scenario}"
        f"::LOCUST"
        f"::users={users}"
        f"::ramp={ramp}"
        f"::duration={duration}"
        f"::target={target_hash}"
    )

    # Snapshots históricos fuera del results dir operativo.
    # Locust reutiliza results/locust-<scenario>; por eso un snapshot
    # dentro de results puede desaparecer en una ejecución posterior.
    history_snapshot_dir = ROOT / "history" / "locust-snapshots"
    history_snapshot_dir.mkdir(parents=True, exist_ok=True)

    snapshot_path = (
        history_snapshot_dir
        / f"{execution_id}.metadata.json"
    )

    generated_at = execution_metadata.get("generated_at")
    if not generated_at:
        stamp = execution_id.split("-", 1)[0]
        try:
            date_part, time_part = stamp[:-1].split("T", 1)
            hhmmss, fraction = (
                time_part.split(".", 1)
                if "." in time_part
                else (time_part, "")
            )
            generated_at = (
                f"{date_part[0:4]}-{date_part[4:6]}-{date_part[6:8]}"
                f"T{hhmmss[0:2]}:{hhmmss[2:4]}:{hhmmss[4:6]}"
                + (f".{fraction}" if fraction else "")
                + "+00:00"
            )
        except (ValueError, IndexError):
            generated_at = None

    snapshot = {
        "schema_version": "1.0",
        "execution_id": execution_id,
        "generated_at": generated_at,
        "scenario": history_scenario,
        "display_scenario": scenario,
        "engine": "LOCUST",
        "target": target,
        "environment": execution_metadata.get("environment", "demo"),
        "authorized": True,
        "test_configuration": {
            "threads": users,
            "ramp_time_seconds": ramp,
            "duration_seconds": duration,
            "prometheus_port": 9271,
        },
        "files": {
            "result_directory": str(results.resolve()),
            "analysis": str(analysis_path.resolve()),
            "locust_stats": str(
                (results / "locust_stats.csv").resolve()
            ),
            "locust_stats_history": str(
                (results / "locust_stats_history.csv").resolve()
            ),
        },
        "technical_errors": [],
        "verdict": analysis.get("verdict"),
        "metrics": analysis.get("metrics"),
        "sla_checks": analysis.get("sla_checks"),
    }

    temporary = snapshot_path.with_suffix(
        snapshot_path.suffix + ".tmp"
    )
    try:
        temporary.write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(snapshot_path)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)

    history_manager = ROOT / "scripts" / "history_manager.py"
    trend_analyzer = ROOT / "scripts" / "trend_analyzer.py"
    config = ROOT / "config" / "project-config.yaml"
    trend_path = results / "trend.json"

    if not history_manager.is_file():
        print(
            "[LOCUST HISTORY] SKIPPED: "
            f"no existe {history_manager}"
        )
        return

    print()
    print("=" * 72)
    print("LOCUST EXECUTION HISTORY")
    print("=" * 72)
    print(f"Execution : {execution_id}")
    print(f"Scenario  : {scenario}")
    print("Engine    : LOCUST")

    add_result = subprocess.run(
        [
            sys.executable,
            str(history_manager),
            "--config",
            str(config),
            "add",
            "--metadata",
            str(snapshot_path),
        ],
        cwd=ROOT,
        check=False,
    )

    if add_result.returncode != 0:
        print(
            "[LOCUST HISTORY] INFO: "
            "la ejecución puede estar ya registrada; "
            "se continuará con compare/trend de forma idempotente."
        )

    comparison_result = subprocess.run(
        [
            sys.executable,
            str(history_manager),
            "--config",
            str(config),
            "compare",
            "--scenario",
            history_scenario,
        ],
        cwd=ROOT,
        check=False,
    )

    trend_path.unlink(missing_ok=True)

    if not trend_analyzer.is_file():
        print(
            "[LOCUST HISTORY] WARNING: "
            f"no existe {trend_analyzer}. "
            "El reporte continuará sin tendencia."
        )
        print("=" * 72)
        return

    trend_result = subprocess.run(
        [
            sys.executable,
            str(trend_analyzer),
            "--config",
            str(config),
            "--scenario",
            history_scenario,
            "--output",
            str(trend_path),
        ],
        cwd=ROOT,
        check=False,
    )

    if trend_result.returncode == 0 and trend_path.is_file():
        print(
            "[LOCUST HISTORY] Trend disponible: "
            f"{trend_path}"
        )
    elif trend_result.returncode == 1:
        print(
            "[LOCUST HISTORY] Sin historial suficiente. "
            "Ejecución registrada como referencia inicial."
        )
    else:
        print(
            "[LOCUST HISTORY] WARNING: "
            f"trend falló con código {trend_result.returncode}. "
            "El reporte continuará."
        )

    if comparison_result.returncode != 0:
        print(
            "[LOCUST HISTORY] Comparación previa no disponible todavía."
        )

    print("=" * 72)


def generate(
    *,
    results: Path,
    scenario: str | None,
    target: str | None,
    open_report: bool,
) -> Path:
    project_root = (
        Path(__file__)
        .resolve()
        .parents[3]
    )

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

    _run_locust_history_pipeline(
        results=results,
        analysis_path=analysis_path,
        scenario=scenario,
        target=target,
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

    _write_report_metadata(
        results=results,
        report_dir=report_dir,
        report=report,
        stats=stats,
        analysis_path=analysis_path,
        scenario=scenario,
    )

    print()
    print("=" * 72)
    target = resolve_report_target(
        project_root=project_root,
        scenario=scenario,
        explicit_target=target,
    )

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
