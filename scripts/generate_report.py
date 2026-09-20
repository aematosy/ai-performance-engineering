#!/usr/bin/env python3
"""
Genera un reporte HTML autocontenido a partir de:

- analysis.json
- results.jtl

Uso:

python3 scripts/generate_report.py \
  --analysis results/baseline-analysis.json \
  --jtl /tmp/baseline.jtl \
  --output reports/baseline-report.html \
  --scenario "Baseline API Test" \
  --target "GET https://jsonplaceholder.typicode.com/posts/1"
"""

import argparse
import csv
import html
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def load_timeseries(jtl_path, bucket_seconds=1):
    buckets_rt = defaultdict(list)
    buckets_count = defaultdict(int)
    buckets_errors = defaultdict(int)

    with jtl_path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    if not rows:
        return [], [], [], []

    timestamps = [
        int(row["timeStamp"])
        for row in rows
        if str(row.get("timeStamp", "")).strip().isdigit()
    ]

    if not timestamps:
        return [], [], [], []

    start_timestamp = min(timestamps)

    for row in rows:
        timestamp_raw = str(row.get("timeStamp", "")).strip()

        if not timestamp_raw.isdigit():
            continue

        timestamp = int(timestamp_raw)
        bucket = (
            timestamp - start_timestamp
        ) // (bucket_seconds * 1000)

        buckets_count[bucket] += 1

        elapsed_raw = str(row.get("elapsed", "")).strip()

        if elapsed_raw.isdigit():
            buckets_rt[bucket].append(int(elapsed_raw))

        success = str(row.get("success", "")).strip().lower()

        if success != "true":
            buckets_errors[bucket] += 1

    max_bucket = max(buckets_count.keys())

    time_labels = [
        bucket * bucket_seconds
        for bucket in range(max_bucket + 1)
    ]

    average_response_time = [
        (
            sum(buckets_rt[bucket]) / len(buckets_rt[bucket])
            if buckets_rt.get(bucket)
            else 0
        )
        for bucket in range(max_bucket + 1)
    ]

    throughput = [
        buckets_count.get(bucket, 0) / float(bucket_seconds)
        for bucket in range(max_bucket + 1)
    ]

    error_rate = [
        (
            buckets_errors.get(bucket, 0)
            / float(buckets_count.get(bucket, 1))
            * 100
        )
        for bucket in range(max_bucket + 1)
    ]

    return (
        time_labels,
        average_response_time,
        throughput,
        error_rate,
    )


