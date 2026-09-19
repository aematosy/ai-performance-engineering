#!/usr/bin/env python3
"""Motor de inteligencia para resultados de Performance Engineering.

Entradas:
- analysis.json
- metadata.json
- trend.json (opcional)

Salidas:
- intelligence.json
- intelligence-report.md (opcional)

El motor es determinístico, auditable y no requiere un LLM. Está diseñado
para que posteriormente pueda enriquecerse con Gemini sin reemplazar las
reglas de seguridad ni la clasificación base.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from config_loader import ConfigurationError, ConfigLoader, load_config


EXIT_OK = 0
EXIT_ERROR = 2


class IntelligenceError(RuntimeError):
    """Error controlado del motor de inteligencia."""


@dataclass(frozen=True)
class IntelligenceSettings:
    p95_warning_ratio: float
    p99_warning_ratio: float
    error_rate_warning_ratio: float
    throughput_warning_ratio: float
    degraded_score_threshold: float
    severe_degradation_score_threshold: float


@dataclass(frozen=True)
class Finding:
    code: str
    category: str
    severity: str
    title: str
    evidence: str
    recommendation: str
    priority: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "priority": self.priority,
        }


def read_json(path: Path, description: str) -> dict[str, Any]:
    if not path.is_file():
        raise IntelligenceError(f"No existe {description}: {path}")

    if path.stat().st_size == 0:
        raise IntelligenceError(f"{description} está vacío: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntelligenceError(
            f"No se pudo leer {description}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise IntelligenceError(
            f"{description} debe contener un objeto JSON."
        )

    return data


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{path.stem}-",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as file:
            temporary = Path(file.name)
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())

        temporary.replace(path)
    except OSError as exc:
        raise IntelligenceError(
            f"No se pudo escribir {path}: {exc}"
        ) from exc
    finally:
        if temporary and temporary.exists():
            temporary.unlink(missing_ok=True)


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{path.stem}-",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as file:
            temporary = Path(file.name)
            file.write(content)
            file.flush()
            os.fsync(file.fileno())

        temporary.replace(path)
    except OSError as exc:
        raise IntelligenceError(
            f"No se pudo escribir {path}: {exc}"
        ) from exc
    finally:
        if temporary and temporary.exists():
            temporary.unlink(missing_ok=True)


def resolve_path(value: str | Path, root: Path) -> Path:
    path = Path(value).expanduser()
    return (
        (root / path).resolve()
        if not path.is_absolute()
        else path.resolve()
    )


def optional_json(path: Path | None, description: str) -> dict[str, Any]:
    if path is None:
        return {}

    if not path.exists():
        return {}

    return read_json(path, description)


def load_settings(config: ConfigLoader) -> IntelligenceSettings:
    return IntelligenceSettings(
        p95_warning_ratio=float(
            config.get(
                "analytics.intelligence.warning_ratios.p95",
                default=0.80,
            )
        ),
        p99_warning_ratio=float(
            config.get(
                "analytics.intelligence.warning_ratios.p99",
                default=0.80,
            )
        ),
        error_rate_warning_ratio=float(
            config.get(
                "analytics.intelligence.warning_ratios.error_rate",
                default=0.80,
            )
        ),
        throughput_warning_ratio=float(
            config.get(
                "analytics.intelligence.warning_ratios.throughput",
                default=1.20,
            )
        ),
        degraded_score_threshold=float(
            config.get(
                "analytics.intelligence.trend.degraded_score_threshold",
                default=-20.0,
            )
        ),
        severe_degradation_score_threshold=float(
            config.get(
                "analytics.intelligence.trend.severe_degradation_score_threshold",
                default=-60.0,
            )
        ),
    )


def metric_value(
    metrics: dict[str, Any],
    name: str,
    *,
    nested_group: str | None = None,
) -> float | None:
    value: Any

    if nested_group:
        group = metrics.get(nested_group) or {}
        value = group.get(name)
    else:
        value = metrics.get(name)

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_sla_limit(
    sla_checks: Any,
    names: Iterable[str],
) -> tuple[float | None, str | None]:
    if isinstance(sla_checks, dict):
        items = [
            {"name": key, **(value if isinstance(value, dict) else {})}
            for key, value in sla_checks.items()
        ]
    elif isinstance(sla_checks, list):
        items = [item for item in sla_checks if isinstance(item, dict)]
    else:
        return None, None

    normalized_names = {name.lower() for name in names}

    for item in items:
        raw_name = str(
            item.get("name")
            or item.get("metric")
            or item.get("id")
            or ""
        ).lower()

        if raw_name not in normalized_names:
            continue

        for key in (
            "threshold",
            "limit",
            "maximum",
            "minimum",
            "sla",
            "expected",
        ):
            value = item.get(key)

            if isinstance(value, dict):
                for nested_key in ("value", "max", "min", "threshold"):
                    if nested_key in value:
                        value = value[nested_key]
                        break

            try:
                return float(value), str(
                    item.get("operator")
                    or item.get("comparison")
                    or ""
                )
            except (TypeError, ValueError):
                continue

    return None, None


def add_finding(
    findings: list[Finding],
    *,
    code: str,
    category: str,
    severity: str,
    title: str,
    evidence: str,
    recommendation: str,
    priority: int,
) -> None:
    findings.append(
        Finding(
            code=code,
            category=category,
            severity=severity,
            title=title,
            evidence=evidence,
            recommendation=recommendation,
            priority=priority,
        )
    )


def evaluate_sla(
    analysis: dict[str, Any],
    settings: IntelligenceSettings,
    findings: list[Finding],
) -> None:
    metrics = analysis.get("metrics") or {}
    sla_checks = analysis.get("sla_checks")

    verdict = str(analysis.get("verdict") or "").upper()

    if verdict == "FAIL":
        add_finding(
            findings,
            code="SLA-FAIL",
            category="sla",
            severity="CRITICAL",
            title="La ejecución incumplió uno o más SLA",
            evidence="El veredicto global del análisis fue FAIL.",
            recommendation=(
                "Revisar primero los SLA incumplidos y repetir la prueba "
                "bajo las mismas condiciones después de aplicar correcciones."
            ),
            priority=100,
        )

    p95 = metric_value(metrics, "p95", nested_group="response_time_ms")
    p95_limit, _ = extract_sla_limit(
        sla_checks,
        ("p95_response_time", "p95", "response_time_p95"),
    )

    if p95 is not None and p95_limit and p95_limit > 0:
        ratio = p95 / p95_limit

        if ratio >= 1:
            add_finding(
                findings,
                code="SLA-P95-BREACH",
                category="latency",
                severity="CRITICAL",
                title="El p95 excede el SLA",
                evidence=f"p95={p95:.2f} ms; SLA={p95_limit:.2f} ms.",
                recommendation=(
                    "Analizar endpoints lentos, tiempos de dependencia, "
                    "consultas de base de datos y saturación de recursos."
                ),
                priority=95,
            )
        elif ratio >= settings.p95_warning_ratio:
            add_finding(
                findings,
                code="SLA-P95-NEAR",
                category="latency",
                severity="WARNING",
                title="El p95 está cerca del límite de SLA",
                evidence=(
                    f"p95={p95:.2f} ms, equivalente al "
                    f"{ratio * 100:.1f}% del límite."
                ),
                recommendation=(
                    "Monitorear el p95 en una prueba más larga y revisar "
                    "si aumenta con mayor concurrencia."
                ),
                priority=70,
            )

    p99 = metric_value(metrics, "p99", nested_group="response_time_ms")
    p99_limit, _ = extract_sla_limit(
        sla_checks,
        ("p99_response_time", "p99", "response_time_p99"),
    )

    if p99 is not None and p99_limit and p99_limit > 0:
        ratio = p99 / p99_limit

        if ratio >= 1:
            add_finding(
                findings,
                code="SLA-P99-BREACH",
                category="latency",
                severity="CRITICAL",
                title="El p99 excede el SLA",
                evidence=f"p99={p99:.2f} ms; SLA={p99_limit:.2f} ms.",
                recommendation=(
                    "Investigar outliers, pausas de runtime, reintentos, "
                    "colas y latencia en servicios externos."
                ),
                priority=94,
            )
        elif ratio >= settings.p99_warning_ratio:
            add_finding(
                findings,
                code="SLA-P99-NEAR",
                category="latency",
                severity="WARNING",
                title="El p99 está cerca del límite de SLA",
                evidence=(
                    f"p99={p99:.2f} ms, equivalente al "
                    f"{ratio * 100:.1f}% del límite."
                ),
                recommendation=(
                    "Revisar la cola larga de latencia y ejecutar una "
                    "prueba de mayor duración para confirmar estabilidad."
                ),
                priority=68,
            )

    error_rate = metric_value(metrics, "error_rate_pct")
    error_limit, _ = extract_sla_limit(
        sla_checks,
        ("error_rate", "error_rate_pct"),
    )

    if error_rate is not None and error_limit is not None and error_limit > 0:
        ratio = error_rate / error_limit

        if ratio >= 1:
            add_finding(
                findings,
                code="SLA-ERROR-BREACH",
                category="reliability",
                severity="CRITICAL",
                title="La tasa de error excede el SLA",
                evidence=(
                    f"Error rate={error_rate:.3f}%; "
                    f"SLA={error_limit:.3f}%."
                ),
                recommendation=(
                    "Clasificar errores por código y etiqueta JMeter antes "
                    "de aumentar la carga."
                ),
                priority=98,
            )
        elif ratio >= settings.error_rate_warning_ratio:
            add_finding(
                findings,
                code="SLA-ERROR-NEAR",
                category="reliability",
                severity="WARNING",
                title="La tasa de error está cerca del límite",
                evidence=(
                    f"Error rate={error_rate:.3f}%, equivalente al "
                    f"{ratio * 100:.1f}% del límite."
                ),
                recommendation=(
                    "Revisar respuestas fallidas, timeouts y reintentos "
                    "antes de ejecutar pruebas de mayor volumen."
                ),
                priority=75,
            )

    throughput = metric_value(metrics, "throughput_req_per_sec")
    throughput_limit, _ = extract_sla_limit(
        sla_checks,
        ("minimum_throughput", "throughput", "throughput_req_per_sec"),
    )

    if throughput is not None and throughput_limit and throughput_limit > 0:
        ratio = throughput / throughput_limit

        if ratio < 1:
            add_finding(
                findings,
                code="SLA-THROUGHPUT-BREACH",
                category="capacity",
                severity="CRITICAL",
                title="El throughput está por debajo del mínimo",
                evidence=(
                    f"Throughput={throughput:.3f} req/s; "
                    f"mínimo={throughput_limit:.3f} req/s."
                ),
                recommendation=(
                    "Identificar el cuello de botella y revisar uso de CPU, "
                    "memoria, pools de conexión y límites de dependencias."
                ),
                priority=96,
            )
        elif ratio <= settings.throughput_warning_ratio:
            add_finding(
                findings,
                code="SLA-THROUGHPUT-NEAR",
                category="capacity",
                severity="WARNING",
                title="El throughput tiene poco margen sobre el SLA",
                evidence=(
                    f"Throughput={throughput:.3f} req/s; margen de "
                    f"{(ratio - 1) * 100:.1f}% sobre el mínimo."
                ),
                recommendation=(
                    "Ejecutar una prueba escalonada para conocer el punto "
                    "de saturación y el margen real de capacidad."
                ),
                priority=65,
            )


def evaluate_trend(
    trend: dict[str, Any],
    settings: IntelligenceSettings,
    findings: list[Finding],
) -> None:
    if not trend:
        add_finding(
            findings,
            code="TREND-NO-DATA",
            category="trend",
            severity="INFO",
            title="No hay tendencia histórica disponible",
            evidence="No se proporcionó trend.json o no fue generado.",
            recommendation=(
                "Mantener el mismo nombre de escenario y parámetros "
                "comparables para construir una línea base histórica."
            ),
            priority=20,
        )
        return

    classification = str(
        trend.get("classification") or "INSUFFICIENT_DATA"
    ).upper()
    score = float(trend.get("score") or 0)

    if classification == "DEGRADED":
        severity = (
            "CRITICAL"
            if score <= settings.severe_degradation_score_threshold
            else "WARNING"
        )
        priority = 92 if severity == "CRITICAL" else 78

        add_finding(
            findings,
            code="TREND-DEGRADED",
            category="trend",
            severity=severity,
            title="La ejecución presenta degradación frente a la anterior",
            evidence=(
                f"Trend score={score:.2f}. "
                f"{trend.get('summary') or ''}".strip()
            ),
            recommendation=(
                "Comparar cambios de aplicación, infraestructura, datos y "
                "ambiente antes de aceptar esta ejecución como nueva línea base."
            ),
            priority=priority,
        )

    elif classification == "IMPROVED":
        add_finding(
            findings,
            code="TREND-IMPROVED",
            category="trend",
            severity="POSITIVE",
            title="La ejecución mejoró frente a la anterior",
            evidence=(
                f"Trend score={score:.2f}. "
                f"{trend.get('summary') or ''}".strip()
            ),
            recommendation=(
                "Confirmar la mejora con al menos dos ejecuciones adicionales "
                "bajo la misma configuración antes de actualizar la línea base."
            ),
            priority=15,
        )

    elif classification == "STABLE":
        add_finding(
            findings,
            code="TREND-STABLE",
            category="trend",
            severity="INFO",
            title="El comportamiento permanece estable",
            evidence=(
                f"Trend score={score:.2f}. "
                f"{trend.get('summary') or ''}".strip()
            ),
            recommendation=(
                "Conservar esta ejecución como evidencia de estabilidad y "
                "continuar monitoreando p95, p99 y throughput."
            ),
            priority=10,
        )

    else:
        add_finding(
            findings,
            code="TREND-INSUFFICIENT",
            category="trend",
            severity="INFO",
            title="No existen suficientes datos para determinar tendencia",
            evidence=str(trend.get("summary") or ""),
            recommendation=(
                "Ejecutar nuevamente el mismo escenario con parámetros "
                "equivalentes."
            ),
            priority=25,
        )


def evaluate_test_quality(
    metadata: dict[str, Any],
    analysis: dict[str, Any],
    findings: list[Finding],
) -> None:
    configuration = metadata.get("test_configuration") or {}
    duration = configuration.get("duration_seconds")
    threads = configuration.get("threads")
    metrics = analysis.get("metrics") or {}
    requests = metrics.get("total_requests")

    try:
        duration_value = float(duration)
    except (TypeError, ValueError):
        duration_value = None

    if duration_value is not None and duration_value < 60:
        add_finding(
            findings,
            code="QUALITY-SHORT-DURATION",
            category="test_quality",
            severity="INFO",
            title="La prueba es demasiado corta para una conclusión sólida",
            evidence=f"Duración configurada: {duration_value:.0f} segundos.",
            recommendation=(
                "Usar al menos 5 a 15 minutos para una prueba base y una "
                "duración mayor para estabilidad o endurance."
            ),
            priority=45,
        )

    try:
        threads_value = int(threads)
    except (TypeError, ValueError):
        threads_value = None

    if threads_value is not None and threads_value < 5:
        add_finding(
            findings,
            code="QUALITY-LOW-CONCURRENCY",
            category="test_quality",
            severity="INFO",
            title="La concurrencia es baja",
            evidence=f"Usuarios configurados: {threads_value}.",
            recommendation=(
                "Incrementar la carga de forma escalonada para observar el "
                "comportamiento bajo concurrencia."
            ),
            priority=35,
        )

    try:
        request_count = int(requests)
    except (TypeError, ValueError):
        request_count = None

    if request_count is not None and request_count < 1000:
        add_finding(
            findings,
            code="QUALITY-SMALL-SAMPLE",
            category="test_quality",
            severity="INFO",
            title="La muestra contiene pocas solicitudes",
            evidence=f"Solicitudes procesadas: {request_count}.",
            recommendation=(
                "Aumentar duración o carga para reducir la sensibilidad a "
                "outliers y obtener percentiles más representativos."
            ),
            priority=40,
        )


def calculate_risk(findings: list[Finding]) -> tuple[str, int]:
    """Calcula riesgo y evita contradicciones entre severidad y nivel global.

    Reglas:
    - Cualquier hallazgo CRITICAL fuerza riesgo HIGH.
    - Dos o más WARNING fuerzan al menos riesgo MEDIUM.
    - Hallazgos INFO aportan contexto, pero no deben elevar por sí solos
      una ejecución a riesgo MEDIUM.
    """
    severity_points = {
        "CRITICAL": 60,
        "WARNING": 15,
        "INFO": 2,
        "POSITIVE": -5,
    }

    critical_count = sum(
        1 for finding in findings if finding.severity == "CRITICAL"
    )
    warning_count = sum(
        1 for finding in findings if finding.severity == "WARNING"
    )

    score = sum(
        severity_points.get(finding.severity, 0)
        for finding in findings
    )
    score = max(0, min(100, score))

    if critical_count > 0:
        return "HIGH", max(score, 60)

    if warning_count >= 2 or score >= 25:
        return "MEDIUM", score

    return "LOW", score


def build_executive_summary(
    analysis: dict[str, Any],
    trend: dict[str, Any],
    risk_level: str,
    findings: list[Finding],
) -> str:
    verdict = str(analysis.get("verdict") or "UNKNOWN").upper()
    trend_classification = str(
        trend.get("classification") or "NOT_AVAILABLE"
    ).upper()

    critical_count = sum(
        1 for finding in findings if finding.severity == "CRITICAL"
    )
    warning_count = sum(
        1 for finding in findings if finding.severity == "WARNING"
    )

    return (
        f"La ejecución obtuvo veredicto {verdict}, tendencia "
        f"{trend_classification} y riesgo {risk_level}. "
        f"Se identificaron {critical_count} hallazgos críticos y "
        f"{warning_count} advertencias."
    )


def build_intelligence(
    analysis: dict[str, Any],
    metadata: dict[str, Any],
    trend: dict[str, Any],
    settings: IntelligenceSettings,
) -> dict[str, Any]:
    findings: list[Finding] = []

    evaluate_sla(analysis, settings, findings)
    evaluate_trend(trend, settings, findings)
    evaluate_test_quality(metadata, analysis, findings)

    findings.sort(
        key=lambda finding: (
            -finding.priority,
            finding.code,
        )
    )

    risk_level, risk_score = calculate_risk(findings)

    recommendations = [
        finding.recommendation
        for finding in findings
        if finding.severity in {"CRITICAL", "WARNING"}
    ]

    if not recommendations:
        recommendations = [
            (
                "Mantener la configuración actual como referencia y repetir "
                "la ejecución para confirmar consistencia."
            )
        ]

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "engine": {
            "name": "performance-intelligence-engine",
            "mode": "deterministic",
            "llm_used": False,
        },
        "execution_id": metadata.get("execution_id"),
        "scenario": metadata.get("scenario"),
        "target": metadata.get("target"),
        "environment": metadata.get("environment"),
        "verdict": analysis.get("verdict"),
        "trend": {
            "classification": trend.get("classification"),
            "score": trend.get("score"),
            "summary": trend.get("summary"),
        },
        "risk": {
            "level": risk_level,
            "score": risk_score,
        },
        "executive_summary": build_executive_summary(
            analysis,
            trend,
            risk_level,
            findings,
        ),
        "findings": [finding.as_dict() for finding in findings],
        "recommendations": recommendations,
        "decision": build_decision(
            analysis,
            trend,
            risk_level,
            findings,
        ),
    }


def build_decision(
    analysis: dict[str, Any],
    trend: dict[str, Any],
    risk_level: str,
    findings: list[Finding],
) -> dict[str, str]:
    """Emite una decisión coherente con SLA, tendencia y severidad."""
    verdict = str(analysis.get("verdict") or "").upper()
    trend_classification = str(
        trend.get("classification") or ""
    ).upper()
    critical_findings = [
        finding for finding in findings
        if finding.severity == "CRITICAL"
    ]

    if verdict == "FAIL":
        return {
            "status": "REJECT",
            "message": (
                "La ejecución incumple SLA y no debe aceptarse como línea "
                "base ni utilizarse para autorizar un avance."
            ),
        }

    if critical_findings or risk_level == "HIGH":
        return {
            "status": "REJECT",
            "message": (
                "La ejecución cumple SLA, pero presenta hallazgos críticos. "
                "No debe aceptarse como nueva línea base sin investigación "
                "y una repetición controlada."
            ),
        }

    if trend_classification == "DEGRADED" or risk_level == "MEDIUM":
        return {
            "status": "REVIEW",
            "message": (
                "La ejecución cumple SLA, pero requiere revisión antes de "
                "ser aceptada como referencia."
            ),
        }

    return {
        "status": "ACCEPT",
        "message": (
            "La ejecución puede aceptarse como evidencia, sujeta a "
            "confirmación con ejecuciones repetidas."
        ),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    findings = payload.get("findings") or []
    recommendations = payload.get("recommendations") or []
    trend = payload.get("trend") or {}
    risk = payload.get("risk") or {}
    decision = payload.get("decision") or {}

    lines = [
        "# Performance Intelligence Report",
        "",
        f"- Execution ID: `{payload.get('execution_id')}`",
        f"- Scenario: `{payload.get('scenario')}`",
        f"- Environment: `{payload.get('environment')}`",
        f"- Verdict: **{payload.get('verdict')}**",
        f"- Trend: **{trend.get('classification') or 'NOT_AVAILABLE'}**",
        f"- Risk: **{risk.get('level')} ({risk.get('score')}/100)**",
        f"- Decision: **{decision.get('status')}**",
        "",
        "## Executive Summary",
        "",
        str(payload.get("executive_summary") or ""),
        "",
        "## Findings",
        "",
    ]

    if findings:
        for finding in findings:
            lines.extend(
                [
                    f"### [{finding['severity']}] {finding['title']}",
                    "",
                    f"- Code: `{finding['code']}`",
                    f"- Category: `{finding['category']}`",
                    f"- Evidence: {finding['evidence']}",
                    f"- Recommendation: {finding['recommendation']}",
                    "",
                ]
            )
    else:
        lines.extend(
            [
                "No se identificaron hallazgos.",
                "",
            ]
        )

    lines.extend(
        [
            "## Recommended Actions",
            "",
        ]
    )

    for index, recommendation in enumerate(recommendations, start=1):
        lines.append(f"{index}. {recommendation}")

    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"**{decision.get('status')}** — {decision.get('message')}",
            "",
        ]
    )

    return "\n".join(lines)


def print_summary(payload: dict[str, Any]) -> None:
    trend = payload.get("trend") or {}
    risk = payload.get("risk") or {}
    decision = payload.get("decision") or {}

    print(f"Execution ID : {payload.get('execution_id')}")
    print(f"Scenario     : {payload.get('scenario')}")
    print(f"Verdict      : {payload.get('verdict')}")
    print(f"Trend        : {trend.get('classification') or 'NOT_AVAILABLE'}")
    print(f"Risk         : {risk.get('level')} ({risk.get('score')}/100)")
    print(f"Decision     : {decision.get('status')}")
    print(f"Summary      : {payload.get('executive_summary')}")
    print()
    print("Top findings:")

    findings = payload.get("findings") or []

    if not findings:
        print("- None")
        return

    for finding in findings[:5]:
        print(
            f"- [{finding['severity']}] "
            f"{finding['title']} ({finding['code']})"
        )


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Genera inteligencia accionable a partir de analysis.json, "
            "metadata.json y trend.json."
        )
    )
    parser.add_argument("--config")
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--trend", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Imprime la salida completa como JSON.",
    )
    return parser


def main() -> int:
    arguments = create_parser().parse_args()

    try:
        config = load_config(config_path=arguments.config)
        root = config.project_root
        settings = load_settings(config)

        analysis_path = resolve_path(arguments.analysis, root)
        metadata_path = resolve_path(arguments.metadata, root)
        trend_path = (
            resolve_path(arguments.trend, root)
            if arguments.trend
            else None
        )
        output_path = resolve_path(arguments.output, root)
        markdown_path = (
            resolve_path(arguments.markdown_output, root)
            if arguments.markdown_output
            else None
        )

        analysis = read_json(analysis_path, "analysis.json")
        metadata = read_json(metadata_path, "metadata.json")
        trend = optional_json(trend_path, "trend.json")

        payload = build_intelligence(
            analysis,
            metadata,
            trend,
            settings,
        )

        write_json_atomic(output_path, payload)

        if markdown_path:
            write_text_atomic(
                markdown_path,
                render_markdown(payload),
            )

        if arguments.json_output:
            print(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print_summary(payload)
            print(f"\nIntelligence JSON: {output_path}")

            if markdown_path:
                print(f"Markdown report  : {markdown_path}")

        return EXIT_OK

    except (
        ConfigurationError,
        IntelligenceError,
        ValueError,
    ) as exc:
        print(f"Intelligence error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())