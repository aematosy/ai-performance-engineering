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
</style>
</head>

<body>
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

  <section class="chart-grid">
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