def svg_line_chart(
    x_labels,
    series,
    width=820,
    height=240,
    color="#4f8ef7",
    y_label="",
    x_suffix="s",
):
    if not series or max(series) == 0:
        return (
            '<p class="empty-chart">'
            "Sin datos suficientes para graficar."
            "</p>"
        )

    pad_left = 55
    pad_right = 20
    pad_top = 25
    pad_bottom = 35

    plot_width = width - pad_left - pad_right
    plot_height = height - pad_top - pad_bottom

    maximum_y = max(series) * 1.15 or 1
    count = len(series)
    step_x = plot_width / max(count - 1, 1)

    points = []

    for index, value in enumerate(series):
        x = pad_left + index * step_x
        y = (
            pad_top
            + plot_height
            - (value / maximum_y) * plot_height
        )
        points.append((x, y))

    polyline_points = " ".join(
        "{:.1f},{:.1f}".format(x, y)
        for x, y in points
    )

    y_ticks = []

    for index in range(5):
        value = maximum_y * index / 4
        y = (
            pad_top
            + plot_height
            - (value / maximum_y) * plot_height
        )

        y_ticks.append(
            (
                '<text x="{x}" y="{y:.1f}" '
                'font-size="10" fill="#8b949e" '
                'text-anchor="end">{value:.0f}</text>'
                '<line x1="{left}" y1="{y:.1f}" '
                'x2="{right}" y2="{y:.1f}" '
                'stroke="#30363d" stroke-width="1"/>'
            ).format(
                x=pad_left - 8,
                y=y + 4,
                value=value,
                left=pad_left,
                right=width - pad_right,
            )
        )

    x_ticks = []
    tick_every = max(count // 6, 1)

    for index in range(0, count, tick_every):
        x_ticks.append(
            (
                '<text x="{x:.1f}" y="{y}" '
                'font-size="10" fill="#8b949e" '
                'text-anchor="middle">{label}{suffix}</text>'
            ).format(
                x=points[index][0],
                y=height - pad_bottom + 18,
                label=x_labels[index],
                suffix=x_suffix,
            )
        )

    area_points = (
        "{},{} {} {:.1f},{}".format(
            pad_left,
            pad_top + plot_height,
            polyline_points,
            points[-1][0],
            pad_top + plot_height,
        )
    )

    return """
    <svg viewBox="0 0 {width} {height}"
         width="100%"
         role="img"
         aria-label="{label}">
      <polygon points="{area}"
               fill="{color}"
               opacity="0.12"/>
      <polyline points="{polyline}"
                fill="none"
                stroke="{color}"
                stroke-width="2.5"/>
      {y_ticks}
      {x_ticks}
      <text x="{left}" y="15"
            font-size="11"
            fill="#8b949e">{label}</text>
    </svg>
    """.format(
        width=width,
        height=height,
        label=html.escape(y_label),
        area=area_points,
        color=color,
        polyline=polyline_points,
        y_ticks="".join(y_ticks),
        x_ticks="".join(x_ticks),
        left=pad_left,
    )



def format_metric(
    value,
    suffix="",
    decimals=2,
):
    """Format metrics consistently for human-readable reports."""

    if value is None:
        return "N/A"

    try:
        number = float(value)
    except (TypeError, ValueError):
        return (
            html.escape(str(value))
            + suffix
        )

    formatted = (
        f"{number:.{decimals}f}"
    )

    return (
        html.escape(formatted)
        + suffix
    )


def transaction_table_rows(
    analysis,
):
    transactions = (
        analysis
        .get("metrics", {})
        .get("transactions", [])
    )

    if not transactions:
        return (
            '<tr>'
            '<td colspan="10" class="muted">'
            'No hay métricas por transacción disponibles.'
            '</td>'
            '</tr>'
        )

    rows = []

    for tx in transactions:
        response = (
            tx.get("response_time_ms")
            or {}
        )

        codes = (
            tx.get("response_codes")
            or {}
        )

        codes_text = ", ".join(
            "{}×{}".format(
                html.escape(str(code)),
                count,
            )
            for code, count
            in codes.items()
        )

        rows.append(
            (
                "<tr>"
                "<td><strong>{label}</strong></td>"
                "<td>{samples}</td>"
                "<td>{success}%</td>"
                "<td>{errors}%</td>"
                "<td>{avg}</td>"
                "<td>{p90}</td>"
                "<td>{p95}</td>"
                "<td>{p99}</td>"
                "<td>{throughput}</td>"
                "<td>{codes}</td>"
                "</tr>"
            ).format(
                label=html.escape(
                    str(
                        tx.get(
                            "label",
                            "unknown",
                        )
                    )
                ),
                samples=tx.get(
                    "samples",
                    tx.get(
                        "total_requests",
                        0,
                    ),
                ),
                success=format_metric(
                    tx.get(
                        "success_rate_pct",
                        0,
                    ),
                    decimals=3,
                ),
                errors=format_metric(
                    tx.get(
                        "error_rate_pct",
                        0,
                    ),
                    decimals=3,
                ),
                avg=format_metric(
                    response.get("avg"),
                    decimals=2,
                ),
                p90=format_metric(
                    response.get("p90"),
                    decimals=2,
                ),
                p95=format_metric(
                    response.get("p95"),
                    decimals=2,
                ),
                p99=format_metric(
                    response.get("p99"),
                    decimals=2,
                ),
                throughput=format_metric(
                    tx.get(
                        "throughput_req_per_sec"
                    ),
                    decimals=3,
                ),
                codes=(
                    codes_text
                    or "Sin datos"
                ),
            )
        )

    return "".join(rows)


def error_transaction_rows(
    analysis,
):
    error_details = (
        analysis
        .get("metrics", {})
        .get("error_details", [])
    )

    if not error_details:
        return (
            '<tr>'
            '<td colspan="5" class="muted">'
            'No failed transactions.'
            '</td>'
            '</tr>'
        )

    rows = []

    for item in error_details:
        codes = item.get(
            "error_response_codes",
            {},
        )

        messages = item.get(
            "failure_messages",
            {},
        )

        codes_text = ", ".join(
            "{}×{}".format(
                html.escape(str(code)),
                count,
            )
            for code, count
            in codes.items()
        )

        message_text = "<br>".join(
            "{} × {}".format(
                count,
                html.escape(str(message)),
            )
            for message, count
            in messages.items()
        )

        rows.append(
            (
                "<tr>"
                "<td><strong>{label}</strong></td>"
                "<td>{errors}</td>"
                "<td>{rate}%</td>"
                "<td>{codes}</td>"
                "<td>{messages}</td>"
                "</tr>"
            ).format(
                label=html.escape(
                    str(
                        item.get(
                            "label",
                            "unknown",
                        )
                    )
                ),
                errors=item.get(
                    "error_count",
                    0,
                ),
                rate=item.get(
                    "error_rate_pct",
                    0,
                ),
                codes=(
                    codes_text
                    or "N/A"
                ),
                messages=(
                    message_text
                    or "N/A"
                ),
            )
        )

    return "".join(rows)



def build_recommendations(analysis):
    metrics = analysis["metrics"]
    recommendations = []

    if metrics["error_rate_pct"] > 0:
        recommendations.append(
            "Revisar los códigos de respuesta y etiquetas "
            "con errores antes de aumentar la carga."
        )

    if metrics["response_time_ms"]["p95"] is not None:
        if (
            metrics["response_time_ms"]["p95"]
            > analysis["sla"]["p95_threshold_ms"]
        ):
            recommendations.append(
                "Investigar el incremento del p95 y correlacionarlo "
                "con CPU, memoria, red y dependencias externas."
            )

    if metrics["response_time_ms"]["p99"] is not None:
        if (
            metrics["response_time_ms"]["p99"]
            > analysis["sla"]["p99_threshold_ms"]
        ):
            recommendations.append(
                "Analizar outliers y operaciones lentas que afectan "
                "el percentil p99."
            )

    if analysis["verdict"] == "PASS":
        recommendations.append(
            "El escenario cumple los SLA configurados. "
            "Ejecutar una prueba escalonada con mayor concurrencia."
        )

        recommendations.append(
            "Repetir la línea base varias veces para establecer "
            "variabilidad y estabilidad."
        )

    return recommendations


def build_html(
    analysis,
    time_labels,
    average_response_time,
    throughput_series,
    error_rate_series,
    scenario,
    target,
):
    metrics = analysis["metrics"]
    verdict = analysis["verdict"]

    interactive_payload = {
        "global": {
            "label": "Todas las transacciones",
            "samples": metrics.get(
                "total_requests",
                0,
            ),
            "success_count": metrics.get(
                "success_count",
                0,
            ),
            "error_count": metrics.get(
                "error_count",
                0,
            ),
            "success_rate_pct": metrics.get(
                "success_rate_pct",
                0,
            ),
            "error_rate_pct": metrics.get(
                "error_rate_pct",
                0,
            ),
            "throughput_req_per_sec": metrics.get(
                "throughput_req_per_sec"
            ),
            "response_time_ms": metrics.get(
                "response_time_ms",
                {},
            ),
            "response_codes": {},
            "time_series": metrics.get(
                "time_series",
                [],
            ),
        },
        "transactions": metrics.get(
            "transactions",
            [],
        ),
    }

    service_dashboard_json = (
        json.dumps(
            interactive_payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        .replace("</", "<\\/")
    )

    verdict_class = (
        "verdict-pass"
        if verdict == "PASS"
        else "verdict-fail"
    )

    response_time_chart = svg_line_chart(
        time_labels,
        average_response_time,
        color="#58a6ff",
        y_label="Tiempo de respuesta promedio (ms)",
    )

    throughput_chart = svg_line_chart(
        time_labels,
        throughput_series,
        color="#d29922",
        y_label="Throughput (req/s)",
    )

    error_chart = svg_line_chart(
        time_labels,
        error_rate_series,
        color="#f85149",
        y_label="Tasa de error (%)",
    )

    checks_rows = "".join(
        (
            "<tr>"
            "<td>{check}</td>"
            "<td>{threshold}</td>"
            "<td>{actual}</td>"

            "</tr>"
        ).format(
            check=html.escape(str(check["check"])),
            threshold=html.escape(str(check["threshold"])),
            actual=html.escape(str(check["actual"])),
            status_class=(
                "status-pass"
                if check["passed"]
                else "status-fail"
            ),
            status=(
                "PASS"
                if check["passed"]
                else "FAIL"
            ),
        )
        for check in analysis["sla_checks"]
    )

    transaction_rows = (
        transaction_table_rows(
            analysis
        )
    )

    transaction_error_rows = (
        error_transaction_rows(
            analysis
        )
    )

    errors_by_code = metrics.get(
        "errors_by_response_code",
        {},
    )

    errors_rows = "".join(
        "<tr><td>{}</td><td>{}</td></tr>".format(
            html.escape(str(code)),
            count,
        )
        for code, count in errors_by_code.items()
    )

    if not errors_rows:
        errors_rows = (
            '<tr><td colspan="2" class="muted">'
            "Sin errores registrados"
            "</td></tr>"
        )

    recommendations = build_recommendations(analysis)

    recommendations_html = "".join(
        "<li>{}</li>".format(
            html.escape(recommendation)
        )
        for recommendation in recommendations
    )

    generated_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport"
      content="width=device-width, initial-scale=1.0">
<title>Reporte de Prueba de Performance</title>

<style>
  :root {{
    color-scheme: dark;
    --background: #0d1117;
    --surface: #161b22;
    --border: #30363d;
    --text: #f0f6fc;
    --muted: #8b949e;
    --blue: #58a6ff;
    --green: #3fb950;
    --red: #f85149;
    --yellow: #d29922;
  }}

  * {{
    box-sizing: border-box;
  }}

  body {{
    margin: 0;
    background:
      radial-gradient(
        circle at top right,
        rgba(88, 166, 255, 0.10),
        transparent 28%
      ),
      var(--background);
    color: var(--text);
    font-family:
      Inter,
      -apple-system,
      BlinkMacSystemFont,
      "Segoe UI",
      sans-serif;
    line-height: 1.5;
  }}

  .container {{
    width: min(1120px, calc(100% - 40px));
    margin: 0 auto;
    padding: 42px 0 60px;
  }}

  .header {{
    display: flex;
    justify-content: space-between;
    gap: 24px;
    align-items: flex-start;
    margin-bottom: 28px;
  }}

  .eyebrow {{
    color: var(--blue);
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }}

  h1 {{
    margin: 5px 0 8px;
    font-size: clamp(28px, 5vw, 42px);
    line-height: 1.1;
  }}

  .subtitle {{
    color: var(--muted);
    max-width: 720px;
  }}

  .verdict {{
    border-radius: 999px;
    padding: 10px 18px;
    font-size: 14px;
    font-weight: 800;
    letter-spacing: 0.08em;
  }}

  .verdict-pass {{
    color: var(--green);
    border: 1px solid rgba(63, 185, 80, 0.45);
    background: rgba(63, 185, 80, 0.10);
  }}

  .verdict-fail {{
    color: var(--red);
    border: 1px solid rgba(248, 81, 73, 0.45);
    background: rgba(248, 81, 73, 0.10);
  }}

  .metadata {{
    display: grid;
    grid-template-columns:
      repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px;
    margin-bottom: 24px;
  }}

  .metadata-item,
  .card,
  .panel {{
    background: rgba(22, 27, 34, 0.92);
    border: 1px solid var(--border);
    border-radius: 14px;
  }}

  .metadata-item {{
    padding: 14px 16px;
  }}

  .metadata-label,
  .card-label {{
    color: var(--muted);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }}

  .metadata-value {{
    margin-top: 4px;
    overflow-wrap: anywhere;
  }}

  .cards {{
    display: grid;
    grid-template-columns:
      repeat(auto-fit, minmax(170px, 1fr));
    gap: 14px;
    margin-bottom: 26px;
  }}

  .card {{
    padding: 18px;
  }}

  .table-scroll {{
    width: 100%;
    overflow-x: auto;
  }}

  .table-scroll table {{
    min-width: 1050px;
  }}

  .card-value {{
    margin-top: 6px;
    font-size: 27px;
    font-weight: 750;
  }}

  .panel {{
    padding: 20px;
    margin-bottom: 20px;
  }}

  .panel h2 {{
    margin: 0 0 16px;
    font-size: 17px;
  }}

  .chart-grid {{
    display: grid;
    grid-template-columns:
      repeat(auto-fit, minmax(380px, 1fr));
    gap: 18px;
  }}

  .chart-panel {{
    min-width: 0;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}

  th,
  td {{
    padding: 11px 12px;
    border-bottom: 1px solid var(--border);
    text-align: left;
  }}

  th {{
    color: var(--muted);
    font-weight: 650;
  }}

  .status-pass {{
    color: var(--green);
    font-weight: 750;
  }}

  .status-fail {{
    color: var(--red);
    font-weight: 750;
  }}

  .muted,
  .empty-chart {{
    color: var(--muted);
  }}

  ul {{
    padding-left: 20px;
  }}

  li {{
    margin-bottom: 8px;
  }}

  .footer {{
    color: var(--muted);
    text-align: center;
    font-size: 12px;
    padding-top: 18px;
  }}

  @media (max-width: 720px) {{
    .header {{
      flex-direction: column;
    }}

    .chart-grid {{
      grid-template-columns: 1fr;
    }}
  }}

  :root {{
    color-scheme: dark;

    --theme-bg: #0d1117;
    --theme-surface: #151b23;
    --theme-surface-alt: #1b222c;
    --theme-border: #303844;

    --theme-text: #f2f5f8;
    --theme-text-secondary: #a6b0bd;
    --theme-muted: #8d98a6;

    --theme-table-header: #1b222c;
    --theme-table-alt: #111820;

    --theme-shadow: rgba(0, 0, 0, 0.20);

    --theme-toggle-bg: #1b222c;
    --theme-toggle-hover: #252e39;
  }}

  html[data-theme="light"] {{
    color-scheme: light;

    --theme-bg: #f5f7fa;
    --theme-surface: #ffffff;
    --theme-surface-alt: #f3f5f8;
    --theme-border: #d8dee7;

    --theme-text: #18202a;
    --theme-text-secondary: #4e5968;
    --theme-muted: #697586;

    --theme-table-header: #edf1f5;
    --theme-table-alt: #f8fafc;

    --theme-shadow: rgba(15, 23, 42, 0.08);

    --theme-toggle-bg: #ffffff;
    --theme-toggle-hover: #f0f3f7;
  }}

  html,
  body {{
    background: var(--theme-bg) !important;
    color: var(--theme-text) !important;

    transition:
      background-color 0.18s ease,
      color 0.18s ease;
  }}

  body {{
    min-height: 100vh;
  }}

  .panel,
  .card,
  .metric-card,
  .summary-card {{
    background: var(--theme-surface) !important;
    border-color: var(--theme-border) !important;
    color: var(--theme-text) !important;
  }}

  h1,
  h2,
  h3,
  h4,
  strong,
  .card-value {{
    color: var(--theme-text) !important;
  }}

  p,
  .muted,
  .subtitle,
  .card-label {{
    color: var(--theme-text-secondary) !important;
  }}

  table {{
    color: var(--theme-text) !important;
  }}

  th {{
    background: var(--theme-table-header) !important;
    color: var(--theme-text) !important;
    border-color: var(--theme-border) !important;
  }}

  td {{
    color: var(--theme-text) !important;
    border-color: var(--theme-border) !important;
  }}

  tbody tr:nth-child(even) {{
    background: var(--theme-table-alt) !important;
  }}

  .report-toolbar {{
    position: fixed;
    top: 18px;
    right: 22px;
    z-index: 9999;

    display: flex;
    align-items: center;
    gap: 8px;
  }}

  .theme-toggle {{
    appearance: none;

    border: 1px solid var(--theme-border);
    border-radius: 999px;

    background: var(--theme-toggle-bg);
    color: var(--theme-text);

    padding: 9px 14px;

    display: inline-flex;
    align-items: center;
    gap: 8px;

    font: inherit;
    font-size: 13px;
    font-weight: 700;

    cursor: pointer;

    box-shadow:
      0 6px 18px var(--theme-shadow);

    transition:
      background-color 0.15s ease,
      border-color 0.15s ease,
      transform 0.15s ease;
  }}

  .theme-toggle:hover {{
    background: var(--theme-toggle-hover);
    transform: translateY(-1px);
  }}

  .theme-toggle:focus-visible {{
    outline: 2px solid currentColor;
    outline-offset: 3px;
  }}

  .theme-toggle-icon {{
    font-size: 16px;
    line-height: 1;
  }}

  @media (max-width: 720px) {{
    .report-toolbar {{
      position: static;
      justify-content: flex-end;
      margin-bottom: 16px;
    }}
  }}


  /* ==========================================================
     REPORT THEME v3
     Semantic tokens shared by every report component.
     Literal braces are doubled because this template uses
     Python str.format().
     ========================================================== */

  :root {{
    --report-bg: #0d1117;
    --report-panel: #151b23;
    --report-panel-soft: #1b222c;
    --report-card: #151b23;
    --report-card-strong: #1b222c;

    --report-text: #f2f5f8;
    --report-text-secondary: #a6b0bd;
    --report-muted: #8d98a6;

    --report-border: #303844;
    --report-table-head: #1b222c;
    --report-table-alt: #111820;

    --report-input-bg: #151b23;

    --report-grid: #303844;
    --report-axis-text: #8d98a6;

    --report-response: #58a6ff;
    --report-throughput: #d29922;
    --report-error: #f85149;

    --report-pass: #3fb950;
    --report-fail: #f85149;

    --report-shadow:
      0 12px 30px rgba(0, 0, 0, 0.18);
  }}

  html[data-theme="light"] {{
    --report-bg: #f4f7fb;
    --report-panel: #ffffff;
    --report-panel-soft: #f7f9fc;
    --report-card: #ffffff;
    --report-card-strong: #ffffff;

    --report-text: #17202c;
    --report-text-secondary: #4d5968;
    --report-muted: #6d7886;

    --report-border: #d8e0ea;
    --report-table-head: #edf2f7;
    --report-table-alt: #f7f9fc;

    --report-input-bg: #ffffff;

    --report-grid: #d7dee8;
    --report-axis-text: #687386;

    --report-response: #2563eb;
    --report-throughput: #b86e00;
    --report-error: #dc2626;

    --report-pass: #16803d;
    --report-fail: #d92d20;

    --report-shadow:
      0 8px 24px rgba(15, 23, 42, 0.07);
  }}

  html,
  body {{
    background: var(--report-bg) !important;
    color: var(--report-text) !important;
  }}

  body {{
    color: var(--report-text) !important;
  }}

  h1,
  h2,
  h3,
  h4 {{
    color: var(--report-text) !important;
  }}

  p,
  .subtitle,
  .muted {{
    color: var(--report-text-secondary) !important;
  }}

  .panel,
  .card,
  .metric-card,
  .summary-card {{
    background: var(--report-panel) !important;
    border-color: var(--report-border) !important;
    color: var(--report-text) !important;
    box-shadow: var(--report-shadow);
  }}

  /* Metadata cards at the top.
     This intentionally overrides their previous dark-only design. */
  .meta-card,
  .metadata-card,
  .info-card {{
    background: var(--report-card-strong) !important;
    border-color: var(--report-border) !important;
    color: var(--report-text) !important;
  }}

  .meta-card *,
  .metadata-card *,
  .info-card * {{
    color: var(--report-text) !important;
  }}

  .meta-card .label,
  .metadata-card .label,
  .info-card .label,
  .card-label {{
    color: var(--report-muted) !important;
  }}

  table {{
    color: var(--report-text) !important;
  }}

  th {{
    background: var(--report-table-head) !important;
    border-color: var(--report-border) !important;
    color: var(--report-text) !important;
  }}

  td {{
    border-color: var(--report-border) !important;
    color: var(--report-text) !important;
  }}

  tbody tr:nth-child(even) {{
    background: var(--report-table-alt) !important;
  }}

  .status-pass {{
    color: var(--report-pass) !important;
  }}

  .status-fail {{
    color: var(--report-fail) !important;
  }}

  .service-dashboard {{
    margin-top: 24px;
  }}

  .service-dashboard-toolbar {{
    display: flex;
    align-items: end;
    justify-content: space-between;
    gap: 20px;
    flex-wrap: wrap;

    margin-bottom: 20px;
  }}

  .service-selector-group {{
    min-width: min(100%, 420px);
  }}

  .service-selector-group label {{
    display: block;

    margin-bottom: 7px;

    color: var(--report-muted);

    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }}

  .service-selector {{
    width: 100%;
    min-height: 44px;

    padding: 9px 38px 9px 12px;

    border: 1px solid var(--report-border);
    border-radius: 10px;

    background: var(--report-input-bg);
    color: var(--report-text);

    font: inherit;
    font-weight: 650;

    cursor: pointer;
  }}

  .service-selector:focus {{
    outline: 2px solid var(--report-response);
    outline-offset: 2px;
  }}

  .service-context {{
    color: var(--report-muted);

    font-size: 13px;
  }}

  .service-kpis {{
    display: grid;
    grid-template-columns:
      repeat(7, minmax(110px, 1fr));
    gap: 12px;

    margin-bottom: 22px;
  }}

  .service-kpi {{
    min-height: 92px;

    padding: 15px;

    border: 1px solid var(--report-border);
    border-radius: 12px;

    background: var(--report-panel-soft);
  }}

  .service-kpi-label {{
    margin-bottom: 9px;

    color: var(--report-muted);

    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.07em;
    text-transform: uppercase;
  }}

  .service-kpi-value {{
    color: var(--report-text);

    font-size: 22px;
    font-weight: 800;
    line-height: 1.15;
  }}

  .interactive-chart-grid {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 18px;
  }}

  .interactive-chart-grid
  .service-chart-panel:last-child {{
    grid-column: 1 / -1;
  }}

  .service-chart-panel {{
    min-width: 0;

    padding: 18px;

    border: 1px solid var(--report-border);
    border-radius: 14px;

    background: var(--report-panel);
  }}

  .service-chart-panel h3 {{
    margin: 0 0 12px;
  }}

  .service-chart {{
    width: 100%;
    min-height: 260px;
  }}

  .service-chart svg {{
    display: block;
    width: 100%;
    height: auto;
  }}

  .chart-empty {{
    display: flex;
    align-items: center;
    justify-content: center;

    min-height: 220px;

    color: var(--report-muted);
  }}

  .legacy-global-charts {{
    display: none !important;
  }}

  @media (max-width: 1250px) {{
    .service-kpis {{
      grid-template-columns:
        repeat(4, minmax(120px, 1fr));
    }}
  }}

  @media (max-width: 900px) {{
    .interactive-chart-grid {{
      grid-template-columns: 1fr;
    }}

    .interactive-chart-grid
    .service-chart-panel:last-child {{
      grid-column: auto;
    }}

    .service-kpis {{
      grid-template-columns:
        repeat(2, minmax(120px, 1fr));
    }}
  }}

  @media (max-width: 560px) {{
    .service-kpis {{
      grid-template-columns: 1fr;
    }}
  }}


  /* ==========================================================
     FINAL THEME HARDENING v1

     Goals:
     - Light mode must never leave dark context cards.
     - Text must always inherit the appropriate theme color.
     - No scenario/service names are referenced here.
     - Charts continue using the existing theme variables.
     ========================================================== */

  html[data-theme="light"] {{
    color-scheme: light;
  }}

  html[data-theme="dark"] {{
    color-scheme: dark;
  }}

  /*
   * Generic report surfaces.
   */
  html[data-theme="light"] .panel,
  html[data-theme="light"] .card,
  html[data-theme="light"] .metric-card,
  html[data-theme="light"] .summary-card,
  html[data-theme="light"] .service-kpi,
  html[data-theme="light"] .service-chart-panel {{
    background-color: var(--report-panel) !important;
    border-color: var(--report-border) !important;
    color: var(--report-text) !important;
  }}

  /*
   * Context / metadata containers.
   *
   * Different report versions may call these meta, metadata,
   * context, info, overview or hero cards. Attribute selectors
   * keep the theme portable across those layouts.
   */
  html[data-theme="light"] [class*="meta"],
  html[data-theme="light"] [class*="metadata"],
  html[data-theme="light"] [class*="context"],
  html[data-theme="light"] [class*="info-card"],
  html[data-theme="light"] [class*="overview-card"] {{
    background-color: var(--report-card) !important;
    border-color: var(--report-border) !important;
    color: var(--report-text) !important;
  }}

  /*
   * Common grid children used by report header/context sections.
   * Only direct card-like children are normalized.
   */
  html[data-theme="light"] [class*="meta"] > *,
  html[data-theme="light"] [class*="metadata"] > *,
  html[data-theme="light"] [class*="context"] > *,
  html[data-theme="light"] [class*="overview"] > * {{
    background-color: var(--report-card) !important;
    border-color: var(--report-border) !important;
    color: var(--report-text) !important;
  }}

  /*
   * Text inside themed surfaces must inherit the surface color
   * instead of retaining a dark-only hardcoded value.
   */
  html[data-theme="light"] .panel *,
  html[data-theme="light"] .card *,
  html[data-theme="light"] .metric-card *,
  html[data-theme="light"] .summary-card *,
  html[data-theme="light"] [class*="meta"] *,
  html[data-theme="light"] [class*="metadata"] *,
  html[data-theme="light"] [class*="context"] *,
  html[data-theme="light"] [class*="overview-card"] * {{
    color: inherit;
  }}

  /*
   * Secondary labels receive explicit muted contrast.
   */
  html[data-theme="light"] .card-label,
  html[data-theme="light"] .service-kpi-label,
  html[data-theme="light"] [class*="label"],
  html[data-theme="light"] .muted {{
    color: var(--report-muted) !important;
  }}

  /*
   * Restore primary values after the generic label rule.
   */
  html[data-theme="light"] .card-value,
  html[data-theme="light"] .service-kpi-value,
  html[data-theme="light"] td,
  html[data-theme="light"] strong {{
    color: var(--report-text) !important;
  }}

  /*
   * Tables.
   */
  html[data-theme="light"] table {{
    background-color: var(--report-panel) !important;
    color: var(--report-text) !important;
  }}

  html[data-theme="light"] thead,
  html[data-theme="light"] th {{
    background-color: var(--report-table-head) !important;
    color: var(--report-text) !important;
  }}

  html[data-theme="light"] tbody tr {{
    background-color: var(--report-panel) !important;
  }}

  html[data-theme="light"] tbody tr:nth-child(even) {{
    background-color: var(--report-table-alt) !important;
  }}

  /*
   * Inputs.
   */
  html[data-theme="light"] select,
  html[data-theme="light"] .service-selector,
  html[data-theme="light"] button {{
    background-color: var(--report-input-bg) !important;
    border-color: var(--report-border) !important;
    color: var(--report-text) !important;
  }}

  /*
   * Semantic colors must NOT be flattened by generic inheritance.
   */
  html[data-theme="light"] .status-pass {{
    color: var(--report-pass) !important;
  }}

  html[data-theme="light"] .status-fail {{
    color: var(--report-fail) !important;
  }}

  /*
   * Theme toggle itself.
   */
  html[data-theme="light"] .theme-toggle {{
    background-color: #ffffff !important;
    border-color: var(--report-border) !important;
    color: var(--report-text) !important;
  }}

  /*
   * Dark mode explicit normalization as well. This prevents a
   * future light-only rule from leaving components inconsistent.
   */
  html[data-theme="dark"] .panel,
  html[data-theme="dark"] .card,
  html[data-theme="dark"] .metric-card,
  html[data-theme="dark"] .summary-card,
  html[data-theme="dark"] .service-kpi,
  html[data-theme="dark"] .service-chart-panel {{
    background-color: var(--report-panel) !important;
    border-color: var(--report-border) !important;
    color: var(--report-text) !important;
  }}

  /* FINAL THEME HARDENING v1 */




/* ==========================================================
   PERFORMANCE REPORT - MODERN UI V4
   ========================================================== */

:root {{
  --pe-bg: #f5f8fc;
  --pe-card: #ffffff;
  --pe-card-soft: #f8fbff;

  --pe-text: #101828;
  --pe-text-2: #475467;
  --pe-muted: #667085;

  --pe-border: #dfe7f2;
  --pe-border-2: #e9eff7;

  --pe-blue: #2970ff;
  --pe-blue-soft: #eef4ff;

  --pe-green: #12b76a;
  --pe-green-soft: #ecfdf3;

  --pe-cyan: #06aed4;
  --pe-cyan-soft: #ecfdff;

  --pe-orange: #f79009;
  --pe-orange-soft: #fff7e8;

  --pe-purple: #6938ef;
  --pe-purple-soft: #f4f0ff;

  --pe-red: #f04438;
  --pe-red-soft: #fff1f0;

  --pe-shadow:
    0 8px 28px rgba(16, 24, 40, .055);

  --pe-radius: 16px;

  --background: var(--pe-bg);
  --surface: var(--pe-card);
  --border: var(--pe-border);
  --text: var(--pe-text);
  --muted: var(--pe-muted);
  --blue: var(--pe-blue);
  --green: var(--pe-green);
  --red: var(--pe-red);
  --yellow: var(--pe-orange);
}}

[data-theme="dark"] {{
  --pe-bg: #09111f;
  --pe-card: #111c2e;
  --pe-card-soft: #152238;

  --pe-text: #f7f9fc;
  --pe-text-2: #c7d2e3;
  --pe-muted: #98a9c0;

  --pe-border: #243752;
  --pe-border-2: #1f3049;

  --pe-blue-soft: rgba(41,112,255,.13);
  --pe-green-soft: rgba(18,183,106,.13);
  --pe-cyan-soft: rgba(6,174,212,.13);
  --pe-orange-soft: rgba(247,144,9,.13);
  --pe-purple-soft: rgba(105,56,239,.14);
  --pe-red-soft: rgba(240,68,56,.13);

  --pe-shadow:
    0 12px 30px rgba(0,0,0,.20);

  --background: var(--pe-bg);
  --surface: var(--pe-card);
  --border: var(--pe-border);
  --text: var(--pe-text);
  --muted: var(--pe-muted);
}}


/* PAGE */

body {{
  margin: 0;

  color: var(--pe-text);

  background:
    radial-gradient(
      circle at 86% 0%,
      rgba(41,112,255,.07),
      transparent 24%
    ),
    var(--pe-bg);

  font-family:
    Inter,
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    sans-serif;
}}

.container {{
  width: min(
    1480px,
    calc(100% - 48px)
  );

  margin: 0 auto;

  padding:
    18px
    0
    40px;
}}


/* TOP BAR */

.pe-topbar {{
  height: 66px;

  position: sticky;
  top: 0;
  z-index: 100;

  display: flex;
  align-items: center;
  justify-content: space-between;

  padding:
    0
    max(
      26px,
      calc((100vw - 1480px) / 2)
    );

  border-bottom:
    1px solid var(--pe-border-2);

  background:
    color-mix(
      in srgb,
      var(--pe-card) 94%,
      transparent
    );

  backdrop-filter: blur(18px);
}}

.pe-brand {{
  display: flex;
  align-items: center;
  gap: 10px;
}}

.pe-brand-icon {{
  width: 38px;
  height: 38px;

  color: var(--pe-blue);
}}

.pe-brand-title {{
  color: var(--pe-text);

  font-size: 16px;
  font-weight: 850;

  letter-spacing: .015em;
}}

.pe-brand-subtitle {{
  margin-top: 2px;

  color: var(--pe-muted);

  font-size: 11px;
}}

.pe-theme-segment {{
  display: flex;

  padding: 3px;

  border:
    1px solid var(--pe-border);

  border-radius: 999px;

  background: var(--pe-card-soft);
}}

.pe-theme-option {{
  min-height: 32px;

  display: flex;
  align-items: center;

  gap: 6px;

  padding:
    0
    12px;

  border: 0;
  border-radius: 999px;

  cursor: pointer;

  color: var(--pe-muted);

  background: transparent;

  font:
    inherit;

  font-size: 11px;
  font-weight: 750;
}}

.pe-theme-option.is-active {{
  color: var(--pe-blue);

  background: var(--pe-card);

  box-shadow:
    0 2px 8px rgba(16,24,40,.08);
}}

.pe-topbar-actions {{
  margin-right: 150px;
}}

.report-toolbar {{
  display: none !important;
}}


/* PDF */

.performance-pdf-export-button-v4,
a[class*="performance-pdf-export-button"] {{
  top: 11px !important;

  right:
    max(
      26px,
      calc((100vw - 1480px) / 2)
    ) !important;

  bottom: auto !important;

  min-height: 42px;

  padding:
    0
    19px !important;

  border:
    0 !important;

  border-radius:
    999px !important;

  background:
    linear-gradient(
      135deg,
      #2970ff,
      #6047ff
    ) !important;

  box-shadow:
    0 7px 18px
    rgba(41,112,255,.20)
    !important;

  font-size:
    12px !important;

  font-weight:
    800 !important;
}}


/* HERO */

.header {{
  min-height: 230px;

  position: relative;
  overflow: hidden;

  padding:
    26px
    28px
    80px;

  border:
    1px solid #d7e4f6;

  border-radius:
    18px;

  background:
    radial-gradient(
      circle at 20% -30%,
      rgba(105,56,239,.08),
      transparent 34%
    ),
    linear-gradient(
      120deg,
      #fbfdff,
      #f4f8ff 54%,
      #eef5ff
    );

  box-shadow: var(--pe-shadow);
}}

[data-theme="dark"] .header {{
  border-color:
    #263b5a;

  background:
    radial-gradient(
      circle at 20% -30%,
      rgba(105,56,239,.17),
      transparent 34%
    ),
    linear-gradient(
      120deg,
      #132039,
      #101b30 54%,
      #12233d
    );
}}

.header::before,
.header::after {{
  content: "";

  position: absolute;

  border-radius: 50%;

  border-top:
    2px solid
    rgba(41,112,255,.24);
}}

.header::before {{
  width: 500px;
  height: 230px;

  right: -70px;
  bottom: -142px;

  transform:
    rotate(-5deg);
}}

.header::after {{
  width: 445px;
  height: 210px;

  right: 85px;
  bottom: -145px;

  border-color:
    rgba(105,56,239,.20);

  transform:
    rotate(8deg);
}}

.header > * {{
  position: relative;
  z-index: 2;
}}

.eyebrow {{
  display: inline-flex;

  padding:
    5px
    11px;

  border-radius:
    999px;

  color: var(--pe-blue);

  background:
    var(--pe-blue-soft);

  font-size:
    9px;

  font-weight:
    850;
}}

h1 {{
  max-width: 900px;

  margin:
    13px
    0
    7px;

  color:
    var(--pe-text);

  font-size:
    clamp(
      31px,
      3.1vw,
      42px
    );

  line-height: 1.05;

  letter-spacing:
    -.035em;
}}

.subtitle {{
  max-width: 760px;

  color:
    var(--pe-text-2);

  font-size:
    13px;

  line-height:
    1.55;
}}

.verdict {{
  min-width: 145px;

  padding:
    12px
    17px;

  border-radius:
    15px;

  font-size:
    14px;

  font-weight:
    850;
}}

.verdict-pass {{
  color:
    #079455;

  border:
    1px solid #c7f0dc;

  background:
    #ecfdf3;
}}

.verdict-fail {{
  color:
    #d92d20;

  border:
    1px solid #ffd1cd;

  background:
    #fff1f0;
}}

[data-theme="dark"]
.verdict-pass {{
  color:
    #6ce9a6;

  border-color:
    rgba(18,183,106,.32);

  background:
    rgba(18,183,106,.13);
}}


/* HERO METADATA */

.metadata {{
  margin:
    -67px
    0
    16px;

  padding:
    0
    20px
    13px;

  position: relative;
  z-index: 5;

  display: grid;

  grid-template-columns:
    1fr
    1.45fr
    1.25fr
    1.8fr;

  gap: 10px;
}}

.metadata-item {{
  min-width: 0;
  min-height: 65px;

  padding:
    12px
    14px;

  border:
    1px solid var(--pe-border);

  border-radius:
    11px;

  background:
    color-mix(
      in srgb,
      var(--pe-card) 91%,
      transparent
    );

  backdrop-filter:
    blur(12px);

  box-shadow: none;
}}

.metadata-item::before {{
  display: none;
}}

.metadata-label {{
  color:
    var(--pe-muted);

  font-size:
    10px;

  font-weight:
    700;

  text-transform:
    none;
}}

.metadata-value {{
  margin-top:
    4px;

  color:
    var(--pe-text);

  font-size:
    12px;

  font-weight:
    730;

  line-height:
    1.35;

  overflow-wrap:
    anywhere;
}}


/* KPI CARDS */

.cards {{
  display: grid;

  grid-template-columns:
    repeat(
      5,
      minmax(0,1fr)
    );

  gap: 12px;

  margin:
    0
    0
    16px;
}}

.card {{
  min-height: 120px;

  position: relative;
  overflow: hidden;

  padding:
    18px
    18px
    18px
    66px;

  border:
    1px solid var(--pe-border);

  border-radius:
    15px;

  background:
    var(--pe-card);

  box-shadow:
    var(--pe-shadow);
}}

.card::before {{
  position: absolute;

  left: 17px;
  top: 18px;

  width: 37px;
  height: 37px;

  display: grid;
  place-items: center;

  border-radius:
    50%;

  font-size:
    20px;

  font-weight:
    900;
}}

.card::after {{
  content: "";

  position: absolute;

  left: 67px;
  right: 16px;
  bottom: 14px;

  height: 24px;

  opacity: .95;

  background-repeat:
    no-repeat;

  background-position:
    center;

  background-size:
    100% 100%;
}}

.cards .card:nth-child(1) {{
  border-left:
    3px solid
    var(--pe-blue);
}}

.cards .card:nth-child(1)::before {{
  content: "◎";

  color:
    var(--pe-blue);

  background:
    var(--pe-blue-soft);
}}

.cards .card:nth-child(1)::after {{
  background-image:
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 180 24'%3E%3Cpolyline points='0,18 18,17 32,11 49,15 66,12 83,16 100,13 117,8 134,15 150,11 180,7' fill='none' stroke='%232970ff' stroke-width='2'/%3E%3C/svg%3E");
}}

.cards .card:nth-child(2) {{
  border-left:
    3px solid
    var(--pe-green);
}}

.cards .card:nth-child(2)::before {{
  content: "✓";

  color:
    var(--pe-green);

  background:
    var(--pe-green-soft);
}}

.cards .card:nth-child(2)::after {{
  background-image:
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 180 24'%3E%3Cpolyline points='0,18 20,16 33,10 47,18 63,12 77,16 92,11 109,17 128,14 146,18 180,7' fill='none' stroke='%2312b76a' stroke-width='2'/%3E%3C/svg%3E");
}}

.cards .card:nth-child(3) {{
  border-left:
    3px solid
    var(--pe-cyan);
}}

.cards .card:nth-child(3)::before {{
  content: "ϟ";

  color:
    var(--pe-cyan);

  background:
    var(--pe-cyan-soft);
}}

.cards .card:nth-child(3)::after {{
  background-image:
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 180 24'%3E%3Cpolyline points='0,18 18,13 35,17 51,8 67,16 83,10 100,15 117,12 134,17 153,8 180,15' fill='none' stroke='%2306aed4' stroke-width='2'/%3E%3C/svg%3E");
}}

.cards .card:nth-child(4) {{
  border-left:
    3px solid
    var(--pe-orange);
}}

.cards .card:nth-child(4)::before {{
  content: "◷";

  color:
    var(--pe-orange);

  background:
    var(--pe-orange-soft);
}}

.cards .card:nth-child(4)::after {{
  background-image:
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 180 24'%3E%3Cpolyline points='0,18 18,15 35,8 54,14 72,17 89,12 108,15 125,9 145,17 180,10' fill='none' stroke='%23f79009' stroke-width='2'/%3E%3C/svg%3E");
}}

.cards .card:nth-child(5) {{
  border-left:
    3px solid
    var(--pe-purple);
}}

.cards .card:nth-child(5)::before {{
  content: "◷";

  color:
    var(--pe-purple);

  background:
    var(--pe-purple-soft);
}}

.cards .card:nth-child(5)::after {{
  background-image:
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 180 24'%3E%3Cpolyline points='0,17 19,12 35,17 51,8 68,17 84,10 103,15 121,9 140,16 158,9 180,14' fill='none' stroke='%236938ef' stroke-width='2'/%3E%3C/svg%3E");
}}

.card-label {{
  color:
    var(--pe-muted);

  font-size:
    11px;

  font-weight:
    650;

  text-transform:
    none;
}}

.card-value {{
  margin-top:
    5px;

  color:
    var(--pe-text);

  font-size:
    27px;

  font-weight:
    850;

  line-height:
    1.1;

  white-space:
    nowrap;
}}


/* GENERIC PANELS */

.panel,
.service-dashboard,
.performance-observability-v4 {{
  border:
    1px solid
    var(--pe-border) !important;

  border-radius:
    var(--pe-radius) !important;

  background:
    var(--pe-card) !important;

  box-shadow:
    var(--pe-shadow) !important;
}}

.panel {{
  margin-bottom:
    14px;

  padding:
    18px;
}}

.panel h2,
.service-dashboard h2 {{
  margin:
    0
    0
    12px;

  color:
    var(--pe-text);

  font-size:
    15px;

  font-weight:
    820;
}}


/* OBSERVABILITY */

.performance-observability-v4 {{
  margin:
    0
    0
    16px !important;

  padding:
    18px !important;
}}

.performance-observability-v4 h2 {{
  font-size:
    17px !important;

  color:
    var(--pe-text) !important;
}}

.performance-observability-v4 p {{
  color:
    var(--pe-muted) !important;

  font-size:
    12px !important;
}}

.performance-observability-v4
.perf-obs-grid {{
  gap:
    10px !important;
}}

.performance-observability-v4
.perf-obs-link {{
  min-height:
    65px;

  position:
    relative;

  padding:
    12px
    42px
    12px
    52px !important;

  border:
    1px solid
    var(--pe-border) !important;

  border-radius:
    11px !important;

  background:
    var(--pe-card-soft) !important;
}}

.performance-observability-v4
.perf-obs-link::before {{
  position:
    absolute;

  left:
    15px;

  top:
    50%;

  transform:
    translateY(-50%);

  width:
    28px;

  height:
    28px;

  display:
    grid;

  place-items:
    center;

  border-radius:
    50%;

  font-weight:
    900;
}}

.performance-observability-v4
.perf-obs-link:nth-child(1)::before {{
  content: "G";

  color:
    #f79009;

  background:
    var(--pe-orange-soft);
}}

.performance-observability-v4
.perf-obs-link:nth-child(2)::before {{
  content: "P";

  color:
    #e5484d;

  background:
    var(--pe-red-soft);
}}

.performance-observability-v4
.perf-obs-link:nth-child(3)::before {{
  content: "▥";

  color:
    var(--pe-purple);

  background:
    var(--pe-purple-soft);
}}

.performance-observability-v4
.perf-obs-link::after {{
  content: "›";

  position:
    absolute;

  right:
    16px;

  top:
    50%;

  transform:
    translateY(-50%);

  color:
    var(--pe-blue);

  font-size:
    22px;
}}

.performance-observability-v4
.perf-obs-link strong {{
  color:
    var(--pe-text) !important;

  font-size:
    12px !important;
}}

.performance-observability-v4
.perf-obs-link span {{
  color:
    var(--pe-muted) !important;

  font-size:
    10px !important;
}}


/* TABLES */

.table-scroll {{
  overflow:
    auto;

  border:
    1px solid
    var(--pe-border-2);

  border-radius:
    10px;
}}

table {{
  width:
    100%;

  border-collapse:
    separate;

  border-spacing:
    0;
}}

thead th {{
  padding:
    10px
    11px;

  color:
    #344054;

  background:
    #eef3f9;

  border-bottom:
    1px solid
    var(--pe-border);

  font-size:
    10px;

  font-weight:
    800;

  text-transform:
    none;

  letter-spacing:
    0;

  white-space:
    nowrap;
}}

[data-theme="dark"]
thead th {{
  color:
    #d8e2f0;

  background:
    #1b2a42;
}}

tbody td {{
  padding:
    10px
    11px;

  color:
    var(--pe-text);

  border-bottom:
    1px solid
    var(--pe-border-2);

  font-size:
    11px;

  line-height:
    1.4;
}}

tbody tr:last-child td {{
  border-bottom:
    0;
}}

.status-pass {{
  display:
    inline-flex;

  padding:
    3px
    8px;

  color:
    #079455 !important;

  border-radius:
    999px;

  background:
    #dcfae6;

  font-size:
    9px;

  font-weight:
    850;
}}

.status-fail {{
  display:
    inline-flex;

  padding:
    3px
    8px;

  color:
    #d92d20 !important;

  border-radius:
    999px;

  background:
    #fee4e2;

  font-size:
    9px;

  font-weight:
    850;
}}


/* TWO-COLUMN ANALYSIS GRID */

.pe-analysis-grid {{
  display:
    grid;

  grid-template-columns:
    minmax(0, 2fr)
    minmax(310px, .95fr);

  gap:
    14px;

  margin-bottom:
    16px;
}}

.pe-analysis-left,
.pe-analysis-right {{
  min-width:
    0;
}}

.pe-analysis-grid
.panel {{
  margin-bottom:
    14px;
}}

.pe-analysis-grid
.panel:last-child {{
  margin-bottom:
    0;
}}


/* SERVICE / TRENDS */

.service-dashboard {{
  padding:
    18px;

  margin-bottom:
    16px;
}}

.service-dashboard-toolbar {{
  padding-bottom:
    12px;

  margin-bottom:
    14px;

  border-bottom:
    1px solid
    var(--pe-border-2);
}}

.service-kpis {{
  gap:
    8px;
}}

.service-kpi {{
  min-height:
    70px;

  padding:
    11px;

  border:
    1px solid
    var(--pe-border-2);

  border-radius:
    10px;

  background:
    var(--pe-card-soft);
}}

.service-kpi-label {{
  color:
    var(--pe-muted);

  font-size:
    9px;
}}

.service-kpi-value {{
  margin-top:
    4px;

  color:
    var(--pe-text);

  font-size:
    17px;

  font-weight:
    800;
}}

.interactive-chart-grid {{
  display:
    grid;

  grid-template-columns:
    repeat(3,minmax(0,1fr));

  gap:
    10px;

  margin-top:
    14px;
}}

.service-chart-panel {{
  padding:
    13px;

  border:
    1px solid
    var(--pe-border-2);

  border-radius:
    11px;

  background:
    var(--pe-card-soft);
}}

.service-chart-panel h3 {{
  margin:
    0
    0
    8px;

  color:
    var(--pe-text);

  font-size:
    11px;
}}

.service-chart {{
  min-height:
    225px;
}}

.service-chart svg text {{
  font-size:
    10px !important;
}}


/* RECOMMENDATIONS */

.pe-recommendations {{
  border-color:
    #ccefdc !important;

  background:
    linear-gradient(
      90deg,
      rgba(18,183,106,.045),
      transparent
    ),
    var(--pe-card) !important;
}}

.pe-recommendations ul {{
  display:
    grid;

  grid-template-columns:
    repeat(3,minmax(0,1fr));

  gap:
    10px;

  padding:
    0;

  margin:
    0;

  list-style:
    none;
}}

.pe-recommendations li {{
  position:
    relative;

  padding-left:
    18px;

  color:
    var(--pe-text-2);

  font-size:
    10px;
}}

.pe-recommendations li::before {{
  content:
    "";

  width:
    7px;

  height:
    7px;

  position:
    absolute;

  left:
    0;

  top:
    6px;

  border-radius:
    50%;

  background:
    var(--pe-green);
}}


/* DARK POLISH */

[data-theme="dark"]
.performance-observability-v4
.perf-obs-link,
[data-theme="dark"]
.service-kpi,
[data-theme="dark"]
.service-chart-panel {{
  background:
    var(--pe-card-soft) !important;
}}

[data-theme="dark"]
.status-pass {{
  color:
    #6ce9a6 !important;

  background:
    rgba(18,183,106,.14);
}}

[data-theme="dark"]
.status-fail {{
  color:
    #fda29b !important;

  background:
    rgba(240,68,56,.15);
}}


/* RESPONSIVE */

@media (max-width: 1150px) {{
  .cards {{
    grid-template-columns:
      repeat(3,minmax(0,1fr));
  }}

  .metadata {{
    grid-template-columns:
      repeat(2,minmax(0,1fr));
  }}

  .pe-analysis-grid {{
    grid-template-columns:
      1fr;
  }}

  .interactive-chart-grid {{
    grid-template-columns:
      1fr;
  }}
}}

@media (max-width: 720px) {{
  .container {{
    width:
      min(
        100% - 20px,
        1480px
      );
  }}

  .header {{
    padding:
      22px
      18px
      145px;
  }}

  h1 {{
    font-size:
      30px;
  }}

  .metadata {{
    margin-top:
      -132px;

    grid-template-columns:
      1fr;
  }}

  .cards {{
    grid-template-columns:
      1fr;
  }}

  .pe-recommendations ul {{
    grid-template-columns:
      1fr;
  }}
}}


/* ==========================================================
   PERFORMANCE REPORT - ERROR VISUALIZATION V4.1
   ========================================================== */

/* Response code badges */

.pe-response-codes {{
  display: flex;
  flex-wrap: wrap;
  align-items: stretch;
  gap: 7px;
}}

.pe-http-code {{
  min-width: 78px;

  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;

  gap: 1px;

  padding: 6px 9px;

  border: 1px solid transparent;
  border-radius: 10px;

  line-height: 1.15;
}}

.pe-http-code-name {{
  font-size: 10px;
  font-weight: 850;
}}

.pe-http-code-count {{
  font-size: 13px;
  font-weight: 850;
}}

.pe-http-code-rate {{
  margin-top: 2px;

  font-size: 9px;
  font-weight: 650;
  opacity: .9;
}}


/* 2xx */

.pe-http-code-success {{
  color: #079455;
  border-color: #c8efdc;
  background: #ecfdf3;
}}


/* 3xx */

.pe-http-code-redirect {{
  color: #175cd3;
  border-color: #c7d7fe;
  background: #eff4ff;
}}


/* 4xx */

.pe-http-code-client {{
  color: #b54708;
  border-color: #fedf89;
  background: #fffaeb;
}}


/* 5xx */

.pe-http-code-server {{
  color: #d92d20;
  border-color: #fecdca;
  background: #fef3f2;
}}


/* Transaction with errors */

.pe-transaction-failed td {{
  background:
    linear-gradient(
      90deg,
      rgba(240, 68, 56, .040),
      transparent 75%
    );
}}

.pe-transaction-failed td:first-child {{
  box-shadow:
    inset 3px 0 0 #f04438;
}}


/* Status badge */

}}

}}


