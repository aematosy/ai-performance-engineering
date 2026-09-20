#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from interpret_results import (
    PerformanceResultInterpreter,
    load_json,
    load_workload,
    natural_decision,
    natural_risk,
    natural_verdict,
)
from jtl_metrics import JtlMetricsAnalyzer


BLUE = colors.HexColor("#2563EB")
INDIGO = colors.HexColor("#4F46E5")
NAVY = colors.HexColor("#0F172A")
SLATE = colors.HexColor("#475569")
MUTED = colors.HexColor("#64748B")
BORDER = colors.HexColor("#D8E2F0")
PALE_BLUE = colors.HexColor("#EFF6FF")
PALE_INDIGO = colors.HexColor("#EEF2FF")
PALE_GREEN = colors.HexColor("#ECFDF3")
GREEN = colors.HexColor("#16A34A")
PALE_RED = colors.HexColor("#FEF2F2")
RED = colors.HexColor("#DC2626")
PALE_AMBER = colors.HexColor("#FFFBEB")
AMBER = colors.HexColor("#D97706")
SURFACE = colors.HexColor("#F8FAFC")
WHITE = colors.white


class ProfessionalPdfReportGenerator:
    """Genera un PDF ejecutivo, visual y genérico para pruebas HTTP web/API."""

    def __init__(
        self,
        *,
        analysis: dict[str, Any],
        intelligence: dict[str, Any],
        evidence: dict[str, Any],
        workload: dict[str, Any],
        runtime_metrics: dict[str, Any],
        scenario: str,
        target: str,
    ) -> None:
        self.analysis = analysis
        self.intelligence = intelligence
        self.evidence = evidence
        self.workload = workload
        self.runtime_metrics = runtime_metrics
        self.scenario = scenario
        self.target = target
        self.result = PerformanceResultInterpreter(
            analysis, intelligence, evidence, workload, runtime_metrics
        ).build()
        self.styles = self._styles()

    def _styles(self) -> dict[str, ParagraphStyle]:
        base = getSampleStyleSheet()
        return {
            "eyebrow": ParagraphStyle(
                "Eyebrow", parent=base["Normal"], fontName="Helvetica-Bold",
                fontSize=8.8, leading=10.5, textColor=BLUE, spaceAfter=4,
            ),
            "title": ParagraphStyle(
                "Title", parent=base["Title"], fontName="Helvetica-Bold",
                fontSize=24, leading=27, textColor=NAVY, alignment=TA_LEFT, spaceAfter=5,
            ),
            "subtitle": ParagraphStyle(
                "Subtitle", parent=base["Normal"], fontName="Helvetica",
                fontSize=9.4, leading=13, textColor=SLATE,
            ),
            "section": ParagraphStyle(
                "Section", parent=base["Heading2"], fontName="Helvetica-Bold",
                fontSize=14.2, leading=17, textColor=NAVY, spaceBefore=10, spaceAfter=6,
            ),
            "section_small": ParagraphStyle(
                "SectionSmall", parent=base["Heading3"], fontName="Helvetica-Bold",
                fontSize=11.5, leading=14, textColor=NAVY, spaceBefore=5, spaceAfter=4,
            ),
            "body": ParagraphStyle(
                "Body", parent=base["BodyText"], fontName="Helvetica",
                fontSize=9.2, leading=13.3, textColor=SLATE, spaceAfter=4,
            ),
            "small": ParagraphStyle(
                "Small", parent=base["BodyText"], fontName="Helvetica",
                fontSize=8, leading=10.8, textColor=SLATE,
            ),
            "tiny": ParagraphStyle(
                "Tiny", parent=base["BodyText"], fontName="Helvetica",
                fontSize=7.1, leading=9.2, textColor=MUTED,
            ),
            "card_label": ParagraphStyle(
                "CardLabel", parent=base["Normal"], fontName="Helvetica-Bold",
                fontSize=7.2, leading=8.5, textColor=MUTED, alignment=TA_CENTER,
            ),
            "card_value": ParagraphStyle(
                "CardValue", parent=base["Normal"], fontName="Helvetica-Bold",
                fontSize=11.5, leading=13.8, textColor=NAVY, alignment=TA_CENTER,
            ),
            "card_value_small": ParagraphStyle(
                "CardValueSmall", parent=base["Normal"], fontName="Helvetica-Bold",
                fontSize=11.5, leading=13.8, textColor=NAVY, alignment=TA_CENTER,
            ),
            "kpi": ParagraphStyle(
                "KPI", parent=base["Normal"], fontName="Helvetica-Bold",
                fontSize=12.2, leading=14.5, textColor=NAVY, alignment=TA_CENTER,
            ),
            "cell": ParagraphStyle(
                "Cell", parent=base["Normal"], fontName="Helvetica",
                fontSize=8.2, leading=10.8, textColor=SLATE,
            ),
            "cell_bold": ParagraphStyle(
                "CellBold", parent=base["Normal"], fontName="Helvetica-Bold",
                fontSize=8.2, leading=10.8, textColor=NAVY,
            ),
            "callout_title": ParagraphStyle(
                "CalloutTitle", parent=base["Normal"], fontName="Helvetica-Bold",
                fontSize=10.5, leading=12.5, textColor=NAVY, spaceAfter=3,
            ),
            "callout": ParagraphStyle(
                "Callout", parent=base["BodyText"], fontName="Helvetica",
                fontSize=9.2, leading=13.3, textColor=SLATE,
            ),
        }

    @staticmethod
    def fmt(value: Any, suffix: str = "", digits: int = 2) -> str:
        if value is None:
            return "No disponible"
        if isinstance(value, int) and digits == 0:
            return f"{value}{suffix}"
        try:
            number = float(value)
            if digits == 0:
                return f"{number:.0f}{suffix}"
            return f"{number:.{digits}f}{suffix}"
        except (TypeError, ValueError):
            return f"{value}{suffix}"

    def p(self, text: Any, style: str = "cell") -> Paragraph:
        safe = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return Paragraph(safe, self.styles[style])

    def _table(self, rows: list[list[Any]], widths: list[float], *, header: bool = False) -> Table:
        cooked: list[list[Any]] = []
        for row_index, row in enumerate(rows):
            cooked.append([
                item if isinstance(item, Paragraph) else self.p(
                    item, "cell_bold" if header and row_index == 0 else "cell"
                )
                for item in row
            ])
        table = Table(cooked, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
        commands: list[tuple] = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
        if header:
            commands += [
                ("BACKGROUND", (0, 0), (-1, 0), PALE_BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ]
            for idx in range(1, len(rows)):
                if idx % 2 == 0:
                    commands.append(("BACKGROUND", (0, idx), (-1, idx), SURFACE))
        table.setStyle(TableStyle(commands))
        return table

    def _callout(
        self,
        title: str,
        body: str,
        *,
        fill: colors.Color = PALE_BLUE,
        accent: colors.Color = BLUE,
    ) -> Table:
        content = Table([
            [Paragraph(title, self.styles["callout_title"])],
            [Paragraph(body, self.styles["callout"])],
        ], colWidths=[158 * mm])
        content.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), fill),
            ("LINEBEFORE", (0, 0), (0, -1), 3.2, accent),
            ("BOX", (0, 0), (-1, -1), 0.45, BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, 0), 7),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
            ("TOPPADDING", (0, 1), (-1, 1), 1),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
        ]))
        return content

    def _header_footer(self, canvas, doc) -> None:
        width, height = A4
        canvas.saveState()
        canvas.setFillColor(BLUE)
        canvas.rect(0, height - 6 * mm, width, 6 * mm, fill=1, stroke=0)
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.35)
        canvas.line(18 * mm, 13 * mm, width - 18 * mm, 13 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7.2)
        canvas.drawString(18 * mm, 8.5 * mm, "Performance Engineering")
        canvas.drawRightString(width - 18 * mm, 8.5 * mm, f"Página {doc.page}")
        canvas.restoreState()

    def _executive_reading(self) -> tuple[str, str, str]:
        m = self.result.metrics
        w = self.result.workload
        verdict_pass = self.result.verdict.upper() == "PASS"

        workload_bits: list[str] = []
        if w.users is not None:
            workload_bits.append(f"{w.users} usuarios virtuales")
        if w.duration_seconds is not None:
            workload_bits.append(f"{w.duration_seconds:.0f} segundos")
        workload_text = " durante ".join(workload_bits) if len(workload_bits) == 2 else ", ".join(workload_bits)

        if verdict_pass:
            observed = "El sistema cumplió los criterios de rendimiento definidos"
        else:
            observed = "El sistema no cumplió todos los criterios de rendimiento definidos"
        if workload_text:
            observed += f" bajo la carga evaluada de {workload_text}"
        if m.failed == 0 and m.requests is not None:
            observed += f". Se procesaron {m.requests} solicitudes sin errores según las validaciones configuradas."
        elif m.error_rate is not None:
            observed += f". La tasa de error observada fue {m.error_rate:.2f}%."
        else:
            observed += "."

        meaning_parts: list[str] = []
        if m.p95_ms is not None:
            meaning_parts.append(f"95 de cada 100 solicitudes respondieron en {m.p95_ms:.0f} ms o menos")
        if m.p99_ms is not None:
            meaning_parts.append(f"99 de cada 100 respondieron en {m.p99_ms:.0f} ms o menos")
        if m.throughput is not None:
            meaning_parts.append(f"el ritmo observado fue {m.throughput:.3f} solicitudes por segundo")
        meaning = "; ".join(meaning_parts)
        if meaning:
            meaning = meaning[0].upper() + meaning[1:] + ". "
        meaning += "Estos resultados describen este nivel de carga; no representan por sí solos la capacidad máxima del sistema."

        if verdict_pass:
            next_step = (
                "Usar esta ejecución como línea base y repetirla en condiciones equivalentes para confirmar estabilidad. "
                "Si se necesita evaluar escalabilidad o capacidad, ejecutar después una prueba escalonada con mayor concurrencia mediante un nuevo plan aprobado."
            )
        else:
            next_step = (
                "Revisar primero las transacciones con error y los criterios incumplidos. "
                "No aumentar la carga hasta entender la causa y repetir la línea base."
            )
        return observed, meaning, next_step

    def _latency_table(self) -> Table:
        m = self.result.metrics
        rows = [
            ["Promedio", "p50", "p90", "p95", "p99", "Máximo"],
            [
                self.fmt(m.average_ms, " ms"),
                self.fmt(m.p50_ms, " ms"),
                self.fmt(m.p90_ms, " ms"),
                self.fmt(m.p95_ms, " ms"),
                self.fmt(m.p99_ms, " ms"),
                self.fmt(m.max_ms, " ms"),
            ],
        ]
        table = self._table(rows, [27.5 * mm] * 6, header=True)
        table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BACKGROUND", (0, 1), (-1, 1), WHITE),
        ]))
        return table

    def build(self, output: Path) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(
            str(output),
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=17 * mm,
            bottomMargin=18 * mm,
            title="Reporte de Prueba de Performance",
            author="Performance Engineering",
        )
        story: list[Any] = []
        m = self.result.metrics
        w = self.result.workload
        verdict_pass = self.result.verdict.upper() == "PASS"
        verdict_color = GREEN if verdict_pass else RED
        verdict_fill = PALE_GREEN if verdict_pass else PALE_RED

        # ------------------------------------------------------------------
        # Página 1 - resumen ejecutivo
        # ------------------------------------------------------------------
        story.append(Paragraph("PERFORMANCE ENGINEERING", self.styles["eyebrow"]))
        story.append(Paragraph("Reporte de Prueba de Performance", self.styles["title"]))
        story.append(Paragraph(
            "Resultados observados durante la prueba y su interpretación.",
            self.styles["subtitle"],
        ))
        story.append(Spacer(1, 5))

        hero_meta = self._table([
            ["Escenario", self.scenario],
            ["Objetivo evaluado", self.target],
        ], [35 * mm, 130 * mm])
        hero_meta.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), PALE_INDIGO),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ]))
        story.append(hero_meta)
        story.append(Spacer(1, 7))

        conclusion_text = "Baseline" if verdict_pass else "Requiere revisión"
        status_cards = Table([
            [
                Paragraph("RESULTADO", self.styles["card_label"]),
                Paragraph("RIESGO TÉCNICO", self.styles["card_label"]),
                Paragraph("CLASIFICACIÓN", self.styles["card_label"]),
            ],
            [
                Paragraph(natural_verdict(self.result.verdict), self.styles["card_value"]),
                Paragraph(natural_risk(self.result.risk), self.styles["card_value"]),
                Paragraph(conclusion_text, self.styles["card_value"]),
            ],
        ], colWidths=[55 * mm] * 3, hAlign="CENTER")
        status_cards.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), verdict_fill),
            ("BACKGROUND", (1, 0), (1, -1), PALE_BLUE),
            ("BACKGROUND", (2, 0), (2, -1), PALE_INDIGO),
            ("BOX", (0, 0), (0, -1), 0.6, BORDER),
            ("BOX", (1, 0), (1, -1), 0.6, BORDER),
            ("BOX", (2, 0), (2, -1), 0.6, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, 0), 7),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
            ("TOPPADDING", (0, 1), (-1, 1), 7),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 9),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(status_cards)
        story.append(Spacer(1, 7))

        observed, meaning, next_step = self._executive_reading()
        story.append(Paragraph("Resumen de resultados", self.styles["section"]))
        story.append(self._callout("Resultado observado", observed, fill=verdict_fill, accent=verdict_color))
        story.append(Spacer(1, 4))
        story.append(self._callout("Interpretación", meaning, fill=PALE_BLUE, accent=BLUE))
        story.append(Spacer(1, 4))
        story.append(self._callout("Consideraciones", next_step, fill=PALE_INDIGO, accent=INDIGO))

        story.append(Paragraph("Configuración de la prueba", self.styles["section"]))
        story.append(self._table([
            ["Usuarios virtuales", self.fmt(w.users, digits=0), "Duración", self.fmt(w.duration_seconds, " s")],
            ["Ramp-up", self.fmt(w.ramp_up_seconds, " s"), "Pacing", self.fmt(w.pacing_seconds, " s")],
        ], [35 * mm, 45 * mm, 30 * mm, 55 * mm]))

        story.append(Paragraph("Indicadores principales", self.styles["section"]))

        def metric_cell(label: str, value: str, tone: str = "default") -> Paragraph:
            color = {
                "good": "#15803D",
                "warn": "#B45309",
                "bad": "#B91C1C",
                "default": "#0F172A",
            }.get(tone, "#0F172A")
            return Paragraph(
                f'<font size="7.2" color="#64748B"><b>{label.upper()}</b></font><br/>'
                f'<font size="13" color="{color}"><b>{value}</b></font>',
                self.styles["kpi"],
            )

        success_tone = "good" if (m.success_rate or 0) >= 99 else "warn"
        error_tone = "good" if (m.error_rate or 0) == 0 else "bad"
        kpi_grid = Table([
            [
                metric_cell("Solicitudes", self.fmt(m.requests, digits=0)),
                metric_cell("Éxito", self.fmt(m.success_rate, "%"), success_tone),
                metric_cell("Errores", self.fmt(m.error_rate, "%"), error_tone),
            ],
            [
                metric_cell("Throughput", self.fmt(m.throughput, " req/s", 3)),
                metric_cell("p95", self.fmt(m.p95_ms, " ms")),
                metric_cell("p99", self.fmt(m.p99_ms, " ms")),
            ],
        ], colWidths=[55 * mm] * 3, hAlign="CENTER")
        kpi_grid.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
            ("BACKGROUND", (1, 0), (1, 0), PALE_GREEN if success_tone == "good" else PALE_AMBER),
            ("BACKGROUND", (2, 0), (2, 0), PALE_GREEN if error_tone == "good" else PALE_RED),
            ("BACKGROUND", (0, 1), (0, 1), PALE_INDIGO),
            ("BACKGROUND", (1, 1), (2, 1), PALE_BLUE),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(kpi_grid)

        # ------------------------------------------------------------------
        # Página 2 - detalle técnico útil
        # ------------------------------------------------------------------
        story.append(PageBreak())
        story.append(Paragraph("Detalle técnico", self.styles["title"]))
        story.append(Paragraph(
            "Métricas para entender latencia, variabilidad y comportamiento por transacción.",
            self.styles["subtitle"],
        ))
        story.append(Spacer(1, 5))

        story.append(Paragraph("Distribución de tiempos de respuesta", self.styles["section"]))
        story.append(self._latency_table())
        story.append(Spacer(1, 5))
        story.append(self._callout(
            "Cómo interpretar estos percentiles",
            "p50 representa el comportamiento típico. p95 muestra el tiempo máximo observado para 95 de cada 100 solicitudes y p99 ayuda a detectar lentitud en la cola de casos más extremos. Un promedio aislado puede ocultar esos casos; por eso los percentiles son más útiles para evaluar experiencia y estabilidad.",
            fill=PALE_BLUE,
            accent=BLUE,
        ))

        if self.result.transactions:
            story.append(Paragraph("Desglose por transacción / servicio", self.styles["section"]))
            rows = [["Transacción / servicio", "Muestras", "Éxito", "Promedio", "p95", "p99", "Estado"]]
            for item in self.result.transactions:
                status_text = "Cumple" if item.status.upper() == "PASS" else "Con errores"
                rows.append([
                    item.label,
                    str(item.samples),
                    f"{item.success_rate:.2f}%",
                    f"{item.average_ms:.2f} ms",
                    f"{item.p95_ms:.2f} ms",
                    f"{item.p99_ms:.2f} ms",
                    status_text,
                ])
            story.append(self._table(
                rows,
                [48 * mm, 16 * mm, 19 * mm, 22 * mm, 20 * mm, 20 * mm, 20 * mm],
                header=True,
            ))

        story.append(Paragraph("Conclusiones y consideraciones", self.styles["section"]))
        limitations_text = "<br/>".join(f"• {item}" for item in self.result.limitations) or "Sin limitaciones adicionales registradas."
        recommendations = list(self.result.recommendations)
        if verdict_pass:
            recommendations.insert(0, "Usar esta ejecución como baseline de referencia para comparaciones equivalentes.")
        recommendations_text = "<br/>".join(f"• {item}" for item in recommendations) or "Sin recomendaciones adicionales."

        closing = Table([[
            Table([
                [Paragraph("Limitaciones de la ejecución", self.styles["callout_title"])],
                [Paragraph(limitations_text, self.styles["small"])],
            ], colWidths=[79 * mm], style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("LINEBEFORE", (0, 0), (0, -1), 3.2, MUTED),
                ("BOX", (0, 0), (-1, -1), 0.45, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ])),
            Table([
                [Paragraph("Recomendaciones técnicas", self.styles["callout_title"])],
                [Paragraph(recommendations_text, self.styles["small"])],
            ], colWidths=[79 * mm], style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("LINEBEFORE", (0, 0), (0, -1), 3.2, BLUE),
                ("BOX", (0, 0), (-1, -1), 0.45, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ])),
        ]], colWidths=[82.5 * mm, 82.5 * mm], hAlign="CENTER")
        closing.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(closing)

        doc.build(story, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
        return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Generar PDF profesional de performance en español.")
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--intelligence", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--workload", type=Path)
    parser.add_argument("--jtl", required=True, type=Path)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--target")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    runtime = JtlMetricsAnalyzer(args.jtl).analyze()
    target = args.target or runtime.get("scope", {}).get("target") or "Aplicación / servicio bajo prueba"
    generator = ProfessionalPdfReportGenerator(
        analysis=load_json(args.analysis),
        intelligence=load_json(args.intelligence),
        evidence=load_json(args.evidence),
        workload=load_workload(args.workload),
        runtime_metrics=runtime,
        scenario=args.scenario,
        target=target,
    )
    print(generator.build(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
