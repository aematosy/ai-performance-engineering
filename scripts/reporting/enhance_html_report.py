#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


class HtmlReportEnhancer:
    """Mejora el HTML existente sin invadir controles ni reescribir el dashboard base."""

    MARKER = "performance-report-enhancer-v4"
    EXPORT_CLASS = "performance-pdf-export-button-v4"
    OBS_CLASS = "performance-observability-v4"

    def __init__(
        self,
        html_path: Path,
        pdf_filename: str = "executive-report.pdf",
        target: str | None = None,
        *,
        grafana_url: str = "http://localhost:3000",
        prometheus_url: str = "http://localhost:9090",
        metrics_url: str = "http://localhost:9270/metrics",
    ) -> None:
        self.html_path = html_path
        self.pdf_filename = pdf_filename
        self.target = (target or "").strip()
        self.grafana_url = grafana_url.strip()
        self.prometheus_url = prometheus_url.strip()
        self.metrics_url = metrics_url.strip()

    @staticmethod
    def _remove_previous_enhancements(text: str) -> str:
        """Remove v2/v3/v4 injections so repeated runs remain idempotent."""
        marker_pattern = r"performance-(?:pdf-export-button|report-enhancer)-v\d+"
        patterns = [
            rf'<style\s+id="{marker_pattern}-style"[^>]*>.*?</style>\s*',
            rf'<script\s+id="{marker_pattern}-script"[^>]*>.*?</script>\s*',
            rf'<a\s+class="{marker_pattern}"[^>]*>.*?</a>\s*',
            rf'<div\s+class="performance-observability-v\d+"[^>]*>.*?</div>\s*',
        ]
        for pattern in patterns:
            text = re.sub(pattern, "", text, flags=re.DOTALL | re.IGNORECASE)
        return text

    def enhance(self) -> bool:
        if not self.html_path.is_file():
            return False

        text = self._remove_previous_enhancements(
            self.html_path.read_text(encoding="utf-8")
        )

        translations = {
            "Performance Test Report": "Reporte de Prueba de Performance",
            "Response Time Summary": "Resumen de Tiempos de Respuesta",
            "Requests": "Solicitudes",
            "Success Rate": "Tasa de Éxito",
            "Throughput": "Throughput",
            "Generated": "Generado",
            "Source": "Fuente",
            "Scenario": "Escenario",
            "Average": "Promedio",
            "Min": "Mínimo",
            "Max": "Máximo",
            "Transaction / Service": "Transacción / Servicio",
            "Transaction / Service Breakdown": "Desglose por Transacción / Servicio",
            "Samples": "Muestras",
            "Success": "Éxito",
            "Error Rate": "Tasa de Error",
            "Response Codes": "Códigos de Respuesta",
            "Status": "Estado",
            "Errors by Transaction / Service": "Errores por Transacción / Servicio",
            "Errors by Response Code": "Errores por Código de Respuesta",
            "SLA Validation": "Validación de SLA",
            "Recommendations": "Recomendaciones",
        }
        translations_json = json.dumps(translations, ensure_ascii=False)
        links_json = json.dumps(
            {
                "grafana": self.grafana_url,
                "prometheus": self.prometheus_url,
                "metrics": self.metrics_url,
            },
            ensure_ascii=False,
        )

        snippet = f'''
<style id="{self.MARKER}-style">
.{self.EXPORT_CLASS} {{
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 99998;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,.30);
  background: linear-gradient(135deg,#2563eb,#4f46e5);
  color: #fff !important;
  text-decoration: none;
  font: 700 14px/1 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  box-shadow: 0 12px 30px rgba(37,99,235,.28);
  transition: transform .18s ease, box-shadow .18s ease;
}}
.{self.EXPORT_CLASS}:hover {{ transform: translateY(-2px); box-shadow: 0 16px 36px rgba(37,99,235,.34); }}
.{self.EXPORT_CLASS}:focus {{ outline: 3px solid rgba(96,165,250,.40); outline-offset: 3px; }}
.{self.OBS_CLASS} {{
  margin: 20px 0 24px;
  padding: 18px 20px;
  border: 1px solid rgba(148,163,184,.32);
  border-radius: 18px;
  background: linear-gradient(135deg,rgba(37,99,235,.07),rgba(79,70,229,.04));
  box-shadow: 0 10px 24px rgba(15,23,42,.05);
}}
.{self.OBS_CLASS} .perf-obs-head {{ display:flex; align-items:flex-start; justify-content:space-between; gap:16px; margin-bottom:14px; }}
.{self.OBS_CLASS} h2 {{ margin:0; font:800 18px/1.25 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
.{self.OBS_CLASS} p {{ margin:5px 0 0; opacity:.72; font-size:13px; line-height:1.45; }}
.{self.OBS_CLASS} .perf-obs-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }}
.{self.OBS_CLASS} .perf-obs-link {{
  display:block; padding:13px 14px; border-radius:14px; border:1px solid rgba(148,163,184,.30);
  background:rgba(255,255,255,.72); color:inherit; text-decoration:none; transition:.18s ease;
}}
.{self.OBS_CLASS} .perf-obs-link:hover {{ transform:translateY(-1px); border-color:rgba(37,99,235,.48); box-shadow:0 8px 18px rgba(37,99,235,.10); }}
.{self.OBS_CLASS} .perf-obs-link strong {{ display:block; font-size:14px; margin-bottom:4px; }}
.{self.OBS_CLASS} .perf-obs-link span {{ display:block; font-size:12px; opacity:.68; line-height:1.35; overflow-wrap:anywhere; }}
[data-theme="dark"] .{self.OBS_CLASS} .perf-obs-link,
.dark .{self.OBS_CLASS} .perf-obs-link,
body.dark .{self.OBS_CLASS} .perf-obs-link {{ background:rgba(15,23,42,.58); }}
@media (max-width: 800px) {{
  .{self.OBS_CLASS} .perf-obs-grid {{ grid-template-columns:1fr; }}
  .{self.EXPORT_CLASS} {{ right:16px; bottom:16px; padding:11px 15px; }}
}}
@media print {{ .{self.EXPORT_CLASS}, .{self.OBS_CLASS} {{ display:none !important; }} }}
</style>
<a class="{self.EXPORT_CLASS}" href="{self.pdf_filename}" download title="Descargar reporte profesional en PDF" aria-label="Exportar reporte a PDF">⬇ Exportar PDF</a>
<script id="{self.MARKER}-script">
(function() {{
  const translations = {translations_json};
  const links = {links_json};
  function normalize(s) {{ return (s || '').replace(/\\s+/g,' ').trim(); }}
  function translateTextNodes() {{
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(node => {{
      const key = normalize(node.nodeValue);
      if (translations[key]) node.nodeValue = node.nodeValue.replace(key, translations[key]);
    }});
  }}
  function observabilitySection() {{
    if (document.querySelector('.{self.OBS_CLASS}')) return;
    const section = document.createElement('section');
    section.className = '{self.OBS_CLASS}';
    section.innerHTML = `
      <div class="perf-obs-head">
        <div>
          <h2>Observabilidad en tiempo real</h2>
          <p>Accesos directos para investigar comportamiento, series temporales y métricas durante una ejecución. Disponibles cuando la stack local esté activa.</p>
        </div>
      </div>
      <div class="perf-obs-grid">
        <a class="perf-obs-link" href="${{links.grafana}}" target="_blank" rel="noopener"><strong>Grafana</strong><span>Dashboards y visualización operacional</span></a>
        <a class="perf-obs-link" href="${{links.prometheus}}" target="_blank" rel="noopener"><strong>Prometheus</strong><span>Consultas y series de métricas</span></a>
        <a class="perf-obs-link" href="${{links.metrics}}" target="_blank" rel="noopener"><strong>Endpoint de métricas</strong><span>${{links.metrics}}</span></a>
      </div>`;
    const headings = Array.from(document.querySelectorAll('h1,h2,h3'));
    const anchor = headings.find(el => /Resumen de Tiempos de Respuesta|Response Time Summary/i.test(normalize(el.textContent)));
    if (anchor) {{
      const container = anchor.closest('section,article,.card') || anchor.parentElement;
      if (container && container.parentElement) container.parentElement.insertBefore(section, container);
      else document.body.appendChild(section);
    }} else {{
      const main = document.querySelector('main') || document.body;
      main.appendChild(section);
    }}
  }}
  function cleanupExportButtons() {{
    const currentClass = '{self.EXPORT_CLASS}';

    const candidates = Array.from(
      document.querySelectorAll('a, button')
    ).filter(el => {{
      const text = normalize(el.textContent).toLowerCase();
      const href = (
        el.getAttribute('href') || ''
      ).toLowerCase();

      return (
        text.includes('exportar pdf') ||
        href.endsWith('executive-report.pdf')
      );
    }});

    const currentButtons = candidates.filter(
      el => el.classList.contains(currentClass)
    );

    let keeper = currentButtons[0] || null;

    candidates.forEach(el => {{
      if (el !== keeper) {{
        el.remove();
      }}
    }});
  }}

  function run() {{
    cleanupExportButtons();
    translateTextNodes();
    observabilitySection();
  }}
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
}})();
</script>
'''
        if "</body>" in text:
            text = text.replace("</body>", snippet + "\n</body>", 1)
        else:
            text += snippet
        self.html_path.write_text(text, encoding="utf-8")
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Agregar exportación PDF, observabilidad y españolización al reporte HTML existente.")
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--pdf-filename", default="executive-report.pdf")
    parser.add_argument("--target")
    parser.add_argument("--grafana-url", default="http://localhost:3000")
    parser.add_argument("--prometheus-url", default="http://localhost:9090")
    parser.add_argument("--metrics-url", default="http://localhost:9270/metrics")
    args = parser.parse_args()
    ok = HtmlReportEnhancer(
        args.html,
        args.pdf_filename,
        args.target,
        grafana_url=args.grafana_url,
        prometheus_url=args.prometheus_url,
        metrics_url=args.metrics_url,
    ).enhance()
    print("HTML_ENHANCED" if ok else "HTML_NOT_FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