/* Error panel */

.pe-transaction-errors.pe-has-errors {{
  position: relative;

  border-color: #fecdca !important;

  background:
    linear-gradient(
      180deg,
      rgba(240, 68, 56, .025),
      transparent 45%
    ),
    var(--pe-card) !important;
}}

.pe-transaction-errors.pe-has-errors h2 {{
  color: var(--pe-text);
}}


/* Error code in detailed table */

.pe-error-code-badge {{
  display: inline-flex;
  align-items: center;
  justify-content: center;

  min-width: 44px;

  padding: 4px 9px;

  border-radius: 999px;

  color: #d92d20;

  background: #fee4e2;

  font-weight: 850;
}}


/* Error summary alert */

.pe-error-alert {{
  margin-top: 13px;

  display: flex;
  align-items: center;
  justify-content: space-between;

  gap: 16px;

  padding: 12px 15px;

  border: 1px solid #fda29b;
  border-radius: 12px;

  background:
    linear-gradient(
      90deg,
      #fff1f0,
      #fff8f7
    );
}}

.pe-error-alert-content {{
  min-width: 0;

  display: flex;
  align-items: center;

  gap: 12px;
}}

.pe-error-alert-icon {{
  width: 34px;
  height: 34px;

  flex: 0 0 auto;

  display: grid;
  place-items: center;

  border-radius: 50%;

  color: #fff;
  background: #f04438;

  font-size: 19px;
  font-weight: 900;
}}

