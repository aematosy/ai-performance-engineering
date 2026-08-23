#!/usr/bin/env python3
"""
Calcula la tendencia entre las dos últimas ejecuciones de un escenario.

Clasificaciones:
- IMPROVED: mejora general relevante.
- STABLE: variaciones dentro de tolerancias.
- DEGRADED: degradación general relevante.
- INSUFFICIENT_DATA: no existen suficientes ejecuciones comparables.

El módulo utiliza history/history.json como fuente y puede escribir trend.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config_loader import ConfigurationError, ConfigLoader, load_config
from history_manager import (
    HistoryError,
    compare_latest_executions,
    get_history_path,
)


EXIT_OK = 0
EXIT_INSUFFICIENT_DATA = 1
EXIT_ERROR = 2


class TrendError(RuntimeError):
    """Error controlado durante el cálculo de tendencia."""


@dataclass(frozen=True)
class TrendSettings:
    stable_threshold_pct: float
    error_rate_stable_threshold_points: float
    improved_score_min: float
    degraded_score_max: float
    critical_p95_degradation_pct: float
    critical_error_rate_increase_points: float
    weights: dict[str, float]


def load_settings(config: ConfigLoader) -> TrendSettings:
    weights = {
        "throughput_req_per_sec": float(
            config.get(
                "analytics.trend.weights.throughput",
                default=0.30,
            )
        ),
        "p95_ms": float(
            config.get(
                "analytics.trend.weights.p95",
                default=0.30,
            )
        ),
        "p99_ms": float(
            config.get(
                "analytics.trend.weights.p99",
                default=0.20,
            )
        ),
        "error_rate_pct": float(
            config.get(
                "analytics.trend.weights.error_rate",
                default=0.20,
            )
        ),
    }

    if any(weight < 0 for weight in weights.values()):
        raise TrendError("Los pesos de tendencia no pueden ser negativos.")

    total_weight = sum(weights.values())

    if total_weight <= 0:
        raise TrendError("La suma de pesos de tendencia debe ser mayor que cero.")

    normalized_weights = {
        name: weight / total_weight
        for name, weight in weights.items()
    }

    return TrendSettings(
        stable_threshold_pct=float(
            config.get(
                "analytics.trend.stable_threshold_pct",
                default=3.0,
            )
        ),
        error_rate_stable_threshold_points=float(
            config.get(
                "analytics.trend.error_rate_stable_threshold_points",
                default=0.10,
            )
        ),
        improved_score_min=float(
            config.get(
                "analytics.trend.improved_score_min",
                default=20.0,
            )
        ),
        degraded_score_max=float(
            config.get(
                "analytics.trend.degraded_score_max",
                default=-20.0,
            )
        ),
        critical_p95_degradation_pct=float(
            config.get(
                "analytics.trend.critical.p95_degradation_pct",
                default=20.0,
            )
        ),
        critical_error_rate_increase_points=float(
            config.get(
                "analytics.trend.critical.error_rate_increase_points",
                default=1.0,
            )
        ),
        weights=normalized_weights,
    )


def classify_percentage_change(
    value: float | int | None,
    *,
    lower_is_better: bool,
    stable_threshold_pct: float,
) -> str:
    if value is None:
        return "NO_DATA"

    numeric = float(value)

    if abs(numeric) <= stable_threshold_pct:
        return "STABLE"

    if lower_is_better:
        return "IMPROVED" if numeric < 0 else "DEGRADED"

    return "IMPROVED" if numeric > 0 else "DEGRADED"


def classify_error_rate(
    previous: float | int | None,
    current: float | int | None,
    stable_threshold_points: float,
) -> tuple[str, float | None]:
    if previous is None or current is None:
        return "NO_DATA", None

    difference = float(current) - float(previous)

    if abs(difference) <= stable_threshold_points:
        return "STABLE", round(difference, 4)

    return (
        "IMPROVED" if difference < 0 else "DEGRADED",
        round(difference, 4),
    )


def status_score(status: str) -> float:
    if status == "IMPROVED":
        return 100.0

    if status == "DEGRADED":
        return -100.0

    return 0.0


def build_trend(
    comparison: dict[str, Any],
    settings: TrendSettings,
) -> dict[str, Any]:
    raw_metrics = comparison.get("metrics") or {}

    metric_results: dict[str, Any] = {}
    weighted_score = 0.0
    available_weight = 0.0

    metric_directions = {
        "throughput_req_per_sec": False,
        "p95_ms": True,
        "p99_ms": True,
    }

    for metric_name, lower_is_better in metric_directions.items():
        metric = raw_metrics.get(metric_name) or {}
        percentage_change = metric.get("percentage_change")

        status = classify_percentage_change(
            percentage_change,
            lower_is_better=lower_is_better,
            stable_threshold_pct=settings.stable_threshold_pct,
        )

        weight = settings.weights[metric_name]

        if status != "NO_DATA":
            weighted_score += status_score(status) * weight
            available_weight += weight

        metric_results[metric_name] = {
            "previous": metric.get("previous"),
            "current": metric.get("current"),
            "absolute_change": metric.get("absolute_change"),
            "percentage_change": percentage_change,
            "status": status,
            "weight": round(weight, 4),
        }

    error_metric = raw_metrics.get("error_rate_pct") or {}
    error_status, error_difference = classify_error_rate(
        error_metric.get("previous"),
        error_metric.get("current"),
        settings.error_rate_stable_threshold_points,
    )
    error_weight = settings.weights["error_rate_pct"]

    if error_status != "NO_DATA":
        weighted_score += status_score(error_status) * error_weight
        available_weight += error_weight

    metric_results["error_rate_pct"] = {
        "previous": error_metric.get("previous"),
        "current": error_metric.get("current"),
        "absolute_change": error_difference,
        "percentage_change": error_metric.get("percentage_change"),
        "status": error_status,
        "weight": round(error_weight, 4),
    }

    if available_weight == 0:
        score = 0.0
        classification = "INSUFFICIENT_DATA"
    else:
        score = round(weighted_score / available_weight, 2)

        p95_change = metric_results["p95_ms"].get("percentage_change")
        error_increase = metric_results["error_rate_pct"].get(
            "absolute_change"
        )

        critical_degradation = (
            p95_change is not None
            and float(p95_change)
            >= settings.critical_p95_degradation_pct
        ) or (
            error_increase is not None
            and float(error_increase)
            >= settings.critical_error_rate_increase_points
        )

        if critical_degradation:
            classification = "DEGRADED"
        elif score >= settings.improved_score_min:
            classification = "IMPROVED"
        elif score <= settings.degraded_score_max:
            classification = "DEGRADED"
        else:
            classification = "STABLE"

    improved_metrics = [
        name
        for name, metric in metric_results.items()
        if metric["status"] == "IMPROVED"
    ]
    degraded_metrics = [
        name
        for name, metric in metric_results.items()
        if metric["status"] == "DEGRADED"
    ]
    stable_metrics = [
        name
        for name, metric in metric_results.items()
        if metric["status"] == "STABLE"
    ]

    summary = build_summary(
        classification,
        improved_metrics,
        degraded_metrics,
        stable_metrics,
    )

    return {
        "schema_version": "1.0",
        "scenario": comparison.get("scenario"),
        "previous_execution_id": comparison.get(
            "previous_execution_id"
        ),
        "current_execution_id": comparison.get(
            "current_execution_id"
        ),
        "previous_verdict": comparison.get("previous_verdict"),
        "current_verdict": comparison.get("current_verdict"),
        "classification": classification,
        "score": score,
        "summary": summary,
        "metrics": metric_results,
        "thresholds": {
            "stable_threshold_pct": settings.stable_threshold_pct,
            "error_rate_stable_threshold_points": (
                settings.error_rate_stable_threshold_points
            ),
            "improved_score_min": settings.improved_score_min,
            "degraded_score_max": settings.degraded_score_max,
            "critical_p95_degradation_pct": (
                settings.critical_p95_degradation_pct
            ),
            "critical_error_rate_increase_points": (
                settings.critical_error_rate_increase_points
            ),
        },
    }


def build_summary(
    classification: str,
    improved: list[str],
    degraded: list[str],
    stable: list[str],
) -> str:
    labels = {
        "throughput_req_per_sec": "throughput",
        "p95_ms": "p95",
        "p99_ms": "p99",
        "error_rate_pct": "error rate",
    }

    improved_text = ", ".join(labels[name] for name in improved)
    degraded_text = ", ".join(labels[name] for name in degraded)
    stable_text = ", ".join(labels[name] for name in stable)

    if classification == "IMPROVED":
        return (
            "La ejecución muestra una mejora general."
            + (
                f" Mejoraron: {improved_text}."
                if improved_text
                else ""
            )
            + (
                f" Requieren atención: {degraded_text}."
                if degraded_text
                else ""
            )
        )

    if classification == "DEGRADED":
        return (
            "La ejecución muestra una degradación general."
            + (
                f" Se degradaron: {degraded_text}."
                if degraded_text
                else ""
            )
            + (
                f" Mejoraron: {improved_text}."
                if improved_text
                else ""
            )
        )

    if classification == "STABLE":
        return (
            "La ejecución se mantiene estable frente a la anterior."
            + (
                f" Métricas estables: {stable_text}."
                if stable_text
                else ""
            )
        )

    return "No existen datos suficientes para calcular una tendencia."


def write_json_atomically(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{path.stem}-",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(
                payload,
                temporary_file,
                indent=2,
                ensure_ascii=False,
            )
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        temporary_path.replace(path)
    except OSError as exc:
        raise TrendError(
            f"No se pudo escribir el archivo de tendencia '{path}': {exc}"
        ) from exc
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def resolve_output_path(
    output: str | None,
    config: ConfigLoader,
    current_execution_id: str,
) -> Path | None:
    if not output:
        return None

    path = Path(output).expanduser()

    if not path.is_absolute():
        path = config.project_root / path

    path = path.resolve()

    if path.is_dir() or output.endswith(("/", "\\")):
        path = path / f"{current_execution_id}-trend.json"

    if path.suffix.lower() != ".json":
        raise TrendError("El archivo de salida debe tener extensión .json.")

    return path


def print_human_result(trend: dict[str, Any]) -> None:
    print(f"Scenario      : {trend['scenario']}")
    print(f"Previous      : {trend['previous_execution_id']}")
    print(f"Current       : {trend['current_execution_id']}")
    print(f"Classification: {trend['classification']}")
    print(f"Trend score   : {trend['score']}")
    print(f"Summary       : {trend['summary']}")
    print()

    labels = {
        "throughput_req_per_sec": "Throughput",
        "p95_ms": "p95",
        "p99_ms": "p99",
        "error_rate_pct": "Error rate",
    }

    for metric_name, metric in trend["metrics"].items():
        print(
            f"{labels[metric_name]:<12}: "
            f"{metric.get('previous')} -> {metric.get('current')} "
            f"| {metric.get('status')}"
        )


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Calcula la tendencia entre las dos últimas ejecuciones "
            "de un escenario."
        )
    )
    parser.add_argument(
        "--config",
        help="Ruta alternativa a project-config.yaml.",
    )
    parser.add_argument(
        "--history",
        help="Ruta alternativa al archivo history.json.",
    )
    parser.add_argument(
        "--scenario",
        required=True,
        help="Nombre exacto del escenario.",
    )
    parser.add_argument(
        "--output",
        help="Ruta opcional para guardar trend.json.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Imprime la tendencia en formato JSON.",
    )
    return parser


def main() -> int:
    arguments = create_parser().parse_args()

    try:
        config = load_config(config_path=arguments.config)
        settings = load_settings(config)
        history_path = get_history_path(config, arguments.history)

        comparison = compare_latest_executions(
            history_path,
            arguments.scenario,
        )
        trend = build_trend(comparison, settings)

        output_path = resolve_output_path(
            arguments.output,
            config,
            str(trend["current_execution_id"]),
        )

        if output_path:
            write_json_atomically(output_path, trend)

        if arguments.json_output:
            print(
                json.dumps(
                    trend,
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            print_human_result(trend)

            if output_path:
                print(f"\nTrend file    : {output_path}")

        return (
            EXIT_INSUFFICIENT_DATA
            if trend["classification"] == "INSUFFICIENT_DATA"
            else EXIT_OK
        )

    except HistoryError as exc:
        message = str(exc)

        if "al menos dos ejecuciones" in message:
            print(
                f"Trend unavailable: {message}",
                file=sys.stderr,
            )
            return EXIT_INSUFFICIENT_DATA

        print(f"Trend error: {message}", file=sys.stderr)
        return EXIT_ERROR

    except (ConfigurationError, TrendError, ValueError) as exc:
        print(f"Trend error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())