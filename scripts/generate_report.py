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



def format_metric(value, suffix=""):
    if value is None:
        return "N/A"

    return (
        html.escape(str(value))
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
            '<td colspan="11" class="muted">'
            'No transaction-level metrics available.'
            '</td>'
            '</tr>'
        )

    rows = []

    for tx in transactions:
        response = tx.get(
            "response_time_ms",
            {},
        )

        codes = tx.get(
            "response_codes",
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

        status = str(
            tx.get(
                "status",
                "UNKNOWN",
            )
        ).upper()

        status_class = (
            "status-pass"
            if status == "PASS"
            else "status-fail"
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
                '<td class="{status_class}">'
                "{status}"
                "</td>"
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
                    0,
                ),
                success=tx.get(
                    "success_rate_pct",
                    0,
                ),
                errors=tx.get(
                    "error_rate_pct",
                    0,
                ),
                avg=format_metric(
                    response.get("avg")
                ),
                p90=format_metric(
                    response.get("p90")
                ),
                p95=format_metric(
                    response.get("p95")
                ),
                p99=format_metric(
                    response.get("p99")
                ),
                throughput=(
                    format_metric(
                        tx.get(
                            "throughput_req_per_sec"
                        )
                    )
                ),
                codes=(
                    codes_text
                    or "N/A"
                ),
                status_class=(
                    status_class
                ),
                status=(
                    html.escape(
                        status
                    )
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
            "label": "All Transactions",
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
            '<td class="{status_class}">{status}</td>'
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
<title>Performance Test Report</title>

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

</head>

<body>

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
        AI-Assisted Performance Engineering
      </div>

      <h1>Performance Test Report</h1>

      <div class="subtitle">
        Resultado ejecutivo y técnico generado automáticamente
        a partir de JMeter, SLA configurables y análisis Python.
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
      <div class="metadata-label">Target</div>
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
      <div class="card-label">Requests</div>
      <div class="card-value">{requests}</div>
    </div>

    <div class="card">
      <div class="card-label">Success Rate</div>
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

  <section class="panel">
    <h2>Response Time Summary</h2>

    <table>
      <thead>
        <tr>
          <th>Min</th>
          <th>Average</th>
          <th>p50</th>
          <th>p90</th>
          <th>p95</th>
          <th>p99</th>
          <th>Max</th>
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

  <section class="panel">
    <h2>Transaction / Service Breakdown</h2>

    <p class="muted">
      Metrics grouped dynamically by JMeter label.
      Labels may represent endpoints, services,
      business transactions or imported test steps.
    </p>

    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Transaction / Service</th>
            <th>Samples</th>
            <th>Success %</th>
            <th>Error %</th>
            <th>Avg ms</th>
            <th>p90 ms</th>
            <th>p95 ms</th>
            <th>p99 ms</th>
            <th>Req/s</th>
            <th>Response Codes</th>
            <th>Status</th>
          </tr>
        </thead>

        <tbody>
          {transaction_rows}
        </tbody>
      </table>
    </div>
  </section>

  <section class="panel">
    <h2>Errors by Transaction / Service</h2>

    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Transaction / Service</th>
            <th>Errors</th>
            <th>Error %</th>
            <th>Response Codes</th>
            <th>Failure Details</th>
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
          Transaction / Service
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
        All Transactions
      </div>
    </div>

    <div class="service-kpis">
      <div class="service-kpi">
        <div class="service-kpi-label">
          Samples
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
          Success
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
          Error Rate
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
          Average
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
        <h3>Response Time Trend</h3>
        <div
          id="service-response-chart"
          class="service-chart"
        ></div>
      </div>

      <div class="service-chart-panel">
        <h3>Throughput Trend</h3>
        <div
          id="service-throughput-chart"
          class="service-chart"
        ></div>
      </div>

      <div class="service-chart-panel">
        <h3>Error Rate Trend</h3>
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

  <section class="chart-grid legacy-global-charts">
    <div class="panel chart-panel">
      <h2>Response Time Trend</h2>
      {response_time_chart}
    </div>

    <div class="panel chart-panel">
      <h2>Throughput Trend</h2>
      {throughput_chart}
    </div>
  </section>

  <section class="panel">
    <h2>Error Rate Trend</h2>
    {error_chart}
  </section>

  <section class="panel">
    <h2>SLA Validation</h2>

    <table>
      <thead>
        <tr>
          <th>Check</th>
          <th>Threshold</th>
          <th>Actual</th>
          <th>Result</th>
        </tr>
      </thead>

      <tbody>
        {checks_rows}
      </tbody>
    </table>
  </section>

  <section class="panel">
    <h2>Errors by Response Code</h2>

    <table>
      <thead>
        <tr>
          <th>Response Code</th>
          <th>Count</th>
        </tr>
      </thead>

      <tbody>
        {errors_rows}
      </tbody>
    </table>
  </section>

  <section class="panel">
    <h2>Recommendations</h2>
    <ul>
      {recommendations}
    </ul>
  </section>

  <footer class="footer">
    Generated by the Performance Engineering Demo Pipeline
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
      label.textContent = "Light";

      button.setAttribute(
        "aria-label",
        "Cambiar a tema claro"
      );
    }} else {{
      icon.textContent = "☾";
      label.textContent = "Dark";

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
      || "All Transactions"
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
        + 'No data available'
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
      "Average response time (ms)",
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
      "Error rate (%)",
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
            ? "All Transactions"
            : "Unnamed Transaction"
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
        success_rate=metrics["success_rate_pct"],
        throughput=metrics["throughput_req_per_sec"],
        p95=metrics["response_time_ms"]["p95"],
        p99=metrics["response_time_ms"]["p99"],
        minimum=metrics["response_time_ms"]["min"],
        average=metrics["response_time_ms"]["avg"],
        p50=metrics["response_time_ms"]["p50"],
        p90=metrics["response_time_ms"]["p90"],
        maximum=metrics["response_time_ms"]["max"],
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