.pe-error-alert-title {{
  color: #d92d20;

  font-size: 12px;
  font-weight: 850;
}}

.pe-error-alert-description {{
  margin-top: 2px;

  color: #667085;

  font-size: 10px;
  line-height: 1.4;
}}


/* Dark mode */

[data-theme="dark"] .pe-http-code-success {{
  color: #6ce9a6;

  border-color:
    rgba(18, 183, 106, .30);

  background:
    rgba(18, 183, 106, .12);
}}

[data-theme="dark"] .pe-http-code-redirect {{
  color: #84adff;

  border-color:
    rgba(41, 112, 255, .32);

  background:
    rgba(41, 112, 255, .13);
}}

[data-theme="dark"] .pe-http-code-client {{
  color: #fec84b;

  border-color:
    rgba(247, 144, 9, .30);

  background:
    rgba(247, 144, 9, .12);
}}

[data-theme="dark"] .pe-http-code-server {{
  color: #fda29b;

  border-color:
    rgba(240, 68, 56, .32);

  background:
    rgba(240, 68, 56, .13);
}}

}}

[data-theme="dark"] .pe-error-code-badge {{
  color: #fda29b;

  background:
    rgba(240, 68, 56, .14);
}}

[data-theme="dark"]
.pe-transaction-errors.pe-has-errors {{
  border-color:
    rgba(240, 68, 56, .35) !important;

  background:
    linear-gradient(
      180deg,
      rgba(240, 68, 56, .075),
      transparent 50%
    ),
    var(--pe-card) !important;
}}

