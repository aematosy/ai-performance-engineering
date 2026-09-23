# Integración

Ejemplo recomendado, dejando que el objetivo general se derive del JTL:

```bash
poetry run python \
  .gemini/skills/performance-report-interpreter/scripts/build_report_bundle.py \
  --analysis "$RESULT_DIR/analysis.json" \
  --intelligence "$RESULT_DIR/intelligence.json" \
  --jtl "$RESULT_DIR/results.jtl" \
  --jmx "tests/generated/<scenario>.jmx" \
  --workload "workspaces/<workspace>/execution-profile.yaml" \
  --output-dir "$REPORT_DIR" \
  --scenario "<scenario>" \
  --html-report "$REPORT_DIR/executive-report.html"
```

Pasar `--target` solo cuando exista un nombre/alcance explícito más útil que el origen derivado, por ejemplo `Portal de Clientes - API y backend`.

El builder genera:

- `evidence.json`
- `interpretation.md`
- `executive-report.pdf`
- mejora no destructiva de `executive-report.html`

No vuelve a ejecutar JMeter.

## Observabilidad HTML

Por defecto el enhancer agrega accesos a:

- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- Métricas: para JMeter usa `observability.prometheus_port` del execution profile (por defecto 9270); para Locust usa el exporter live dedicado en `http://localhost:9271/metrics`, salvo `--metrics-url` explícito.

Se pueden reemplazar con `--grafana-url`, `--prometheus-url` y `--metrics-url`.

El enhancer elimina botones de exportación de versiones anteriores antes de agregar uno nuevo, por lo que puede ejecutarse varias veces sin duplicar controles.

`evidence.json` se conserva como artefacto técnico, pero el PDF ejecutivo no muestra request/response representativos.
