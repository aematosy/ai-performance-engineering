#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from jtl_metrics import JtlMetricsAnalyzer
from report_models import Interpretation, Metrics, TransactionMetric, Workload


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_workload(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def pick(obj: dict[str, Any], *paths: str, default: Any = None) -> Any:
    for path in paths:
        current: Any = obj
        valid = True
        for key in path.split("."):
            if not isinstance(current, dict) or key not in current:
                valid = False
                break
            current = current[key]
        if valid and current is not None:
            return current
    return default


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def first_number(*values: Any) -> float | None:
    for value in values:
        result = as_float(value)
        if result is not None:
            return result
    return None


def risk_value(value: Any) -> str:
    if isinstance(value, dict):
        level = value.get("level") or value.get("status") or value.get("classification")
        return str(level) if level is not None else "No disponible"
    return str(value) if value not in {None, ""} else "No disponible"


def decision_values(value: Any) -> tuple[str, str]:
    if isinstance(value, dict):
        status = value.get("status") or value.get("decision") or value.get("level") or "No disponible"
        message = value.get("message") or value.get("summary") or ""
        return str(status), str(message)
    if value in {None, ""}:
        return "No disponible", ""
    return str(value), ""


def trend_values(value: Any) -> tuple[str, str]:
    if isinstance(value, dict):
        status = value.get("classification") or value.get("status") or value.get("trend") or "No disponible"
        summary = value.get("summary") or value.get("message") or ""
        return str(status), str(summary)
    if value in {None, ""}:
        return "No disponible", ""
    return str(value), ""


def natural_risk(value: str) -> str:
    mapping = {
        "LOW": "Bajo",
        "MEDIUM": "Medio",
        "MODERATE": "Medio",
        "HIGH": "Alto",
        "CRITICAL": "Crítico",
    }
    return mapping.get(value.upper(), value)


def natural_decision(value: str) -> str:
    mapping = {
        "ACCEPT": "Apto para conservar como evidencia",
        "PASS": "Apto para conservar como evidencia",
        "REVIEW": "Requiere revisión antes de aceptarse",
        "REJECT": "No apto para aceptarse como evidencia",
        "BLOCK": "No apto para continuar",
    }
    return mapping.get(value.upper(), value)


def natural_verdict(value: str) -> str:
    normalized = value.upper()
    if normalized in {"PASS", "FAIL"}:
        return normalized
    return value


class PerformanceResultInterpreter:
    """Convierte métricas de JMeter en una explicación ejecutiva clara en español."""

    def __init__(
        self,
        analysis: dict[str, Any],
        intelligence: dict[str, Any] | None = None,
        evidence: dict[str, Any] | None = None,
        workload: dict[str, Any] | None = None,
        runtime_metrics: dict[str, Any] | None = None,
    ) -> None:
        self.analysis = analysis
        self.intelligence = intelligence or {}
        self.evidence = evidence or {}
        self.workload_source = workload or {}
        self.runtime_metrics = runtime_metrics or {}

    def build(self) -> Interpretation:
        a = pick(self.analysis, "metrics", default={}) or {}
        r = pick(self.runtime_metrics, "metrics", default={}) or {}
        requests = as_int(pick(a, "total_requests", "requests", "samples", default=pick(r, "requests")))
        error_rate = first_number(
            pick(a, "error_rate", "error_rate_pct", "errors.percent", "summary.error_rate"),
            pick(r, "error_rate"),
        )
        success_rate = first_number(
            pick(a, "success_rate", "success_rate_pct", "success.percent", "summary.success_rate"),
            pick(r, "success_rate"),
        )
        if success_rate is None and error_rate is not None:
            success_rate = 100.0 - error_rate
        if error_rate is None and success_rate is not None:
            error_rate = 100.0 - success_rate

        metrics = Metrics(
            requests=requests,
            successful=as_int(pick(a, "successful", "success_count", default=pick(r, "successful"))),
            failed=as_int(pick(a, "failed", "error_count", "errors", default=pick(r, "failed"))),
            success_rate=success_rate,
            error_rate=error_rate,
            throughput=first_number(
                pick(a, "throughput", "throughput_req_per_sec", "requests_per_second", "summary.throughput"),
                pick(r, "throughput"),
            ),
            average_ms=first_number(
                pick(
                    a,
                    "response_time_ms.avg",
                    "average",
                    "avg",
                    "avg_response_time",
                    "average_response_time",
                    "response_time.average",
                ),
                pick(r, "average_ms"),
            ),
            p50_ms=first_number(
                pick(
                    a,
                    "response_time_ms.p50",
                    "p50",
                    "p50_response_time",
                    "percentiles.p50",
                ),
                pick(r, "p50_ms"),
            ),
            p90_ms=first_number(
                pick(
                    a,
                    "response_time_ms.p90",
                    "p90",
                    "p90_response_time",
                    "percentiles.p90",
                ),
                pick(r, "p90_ms"),
            ),
            p95_ms=first_number(
                pick(
                    a,
                    "response_time_ms.p95",
                    "p95",
                    "p95_response_time",
                    "percentiles.p95",
                ),
                pick(r, "p95_ms"),
            ),
            p99_ms=first_number(
                pick(
                    a,
                    "response_time_ms.p99",
                    "p99",
                    "p99_response_time",
                    "percentiles.p99",
                ),
                pick(r, "p99_ms"),
            ),
            max_ms=first_number(
                pick(
                    a,
                    "response_time_ms.max",
                    "max",
                    "max_response_time",
                    "response_time.max",
                ),
                pick(r, "max_ms"),
            ),
        )

        workload = Workload(
            users=as_int(pick(self.workload_source, "execution.threads", "threads", "users")),
            duration_seconds=as_float(pick(self.workload_source, "execution.duration_seconds", "duration_seconds", "duration")),
            ramp_up_seconds=as_float(pick(self.workload_source, "execution.ramp_time_seconds", "ramp_time_seconds", "ramp_up")),
            pacing_seconds=as_float(pick(self.workload_source, "execution.pacing_seconds", "pacing_seconds", "pacing")),
        )

        verdict = str(pick(self.analysis, "verdict", "result.verdict", default="DESCONOCIDO"))
        risk = risk_value(pick(self.intelligence, "risk", "risk_level", "assessment.risk"))
        decision, decision_message = decision_values(pick(self.intelligence, "decision", "recommendation.decision"))
        trend, trend_summary = trend_values(pick(self.intelligence, "trend", "assessment.trend"))
        coverage = str(pick(self.evidence, "coverage", default="NOT_AVAILABLE"))

        transactions: list[TransactionMetric] = []

        analysis_transactions = (
            a.get("transactions", [])
            if isinstance(a, dict)
            else []
        )

        transaction_source = (
            analysis_transactions
            if analysis_transactions
            else self.runtime_metrics.get(
                "transactions",
                [],
            )
        )

        for item in transaction_source:
            response_time = item.get(
                "response_time_ms",
                {},
            )

            if not isinstance(
                response_time,
                dict,
            ):
                response_time = {}

            samples = (
                item.get("samples")
                or item.get("total_requests")
                or item.get("requests")
                or 0
            )

            success_rate_value = first_number(
                item.get("success_rate_pct"),
                item.get("success_rate"),
            )

            error_rate_value = first_number(
                item.get("error_rate_pct"),
                item.get("error_rate"),
            )

            average_value = first_number(
                response_time.get("avg"),
                item.get("average_ms"),
            )

            p95_value = first_number(
                response_time.get("p95"),
                item.get("p95_ms"),
            )

            p99_value = first_number(
                response_time.get("p99"),
                item.get("p99_ms"),
            )

            throughput_value = first_number(
                item.get(
                    "throughput_req_per_sec"
                ),
                item.get("throughput"),
            )

            transactions.append(
                TransactionMetric(
                    label=str(
                        item.get(
                            "label",
                            "UNKNOWN",
                        )
                    ),
                    samples=int(samples),
                    success_rate=float(
                        success_rate_value
                        or 0.0
                    ),
                    error_rate=float(
                        error_rate_value
                        or 0.0
                    ),
                    average_ms=float(
                        average_value
                        or 0.0
                    ),
                    p95_ms=float(
                        p95_value
                        or 0.0
                    ),
                    p99_ms=float(
                        p99_value
                        or 0.0
                    ),
                    throughput=float(
                        throughput_value
                        or 0.0
                    ),
                    status=str(
                        item.get("status")
                        or "UNKNOWN"
                    ),
                )
            )

        result = Interpretation(
            verdict=verdict,
            risk=risk,
            decision=decision,
            decision_message=decision_message,
            trend=trend,
            trend_summary=trend_summary,
            workload=workload,
            metrics=metrics,
            transactions=transactions,
        )
        result.executive_summary = self._executive_summary(result)
        result.metric_explanations = self._metric_explanations(result)
        result.evidence_statement = self._evidence_statement(coverage)
        result.limitations = self._limitations(result)
        result.recommendations = self._recommendations(result)
        return result

    def _executive_summary(self, result: Interpretation) -> str:
        m = result.metrics
        verdict_upper = result.verdict.upper()
        if verdict_upper == "PASS":
            opening = (
                "El resultado SLA de la prueba fue PASS para la carga ejecutada."
            )
        elif verdict_upper == "FAIL":
            opening = (
                "El resultado SLA de la prueba fue FAIL para la carga ejecutada."
            )
        else:
            opening = "La ejecución finalizó y requiere revisar los criterios configurados para determinar su resultado."

        parts = [opening]
        if m.requests is not None and m.successful is not None and m.failed is not None:
            if m.failed == 0:
                parts.append(
                    f"Se procesaron {m.requests} solicitudes y todas completaron correctamente según las validaciones configuradas."
                )
            else:
                parts.append(
                    f"Se procesaron {m.requests} solicitudes: {m.successful} fueron correctas y {m.failed} presentaron error."
                )
        elif m.success_rate is not None:
            parts.append(f"La tasa de éxito fue de {m.success_rate:.2f}%.")

        if m.p95_ms is not None:
            parts.append(f"El 95% de las solicitudes respondió en {m.p95_ms:.0f} ms o menos.")
        if m.p99_ms is not None:
            parts.append(f"El 99% respondió en {m.p99_ms:.0f} ms o menos.")
        if m.throughput is not None:
            parts.append(
                f"Durante esta carga, el sistema atendió en promedio {m.throughput:.3f} solicitudes por segundo."
            )

        if result.risk != "No disponible":
            parts.append(f"El nivel de riesgo de esta ejecución es {natural_risk(result.risk).lower()}.")
        if result.decision != "No disponible":
            parts.append(f"En términos prácticos, el resultado es {natural_decision(result.decision).lower()}.")
        if result.decision_message:
            msg = result.decision_message.strip().rstrip(".")
            if msg:
                parts.append(msg + ".")
        return " ".join(parts)

    def _metric_explanations(self, result: Interpretation) -> list[str]:
        m = result.metrics
        lines: list[str] = []
        if m.requests is not None:
            lines.append(f"Solicitudes procesadas: {m.requests}. Es el volumen total de muestras HTTP analizadas en esta ejecución.")
        if m.success_rate is not None:
            if m.success_rate >= 100.0:
                lines.append("Éxito: 100%. Todas las solicitudes cumplieron las validaciones configuradas; esto no sustituye las validaciones funcionales del contenido de negocio.")
            else:
                lines.append(f"Éxito: {m.success_rate:.2f}%. Indica qué proporción de solicitudes cumplió las validaciones configuradas.")
        if m.error_rate is not None:
            lines.append(
                f"Errores: {m.error_rate:.2f}%. "
                "Este valor se compara contra el SLA permitido para determinar "
                "el resultado PASS o FAIL."
            )
        if m.throughput is not None:
            lines.append(f"Ritmo de procesamiento: {m.throughput:.3f} solicitudes por segundo con esta carga. No representa por sí solo la capacidad máxima del sistema.")
        if m.p95_ms is not None:
            lines.append(f"p95: 95 de cada 100 solicitudes tardaron {m.p95_ms:.0f} ms o menos. Es una forma práctica de entender la experiencia de la gran mayoría de las solicitudes.")
        if m.p99_ms is not None:
            lines.append(f"p99: 99 de cada 100 solicitudes tardaron {m.p99_ms:.0f} ms o menos. Ayuda a detectar lentitud en los casos más extremos.")
        return lines

    @staticmethod
    def _evidence_statement(coverage: str) -> str:
        mapping = {
            "RUNTIME_REQUEST_RESPONSE_VERIFIED": "Se capturaron muestras representativas y sanitizadas del request y response reales de runtime. Esto permite comprobar, además del código HTTP, la forma real del intercambio observado.",
            "REQUEST_TEMPLATE_PLUS_RUNTIME_STATUS": "Se dispone del estado real de runtime y del request generado por la plantilla JMX. Esto confirma qué se intentó enviar y cómo respondió HTTP, pero el body exacto del response de runtime no fue almacenado en el JTL.",
            "STATUS_ONLY": "Solo se dispone del resultado de runtime (estado/código). No hay evidencia suficiente para afirmar que el contenido del request y response fue validado.",
            "NOT_AVAILABLE": "No hay evidencia técnica adicional disponible para esta ejecución.",
        }
        return mapping.get(coverage, mapping["NOT_AVAILABLE"])

    @staticmethod
    def _limitations(result: Interpretation) -> list[str]:
        return [
            "Un resultado SLA PASS demuestra que los criterios configurados se alcanzaron con este workload; no demuestra la capacidad máxima del sistema.",
            "Una prueba de performance no sustituye las pruebas funcionales ni garantiza la ausencia de defectos de negocio.",
            "Una ejecución corta sirve como línea base; para afirmar estabilidad sostenida se requieren pruebas de mayor duración y ejecuciones repetidas.",
        ]

    @staticmethod
    def _recommendations(result: Interpretation) -> list[str]:
        recs = [
            "Conservar esta ejecución como referencia del workload aprobado "
            "y compararla con futuras ejecuciones equivalentes."
        ]

        failed = int(result.metrics.failed or 0)
        verdict = result.verdict.upper()

        if failed > 0:
            recs.append(
                "Investigar y resolver las respuestas HTTP con error observadas "
                "antes de aumentar concurrencia o duración."
            )
            recs.append(
                "Aunque el resultado SLA global sea PASS, la ejecución presenta "
                "incidencias funcionales que deben entenderse antes de utilizar "
                "esta baseline como referencia estable."
            )
            recs.append(
                "Repetir la baseline en condiciones equivalentes después de "
                "resolver o explicar las incidencias observadas."
            )
            recs.append(
                "No aumentar la carga hasta confirmar que los errores observados "
                "no corresponden a defectos funcionales, problemas de datos, "
                "correlación, autenticación o comportamiento del servicio."
            )
        elif verdict == "PASS":
            recs.append(
                "Repetir la prueba varias veces en condiciones equivalentes "
                "para establecer variabilidad y estabilidad."
            )
            recs.append(
                "Si las ejecuciones repetidas permanecen estables, evaluar una "
                "prueba escalonada con mayor concurrencia mediante un nuevo plan "
                "revisado y aprobado."
            )
        else:
            recs.append(
                "Revisar primero los SLA incumplidos y las transacciones con "
                "comportamiento degradado antes de aumentar la carga."
            )
            recs.append(
                "Repetir la baseline después de corregir o explicar las causas "
                "del resultado FAIL."
            )

        return recs


def render_markdown(result: Interpretation, coverage: str) -> str:
    risk = natural_risk(result.risk)
    decision = natural_decision(result.decision)
    lines = [
        "# Interpretación de resultados de performance",
        "",
        f"**Resultado:** {natural_verdict(result.verdict)} ({result.verdict})",
        f"**Riesgo:** {risk}",
        f"**Conclusión:** {decision}",
        "",
        "## Resumen ejecutivo",
        "",
        result.executive_summary,
        "",
        "## ¿Interpretaciónn los números?",
        "",
    ]
    lines += [f"- {x}" for x in result.metric_explanations]
    lines += [
        "",
        "## Evidencia y confianza frente a falsos positivos",
        "",
        f"**Cobertura técnica:** {coverage}",
        "",
        result.evidence_statement,
        "",
        "## Limitaciones",
        "",
    ]
    lines += [f"- {x}" for x in result.limitations]
    lines += ["", "## Recomendaciones", ""]
    lines += [f"- {x}" for x in result.recommendations]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Interpretar resultados de performance en español claro.")
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--intelligence", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--workload", type=Path)
    parser.add_argument("--jtl", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    runtime = JtlMetricsAnalyzer(args.jtl).analyze()
    result = PerformanceResultInterpreter(
        load_json(args.analysis),
        load_json(args.intelligence),
        load_json(args.evidence),
        load_workload(args.workload),
        runtime,
    ).build()
    coverage = str(load_json(args.evidence).get("coverage", "NOT_AVAILABLE"))
    args.output.write_text(render_markdown(result, coverage), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