[data-theme="dark"] .pe-error-alert {{
  border-color:
    rgba(240, 68, 56, .38);

  background:
    linear-gradient(
      90deg,
      rgba(240, 68, 56, .14),
      rgba(240, 68, 56, .06)
    );
}}

[data-theme="dark"]
.pe-error-alert-description {{
  color: var(--pe-muted);
}}


/* Responsive */

@media (max-width: 760px) {{
  .pe-error-alert {{
    align-items: flex-start;
  }}

  .pe-response-codes {{
    min-width: 180px;
  }}
}}

</style>

<script>
(function () {{
  const storageKey =
    "performance-report-theme";

  let theme = null;

  try {{
    theme = localStorage.getItem(
      storageKey
    );
  }} catch (error) {{
    theme = null;
  }}

  if (
    theme !== "dark"
    && theme !== "light"
  ) {{
    theme = (
      window.matchMedia
      && window.matchMedia(
        "(prefers-color-scheme: light)"
      ).matches
    )
      ? "light"
      : "dark";
  }}

  document.documentElement
    .setAttribute(
      "data-theme",
      theme
    );
}})();
</script>


<style id="pe-v42-color-adjustments">

.pe-transaction-failed td {{
  background:
    rgba(
      240,
      68,
      56,
      .055
    );
}}

