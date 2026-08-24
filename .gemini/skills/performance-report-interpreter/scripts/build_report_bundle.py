#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evidence_collector import collect
from enhance_html_report import HtmlReportEnhancer
from generate_professional_pdf import ProfessionalPdfReportGenerator
from interpret_results import PerformanceResultInterpreter, load_json, load_workload, render_markdown
from jtl_metrics import JtlMetricsAnalyzer


class PerformanceReportBundleBuilder:
    """Construye interpretación, PDF y mejora el HTML sin tocar la ejecución."""

    def __init__(
        self,
        *,
        analysis: Path,
        intelligence: Path | None,
        jtl: Path,
        jmx: Path | None,
        workload: Path | None,
        output_dir: Path,
        scenario: str,
        target: str | None = None,
        html_report: Path | None = None,
        grafana_url: str = "http://localhost:3000",
        prometheus_url: str = "http://localhost:9090",
        metrics_url: str | None = None,
    ) -> None:
        self.analysis_path = analysis
        self.intelligence_path = intelligence
        self.jtl_path = jtl
        self.jmx_path = jmx
        self.workload_path = workload
        self.output_dir = output_dir
        self.scenario = scenario
        self.target = (target or "").strip()
        self.html_report = html_report or (output_dir / "executive-report.html")
        self.grafana_url = grafana_url
        self.prometheus_url = prometheus_url
        self.metrics_url = metrics_url

    def build(self) -> dict[str, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Keep evidence as a machine-readable artifact for traceability and future
        # diagnostics, but do not print raw representative evidence in the PDF.
        evidence = collect(self.jtl_path, self.jmx_path)
        evidence_path = self.output_dir / "evidence.json"
        evidence_path.write_text(
            json.dumps(evidence.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        analysis = load_json(self.analysis_path)
        intelligence = load_json(self.intelligence_path)
        workload = load_workload(self.workload_path)
        runtime = JtlMetricsAnalyzer(self.jtl_path).analyze()
        resolved_target = self.target or runtime.get("scope", {}).get("target") or "Aplicación / servicio bajo prueba"
        evidence_dict = evidence.to_dict()

        interpretation = PerformanceResultInterpreter(
            analysis, intelligence, evidence_dict, workload, runtime
        ).build()
        interpretation_path = self.output_dir / "interpretation.md"
        interpretation_path.write_text(
            render_markdown(interpretation, evidence.coverage),
            encoding="utf-8",
        )

        pdf_path = self.output_dir / "executive-report.pdf"
        ProfessionalPdfReportGenerator(
            analysis=analysis,
            intelligence=intelligence,
            evidence=evidence_dict,
            workload=workload,
            runtime_metrics=runtime,
            scenario=self.scenario,
            target=resolved_target,
        ).build(pdf_path)

        observability = workload.get("observability", {}) if isinstance(workload, dict) else {}
        port = observability.get("prometheus_port", 9270) if isinstance(observability, dict) else 9270
        resolved_metrics_url = self.metrics_url or f"http://localhost:{port}/metrics"

        html_enhanced = HtmlReportEnhancer(
            self.html_report,
            pdf_path.name,
            resolved_target,
            grafana_url=self.grafana_url,
            prometheus_url=self.prometheus_url,
            metrics_url=resolved_metrics_url,
        ).enhance()

        outputs = {
            "evidence": evidence_path,
            "interpretation": interpretation_path,
            "pdf": pdf_path,
        }
        if html_enhanced:
            outputs["html"] = self.html_report
        return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Construir bundle profesional de resultados de performance.")
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--intelligence", type=Path)
    parser.add_argument("--jtl", required=True, type=Path)
    parser.add_argument("--jmx", type=Path)
    parser.add_argument("--workload", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--target", help="Objetivo general. Si se omite, se deriva del JTL sin usar un endpoint individual.")
    parser.add_argument("--html-report", type=Path)
    parser.add_argument("--grafana-url", default="http://localhost:3000")
    parser.add_argument("--prometheus-url", default="http://localhost:9090")
    parser.add_argument("--metrics-url", help="Endpoint de métricas. Si se omite, se deriva del puerto del execution profile.")
    args = parser.parse_args()

    outputs = PerformanceReportBundleBuilder(
        analysis=args.analysis,
        intelligence=args.intelligence,
        jtl=args.jtl,
        jmx=args.jmx,
        workload=args.workload,
        output_dir=args.output_dir,
        scenario=args.scenario,
        target=args.target,
        html_report=args.html_report,
        grafana_url=args.grafana_url,
        prometheus_url=args.prometheus_url,
        metrics_url=args.metrics_url,
    ).build()
    for name, path in outputs.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