.pe-transaction-failed td:first-child {{
  box-shadow:
    inset 4px 0 0
    #ef233c;
}}

.pe-transaction-success td:first-child {{
  box-shadow:
    inset 4px 0 0
    #00b86b;
}}

.pe-http-code-success {{
  color: #067647 !important;

  border:
    1px solid
    #75e0a7 !important;

  background:
    #dcfae6 !important;
}}

.pe-http-code-server {{
  color: #b42318 !important;

  border:
    1px solid
    #f97066 !important;

  background:
    #fee4e2 !important;
}}

.pe-error-code-badge {{
  color: #ffffff !important;

  background:
    #ef233c !important;

  border:
    1px solid
    #d90429 !important;
}}

.pe-transaction-errors.pe-has-errors {{
  border:
    1px solid
    #f97066 !important;

  box-shadow:
    inset 4px 0 0
    #ef233c,
    var(--pe-shadow) !important;
}}

.pe-error-alert {{
  border:
    1px solid
    #f97066 !important;

  background:
    linear-gradient(
      90deg,
      #fee4e2,
      #fff4f2
    ) !important;
}}

.pe-error-alert-icon {{
  background:
    #ef233c !important;
}}

.pe-error-alert-title {{
  color:
    #b42318 !important;
}}

[data-theme="dark"]
.pe-transaction-failed td {{
  background:
    rgba(
      239,
      35,
      60,
      .10
    );
}}

[data-theme="dark"]
.pe-http-code-success {{
  color:
    #75e0a7 !important;

  border-color:
    #079455 !important;

  background:
    rgba(
      0,
      184,
      107,
      .16
    ) !important;
}}

[data-theme="dark"]
.pe-http-code-server {{
  color:
    #fda29b !important;

  border-color:
    #ef233c !important;

  background:
    rgba(
      239,
      35,
      60,
      .17
    ) !important;
}}

[data-theme="dark"]
.pe-error-alert {{
  background:
    rgba(
      239,
      35,
      60,
      .12
    ) !important;
}}

</style>

</head>


<body>

<div class="pe-topbar">
  <div class="pe-brand">
    <div class="pe-brand-icon" aria-hidden="true">
      <svg viewBox="0 0 48 48">
        <polyline
          points="2,25 8,25 12,12 17,38 22,7 27,33 31,18 35,25 46,25"
          fill="none"
          stroke="currentColor"
          stroke-width="3.3"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </div>

    <div class="pe-brand-copy">
      <div class="pe-brand-title">
        PERFORMANCE ENGINEERING
      </div>
      <div class="pe-brand-subtitle">
        Reporte automatizado de pruebas de performance
      </div>
    </div>
  </div>

  <div class="pe-topbar-actions">
    <div class="pe-theme-segment">
      <button
        type="button"
        class="pe-theme-option"
        data-theme-choice="light"
      >
        ☀
        <span>Claro</span>
      </button>

      <button
        type="button"
        class="pe-theme-option"
        data-theme-choice="dark"
      >
        ◐
        <span>Oscuro</span>
      </button>
    </div>
  </div>
</div>


  <div class="report-toolbar">
    <button
      id="theme-toggle"
      class="theme-toggle"
      type="button"
      aria-label="Cambiar tema del reporte"
      title="Cambiar tema"
    >
      <span
        id="theme-toggle-icon"
        class="theme-toggle-icon"
        aria-hidden="true"
      ></span>

      <span id="theme-toggle-label">
        Theme
      </span>
    </button>
  </div>

<div class="container">

  <header class="header">
    <div>
      <div class="eyebrow">
        REPORTE DE PRUEBA DE PERFORMANCE
      </div>

      <h1>Resultados de la prueba de performance</h1>

      <div class="subtitle">
        Resultados de la prueba de performance generados a partir de
        métricas de ejecución, criterios SLA y análisis automatizado.
      </div>
    </div>

    <div class="verdict {verdict_class}">
      {verdict}
    </div>
  </header>

  <section class="metadata">
    <div class="metadata-item">
      <div class="metadata-label">Escenario</div>
      <div class="metadata-value">{scenario}</div>
    </div>

    <div class="metadata-item">
      <div class="metadata-label">Objetivo</div>
      <div class="metadata-value">{target}</div>
    </div>

    <div class="metadata-item">
      <div class="metadata-label">Generado</div>
      <div class="metadata-value">{generated_at}</div>
    </div>

    <div class="metadata-item">
      <div class="metadata-label">Fuente</div>
      <div class="metadata-value">{source}</div>
    </div>
  </section>

  <section class="cards">
    <div class="card">
      <div class="card-label">Solicitudes</div>
      <div class="card-value">{requests}</div>
    </div>

    <div class="card">
      <div class="card-label">Tasa de éxito</div>
      <div class="card-value">{success_rate}%</div>
    </div>

    <div class="card">
      <div class="card-label">Throughput</div>
      <div class="card-value">{throughput} req/s</div>
    </div>

    <div class="card">
      <div class="card-label">p95</div>
      <div class="card-value">{p95} ms</div>
    </div>

    <div class="card">
      <div class="card-label">p99</div>
      <div class="card-value">{p99} ms</div>
    </div>
  </section>

  <section class="panel pe-response-summary">
    <h2>Resumen de tiempos de respuesta</h2>

    <table>
      <thead>
        <tr>
          <th>Mínimo</th>
          <th>Promedio</th>
          <th>p50</th>
          <th>p90</th>
          <th>p95</th>
          <th>p99</th>
          <th>Máximo</th>
        </tr>
      </thead>

      <tbody>
        <tr>
          <td>{minimum}</td>
          <td>{average}</td>
          <td>{p50}</td>
          <td>{p90}</td>
          <td>{p95}</td>
          <td>{p99}</td>
          <td>{maximum}</td>
        </tr>
      </tbody>
    </table>
  </section>

  <section class="panel pe-transactions">
    <h2>Desglose por transacción / servicio</h2>

    <p class="muted">
      Métricas agrupadas por transacción o servicio.
      Las etiquetas pueden representar endpoints, servicios,
      transacciones de negocio o pasos importados.
    </p>

    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Transacción / servicio</th>
            <th>Muestras</th>
            <th>Éxito %</th>
            <th>Error %</th>
            <th>Promedio ms</th>
            <th>p90 ms</th>
            <th>p95 ms</th>
            <th>p99 ms</th>
            <th>Req/s</th>
            <th>Códigos de respuesta</th>

          </tr>
        </thead>

        <tbody>
          {transaction_rows}
        </tbody>
      </table>
    </div>
  </section>

  <section class="panel pe-transaction-errors">
    <h2>Errores por transacción / servicio</h2>

    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Transacción / servicio</th>
            <th>Errores</th>
            <th>Error %</th>
            <th>Códigos de respuesta</th>
            <th>Detalle del error</th>
          </tr>
        </thead>

        <tbody>
          {transaction_error_rows}
        </tbody>
      </table>
    </div>
  </section>

  <section class="panel service-dashboard">
    <div class="service-dashboard-toolbar">
      <div class="service-selector-group">
        <label for="service-selector">
          Transacción / servicio
        </label>

        <select
          id="service-selector"
          class="service-selector"
        ></select>
      </div>

      <div
        id="service-context"
        class="service-context"
      >
        Todas las transacciones
      </div>
    </div>

    <div class="service-kpis">
      <div class="service-kpi">
        <div class="service-kpi-label">
          Muestras
        </div>
        <div
          id="service-kpi-samples"
          class="service-kpi-value"
        >
          —
        </div>
      </div>

      <div class="service-kpi">
        <div class="service-kpi-label">
          Éxito
        </div>
        <div
          id="service-kpi-success"
          class="service-kpi-value"
        >
          —
        </div>
      </div>

      <div class="service-kpi">
        <div class="service-kpi-label">
          Tasa de error
        </div>
        <div
          id="service-kpi-errors"
          class="service-kpi-value"
        >
          —
        </div>
      </div>

      <div class="service-kpi">
        <div class="service-kpi-label">
          Promedio
        </div>
        <div
          id="service-kpi-avg"
          class="service-kpi-value"
        >
          —
        </div>
      </div>

      <div class="service-kpi">
        <div class="service-kpi-label">
          p95
        </div>
        <div
          id="service-kpi-p95"
          class="service-kpi-value"
        >
          —
        </div>
      </div>

      <div class="service-kpi">
        <div class="service-kpi-label">
          p99
        </div>
        <div
          id="service-kpi-p99"
          class="service-kpi-value"
        >
          —
        </div>
      </div>

      <div class="service-kpi">
        <div class="service-kpi-label">
          Throughput
        </div>
        <div
          id="service-kpi-throughput"
          class="service-kpi-value"
        >
          —
        </div>
      </div>
    </div>

    <div class="interactive-chart-grid">
      <div class="service-chart-panel">
        <h3>Tendencia de tiempo de respuesta</h3>
        <div
          id="service-response-chart"
          class="service-chart"
        ></div>
      </div>

      <div class="service-chart-panel">
        <h3>Tendencia de throughput</h3>
        <div
          id="service-throughput-chart"
          class="service-chart"
        ></div>
      </div>

      <div class="service-chart-panel">
        <h3>Tendencia de tasa de error</h3>
        <div
          id="service-error-chart"
          class="service-chart"
        ></div>
      </div>
    </div>
  </section>

  <script
    id="service-dashboard-data"
    type="application/json"
  >{service_dashboard_json}</script>

  <section class="panel pe-sla">
    <h2>Validación de SLA</h2>

    <table>
      <thead>
        <tr>
          <th>Validación</th>
          <th>Umbral</th>
          <th>Valor observado</th>
          <th>Resultado</th>
        </tr>
      </thead>

      <tbody>
        {checks_rows}
      </tbody>
    </table>
  </section>

  <section class="panel pe-response-errors">
    <h2>Errores por código de respuesta</h2>

    <table>
      <thead>
        <tr>
          <th>Código de respuesta</th>
          <th>Cantidad</th>
        </tr>
      </thead>

      <tbody>
        {errors_rows}
      </tbody>
    </table>
  </section>

  <section class="panel pe-recommendations">
    <h2>Recomendaciones</h2>
    <ul>
      {recommendations}
    </ul>
  </section>

  <footer class="footer">
    Performance Engineering
  </footer>

</div>

<script>
(function () {{
  const storageKey =
    "performance-report-theme";

  const button =
    document.getElementById(
      "theme-toggle"
    );

  const icon =
    document.getElementById(
      "theme-toggle-icon"
    );

  const label =
    document.getElementById(
      "theme-toggle-label"
    );

  if (!button || !icon || !label) {{
    return;
  }}

  function currentTheme() {{
    return (
      document.documentElement
        .getAttribute(
          "data-theme"
        )
      || "dark"
    );
  }}

  function render() {{
    const theme = currentTheme();

    if (theme === "dark") {{
      icon.textContent = "☀";
      label.textContent = "Claro";

      button.setAttribute(
        "aria-label",
        "Cambiar a tema claro"
      );
    }} else {{
      icon.textContent = "☾";
      label.textContent = "Oscuro";

      button.setAttribute(
        "aria-label",
        "Cambiar a tema oscuro"
      );
    }}
  }}

  button.addEventListener(
    "click",
    function () {{
      const next = (
        currentTheme() === "dark"
      )
        ? "light"
        : "dark";

      document.documentElement
        .setAttribute(
          "data-theme",
          next
        );

      try {{
        localStorage.setItem(
          storageKey,
          next
        );
      }} catch (error) {{
        // Storage may be unavailable in
        // restricted browser contexts.
      }}

      render();
    }}
  );

  render();
}})();
</script>


<script>
(function () {{
  const source =
    document.getElementById(
      "service-dashboard-data"
    );

  const selector =
    document.getElementById(
      "service-selector"
    );

  if (!source || !selector) {{
    return;
  }}

  let payload;

  try {{
    payload = JSON.parse(
      source.textContent
    );
  }} catch (error) {{
    console.error(
      "Unable to parse service dashboard data.",
      error
    );
    return;
  }}

  const globalItem =
    payload.global || {{}};

  const transactions =
    Array.isArray(
      payload.transactions
    )
      ? payload.transactions
      : [];

  const items = [
    globalItem,
    ...transactions,
  ];

  const css = function (name, fallback) {{
    const value =
      getComputedStyle(
        document.documentElement
      )
      .getPropertyValue(name)
      .trim();

    return value || fallback;
  }};

  function valueOrDash(value) {{
    return (
      value === null
      || value === undefined
      || Number.isNaN(value)
    )
      ? "—"
      : value;
  }}

  function fixed(value, digits) {{
    if (
      value === null
      || value === undefined
      || Number.isNaN(
        Number(value)
      )
    ) {{
      return "—";
    }}

    return Number(value)
      .toFixed(digits);
  }}

  function selectedItem() {{
    const index =
      Number(selector.value);

    return items[index]
      || items[0];
  }}

  function setText(id, text) {{
    const element =
      document.getElementById(id);

    if (element) {{
      element.textContent = text;
    }}
  }}

  function updateKpis(item) {{
    const response =
      item.response_time_ms || {{}};

    setText(
      "service-context",
      item.label
      || "Todas las transacciones"
    );

    setText(
      "service-kpi-samples",
      valueOrDash(
        item.samples
      )
    );

    setText(
      "service-kpi-success",
      fixed(
        item.success_rate_pct,
        2
      ) + "%"
    );

    setText(
      "service-kpi-errors",
      fixed(
        item.error_rate_pct,
        2
      ) + "%"
    );

    setText(
      "service-kpi-avg",
      fixed(
        response.avg,
        2
      ) + " ms"
    );

    setText(
      "service-kpi-p95",
      fixed(
        response.p95,
        2
      ) + " ms"
    );

    setText(
      "service-kpi-p99",
      fixed(
        response.p99,
        2
      ) + " ms"
    );

    setText(
      "service-kpi-throughput",
      fixed(
        item.throughput_req_per_sec,
        3
      ) + " req/s"
    );
  }}

  function escapeText(value) {{
    return String(
      value ?? ""
    )
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }}

  function lineChart(
    containerId,
    points,
    field,
    unit,
    colorVariable
  ) {{
    const container =
      document.getElementById(
        containerId
      );

    if (!container) {{
      return;
    }}

    const valid = points.map(
      function (point) {{
        const raw =
          point[field];

        return {{
          second:
            Number(
              point.second || 0
            ),
          value:
            raw === null
            || raw === undefined
              ? null
              : Number(raw),
        }};
      }}
    );

    const numeric =
      valid.filter(
        function (point) {{
          return (
            point.value !== null
            && Number.isFinite(
              point.value
            )
          );
        }}
      );

    if (!numeric.length) {{
      container.innerHTML =
        '<div class="chart-empty">'
        + 'Sin datos disponibles'
        + '</div>';

      return;
    }}

    const width = 900;
    const height = 280;

    const left = 62;
    const right = 22;
    const top = 24;
    const bottom = 42;

    const plotWidth =
      width - left - right;

    const plotHeight =
      height - top - bottom;

    const maxValue = Math.max(
      ...numeric.map(
        function (point) {{
          return point.value;
        }}
      ),
      1
    );

    const maxY =
      maxValue * 1.12;

    const maxSecond = Math.max(
      ...valid.map(
        function (point) {{
          return point.second;
        }}
      ),
      1
    );

    function x(second) {{
      return (
        left
        + (
          second
          / maxSecond
        )
        * plotWidth
      );
    }}

    function y(value) {{
      return (
        top
        + plotHeight
        - (
          value
          / maxY
        )
        * plotHeight
      );
    }}

    const lineColor =
      css(
        colorVariable,
        "#58a6ff"
      );

    const gridColor =
      css(
        "--report-grid",
        "#303844"
      );

    const textColor =
      css(
        "--report-axis-text",
        "#8d98a6"
      );

    let grid = "";

    for (
      let tick = 0;
      tick <= 4;
      tick += 1
    ) {{
      const value =
        maxY
        * tick
        / 4;

      const py =
        y(value);

      grid +=
        '<line x1="' + left
        + '" y1="' + py
        + '" x2="' + (width - right)
        + '" y2="' + py
        + '" stroke="' + gridColor
        + '" stroke-width="1"/>';

      grid +=
        '<text x="' + (left - 10)
        + '" y="' + (py + 4)
        + '" text-anchor="end"'
        + ' font-size="11"'
        + ' fill="' + textColor
        + '">'
        + escapeText(
          value.toFixed(
            value >= 100 ? 0 : 1
          )
        )
        + '</text>';
    }}

    let xTicks = "";

    const xStep = Math.max(
      Math.ceil(
        valid.length / 6
      ),
      1
    );

    for (
      let index = 0;
      index < valid.length;
      index += xStep
    ) {{
      const point =
        valid[index];

      xTicks +=
        '<text x="' + x(point.second)
        + '" y="' + (height - 12)
        + '" text-anchor="middle"'
        + ' font-size="11"'
        + ' fill="' + textColor
        + '">'
        + escapeText(
          point.second + "s"
        )
        + '</text>';
    }}

    const pathPoints =
      numeric.map(
        function (point) {{
          return (
            x(point.second)
            + ","
            + y(point.value)
          );
        }}
      )
      .join(" ");

    const areaPoints =
      left
      + ","
      + (top + plotHeight)
      + " "
      + pathPoints
      + " "
      + x(
        numeric[
          numeric.length - 1
        ].second
      )
      + ","
      + (top + plotHeight);

    container.innerHTML =
      '<svg viewBox="0 0 '
      + width
      + ' '
      + height
      + '" role="img">'
      + grid
      + xTicks
      + '<polygon points="'
      + areaPoints
      + '" fill="'
      + lineColor
      + '" opacity="0.10"/>'
      + '<polyline points="'
      + pathPoints
      + '" fill="none" stroke="'
      + lineColor
      + '" stroke-width="2.5"'
      + ' stroke-linecap="round"'
      + ' stroke-linejoin="round"/>'
      + '<text x="'
      + left
      + '" y="15"'
      + ' font-size="11"'
      + ' fill="'
      + textColor
      + '">'
      + escapeText(unit)
      + '</text>'
      + '</svg>';
  }}

  function renderCharts(item) {{
    const series =
      Array.isArray(
        item.time_series
      )
        ? item.time_series
        : [];

    lineChart(
      "service-response-chart",
      series,
      "avg_response_ms",
      "Tiempo promedio de respuesta (ms)",
      "--report-response"
    );

    lineChart(
      "service-throughput-chart",
      series,
      "throughput_req_per_sec",
      "Throughput (req/s)",
      "--report-throughput"
    );

    lineChart(
      "service-error-chart",
      series,
      "error_rate_pct",
      "Tasa de error (%)",
      "--report-error"
    );
  }}

  function render() {{
    const item =
      selectedItem();

    updateKpis(item);
    renderCharts(item);
  }}

  items.forEach(
    function (item, index) {{
      const option =
        document.createElement(
          "option"
        );

      option.value =
        String(index);

      option.textContent =
        item.label
        || (
          index === 0
            ? "Todas las transacciones"
            : "Transacción sin nombre"
        );

      selector.appendChild(
        option
      );
    }}
  );

  selector.addEventListener(
    "change",
    render
  );

  const themeToggle =
    document.getElementById(
      "theme-toggle"
    );

  if (themeToggle) {{
    themeToggle.addEventListener(
      "click",
      function () {{
        window.requestAnimationFrame(
          render
        );
      }}
    );
  }}

  render();
}})();
</script>


<script id="pe-modern-theme-controller">
(function () {{
  const STORAGE_KEY =
    "performance-report-theme";

  const root =
    document.documentElement;

  const buttons = Array.from(
    document.querySelectorAll(
      "[data-theme-choice]"
    )
  );

  function resolvedTheme() {{
    const explicit =
      root.getAttribute("data-theme");

    if (
      explicit === "light"
      || explicit === "dark"
    ) {{
      return explicit;
    }}

    try {{
      const saved =
        localStorage.getItem(
          STORAGE_KEY
        );

      if (
        saved === "light"
        || saved === "dark"
      ) {{
        return saved;
      }}
    }} catch (_) {{
      // Local storage may be restricted.
    }}

    return (
      window.matchMedia
      && window.matchMedia(
        "(prefers-color-scheme: dark)"
      ).matches
    )
      ? "dark"
      : "light";
  }}

  function render(theme) {{
    root.setAttribute(
      "data-theme",
      theme
    );

    buttons.forEach(
      function (button) {{
        button.classList.toggle(
          "is-active",
          button.dataset.themeChoice
            === theme
        );
      }}
    );
  }}

  function setTheme(theme) {{
    render(theme);

    try {{
      localStorage.setItem(
        STORAGE_KEY,
        theme
      );
    }} catch (_) {{
      // Local storage may be restricted.
    }}

    window.dispatchEvent(
      new Event("resize")
    );
  }}

  buttons.forEach(
    function (button) {{
      button.addEventListener(
        "click",
        function () {{
          setTheme(
            button.dataset.themeChoice
          );
        }}
      );
    }}
  );

  render(resolvedTheme());
}})();
</script>


<script id="pe-v4-layout">
(function () {{
  function byClass(name) {{
    return document.querySelector(
      "." + name
    );
  }}

  const responseSummary =
    byClass("pe-response-summary");

  const transactions =
    byClass("pe-transactions");

  const transactionErrors =
    byClass("pe-transaction-errors");

  const sla =
    byClass("pe-sla");

  const responseErrors =
    byClass("pe-response-errors");

  const serviceDashboard =
    document.querySelector(
      ".service-dashboard"
    );

  if (
    !responseSummary
    || !transactions
    || !sla
    || !responseErrors
  ) {{
    return;
  }}

  const existing =
    document.querySelector(
      ".pe-analysis-grid"
    );

  if (existing) {{
    return;
  }}

  const grid =
    document.createElement(
      "div"
    );

  grid.className =
    "pe-analysis-grid";

  const left =
    document.createElement(
      "div"
    );

  left.className =
    "pe-analysis-left";

  const right =
    document.createElement(
      "div"
    );

  right.className =
    "pe-analysis-right";

  left.appendChild(
    responseSummary
  );

  left.appendChild(
    transactions
  );

  if (transactionErrors) {{
    left.appendChild(
      transactionErrors
    );
  }}

  right.appendChild(
    sla
  );

  right.appendChild(
    responseErrors
  );

  grid.appendChild(left);
  grid.appendChild(right);

  if (serviceDashboard) {{
    serviceDashboard
      .parentNode
      .insertBefore(
        grid,
        serviceDashboard
      );
  }} else {{
    document
      .querySelector(".container")
      .appendChild(grid);
  }}
}})();
</script>





<script id="pe-error-visualization-v42">
(function () {{
  function parseNumber(value) {{
    const result = Number(
      String(value || "")
        .replace("%", "")
        .trim()
    );

    return Number.isFinite(result)
      ? result
      : 0;
  }}

  function percent(value) {{
    return Number(value || 0)
      .toFixed(2)
      + "%";
  }}

  function codeType(code) {{
    const value =
      String(code || "");

    if (value.startsWith("2")) {{
      return "success";
    }}

    if (value.startsWith("3")) {{
      return "redirect";
    }}

    if (value.startsWith("4")) {{
      return "client";
    }}

    if (value.startsWith("5")) {{
      return "server";
    }}

    return "redirect";
  }}

  function parseCodes(
    value,
    total
  ) {{
    return String(value || "")
      .split(",")
      .map(function (part) {{
        const trimmed =
          part.trim();

        const match =
          trimmed.match(
            /^(.+?)[×x]([0-9]+)$/
          );

        if (!match) {{
          return null;
        }}

        const code =
          match[1].trim();

        const count =
          Number(match[2]);

        const rate =
          total > 0
            ? (
                count
                / total
                * 100
              )
            : 0;

        return {{
          code: code,
          count: count,
          rate: rate,
          type: codeType(code),
        }};
      }})
      .filter(Boolean);
  }}

  function createCodeBadge(item) {{
    const badge =
      document.createElement(
        "div"
      );

    badge.className =
      "pe-http-code "
      + "pe-http-code-"
      + item.type;

    const code =
      document.createElement(
        "div"
      );

    code.className =
      "pe-http-code-name";

    code.textContent =
      item.code;

    const count =
      document.createElement(
        "div"
      );

    count.className =
      "pe-http-code-count";

    count.textContent =
      item.count;

    const rate =
      document.createElement(
        "div"
      );

    rate.className =
      "pe-http-code-rate";

    rate.textContent =
      percent(item.rate);

    badge.appendChild(code);
    badge.appendChild(count);
    badge.appendChild(rate);

    return badge;
  }}

  function enhanceTransactions() {{
    const panel =
      document.querySelector(
        ".pe-transactions"
      );

    if (!panel) {{
      return;
    }}

    panel
      .querySelectorAll("tbody tr")
      .forEach(function (row) {{
        const cells =
          row.querySelectorAll("td");

        if (cells.length !== 10) {{
          return;
        }}

        const samples =
          parseNumber(
            cells[1].textContent
          );

        const errorRate =
          parseNumber(
            cells[3].textContent
          );

        const codesCell =
          cells[9];

        const parsed =
          parseCodes(
            codesCell.textContent,
            samples
          );

        if (parsed.length) {{
          codesCell.innerHTML = "";

          const wrapper =
            document.createElement(
              "div"
            );

          wrapper.className =
            "pe-response-codes";

          parsed.forEach(
            function (item) {{
              wrapper.appendChild(
                createCodeBadge(
                  item
                )
              );
            }}
          );

          codesCell.appendChild(
            wrapper
          );
        }}

        if (errorRate > 0) {{
          row.classList.add(
            "pe-transaction-failed"
          );
        }} else {{
          row.classList.add(
            "pe-transaction-success"
          );
        }}
      }});
  }}

  function enhanceErrors() {{
    const panel =
      document.querySelector(
        ".pe-transaction-errors"
      );

    if (!panel) {{
      return;
    }}

    let totalErrors = 0;

    panel
      .querySelectorAll("tbody tr")
      .forEach(function (row) {{
        const cells =
          row.querySelectorAll("td");

        if (cells.length < 4) {{
          return;
        }}

        totalErrors +=
          parseNumber(
            cells[1].textContent
          );

        const cell =
          cells[3];

        const match =
          String(
            cell.textContent || ""
          )
          .trim()
          .match(
            /^(.+?)[×x]([0-9]+)$/
          );

        if (match) {{
          cell.innerHTML =
            '<span '
            + 'class="pe-error-code-badge">'
            + match[1].trim()
            + '</span>';
        }}
      }});

    if (totalErrors <= 0) {{
      return;
    }}

    panel.classList.add(
      "pe-has-errors"
    );

    const requestsElement =
      document.querySelector(
        ".cards "
        + ".card:nth-child(1) "
        + ".card-value"
      );

    const totalRequests =
      requestsElement
        ? parseNumber(
            requestsElement.textContent
          )
        : 0;

    const errorRate =
      totalRequests > 0
        ? (
            totalErrors
            / totalRequests
            * 100
          )
        : 0;

    const alert =
      document.createElement(
        "div"
      );

    alert.className =
      "pe-error-alert";

    alert.innerHTML =
      '<div class="pe-error-alert-content">'
      + '<div class="pe-error-alert-icon">!</div>'
      + '<div>'
      + '<div class="pe-error-alert-title">'
      + 'Se detectaron errores en la ejecución'
      + '</div>'
      + '<div class="pe-error-alert-description">'
      + totalErrors
      + ' de '
      + totalRequests
      + ' solicitudes fallaron ('
      + percent(errorRate)
      + ').'
      + '</div>'
      + '</div>'
      + '</div>';

    panel.appendChild(alert);
  }}

  enhanceTransactions();
  enhanceErrors();
}})();
</script>

</body>
</html>
""".format(
        verdict_class=verdict_class,
        verdict=verdict,
        scenario=html.escape(scenario),
        target=html.escape(target),
        generated_at=generated_at,
        source=html.escape(str(analysis.get("source", ""))),
        requests=metrics["total_requests"],
        success_rate=format_metric(
            metrics["success_rate_pct"],
            decimals=3,
        ),
        throughput=format_metric(
            metrics["throughput_req_per_sec"],
            decimals=3,
        ),
        p95=format_metric(
            metrics["response_time_ms"]["p95"],
            decimals=1,
        ),
        p99=format_metric(
            metrics["response_time_ms"]["p99"],
            decimals=1,
        ),
        minimum=format_metric(
            metrics["response_time_ms"]["min"],
            decimals=2,
        ),
        average=format_metric(
            metrics["response_time_ms"]["avg"],
            decimals=2,
        ),
        p50=format_metric(
            metrics["response_time_ms"]["p50"],
            decimals=1,
        ),
        p90=format_metric(
            metrics["response_time_ms"]["p90"],
            decimals=1,
        ),
        maximum=format_metric(
            metrics["response_time_ms"]["max"],
            decimals=2,
        ),
        response_time_chart=response_time_chart,
        throughput_chart=throughput_chart,
        error_chart=error_chart,
        checks_rows=checks_rows,
        errors_rows=errors_rows,
        transaction_rows=transaction_rows,
        transaction_error_rows=transaction_error_rows,
        service_dashboard_json=service_dashboard_json,
        recommendations=recommendations_html,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Genera un reporte HTML de performance."
    )

    parser.add_argument(
        "--analysis",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--jtl",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--output",
        default=Path("reports/performance-report.html"),
        type=Path,
    )

    parser.add_argument(
        "--scenario",
        default="Performance Test",
    )

    parser.add_argument(
        "--target",
        default="Not specified",
    )

    parser.add_argument(
        "--bucket-seconds",
        type=int,
        default=1,
    )

    args = parser.parse_args()

    try:
        with args.analysis.open(
            encoding="utf-8"
        ) as file:
            analysis = json.load(file)

        (
            time_labels,
            average_response_time,
            throughput_series,
            error_rate_series,
        ) = load_timeseries(
            args.jtl,
            bucket_seconds=args.bucket_seconds,
        )

        output_html = build_html(
            analysis=analysis,
            time_labels=time_labels,
            average_response_time=average_response_time,
            throughput_series=throughput_series,
            error_rate_series=error_rate_series,
            scenario=args.scenario,
            target=args.target,
        )

        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        args.output.write_text(
            output_html,
            encoding="utf-8",
        )

    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(
            "ERROR: {}".format(error)
        )
        return 2

    print(
        "Reporte HTML generado: {}".format(
            args.output
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
