# AI-Assisted Performance Engineering Platform

Plataforma de demostración para un ciclo de Performance Engineering asistido por IA, con controles determinísticos y aprobación humana.

## Objetivo

Convertir una entrada como cURL, API, OpenAPI/Swagger o descripción funcional en un flujo reproducible:

```text
Requirement / API / cURL
        ↓
Gemini CLI + Agent Skills
        ↓
AI Discovery & Test Design
        ↓
test-plan.yaml + test-plan.md + data-requirements.json
        ↓
Deterministic Review & Validation
        ↓
Human Approval
        ↓
JMX Generation
        ↓
Explicit Execution Authorization
        ↓
Apache JMeter
        ↓
Prometheus + Grafana
        ↓
SLA Analysis
        ↓
History + Trend
        ↓
Deterministic Intelligence
        ↓
Gemini Results Analysis
```

La IA asiste el diseño y la interpretación. Los resultados, SLA, tendencia, riesgo y decisiones determinísticas permanecen sustentados por artefactos del pipeline.

## Componentes

- Gemini CLI + Agent Skills
- Python 3.11+
- Poetry
- Apache JMeter 5.6.x
- Java 17+
- Docker / Docker Compose
- Prometheus
- Grafana

## Agent Skills

Las Skills viven en `.gemini/skills/`:

- `chief-performance-engineer`
- `performance-test-designer`
- `performance-test-runner`
- `performance-results-analyst`
- `performance-engineer`

`GEMINI.md` contiene las reglas globales del proyecto.

## Estructura principal

```text
config/          configuración central y SLA
knowledge/       conocimiento de Performance Engineering
scripts/         backend determinístico
tests/plans/     Performance Test Plans
tests/generated/ JMX generados
results/         evidencia de ejecución
reports/         reportes
history/         historial de ejecuciones
grafana/         dashboards y provisioning
```

## Seguridad

Nunca persistir:

- API keys
- OAuth tokens
- passwords
- session cookies
- Authorization headers
- secretos productivos

La autenticación de Gemini debe permanecer fuera del repositorio.

La aprobación de diseño NO equivale a autorización de ejecución:

```text
Plan APPROVED
Workload APPROVED
Execution PENDING
```

La carga solo se ejecuta cuando existe autorización explícita.

## Instalación

```bash
poetry install
```

Validar ambiente:

```bash
make validate
```

## Flujo AI-first

### 1. Diseñar con Gemini

Desde la raíz:

```bash
gemini
```

El `performance-test-designer` puede partir de un cURL, OpenAPI/Swagger, endpoint o descripción del servicio.

El resultado esperado es:

```text
tests/plans/<scenario>/test-plan.yaml
tests/plans/<scenario>/test-plan.md
tests/plans/<scenario>/data-requirements.json
```

El plan debe iniciar como:

```text
Plan       : DRAFT
Workload   : PROPOSED
Execution  : PENDING
```

### 2. Revisar y validar

Para el escenario demo:

```bash
make review-plan
make validate-plan
```

El reviewer verifica consistencia, seguridad, SLA, workload, observabilidad y coherencia entre artefactos.

### 3. Aprobar diseño

```bash
make approve-plan APPROVED_BY="Nombre Apellido"
```

Esto aprueba diseño y workload, pero mantiene:

```text
Authorization : PENDING
```

### 4. Generar JMX

```bash
make generate-jmx
```

Esto genera el JMX sin ejecutar carga.

### 5. Ejecutar

La ejecución requiere una acción explícita:

```bash
make run-demo
```

El target demo configurado es JSONPlaceholder. Revisar siempre target, workload y autorización antes de ejecutar.

## Escenario de demostración

Valores actuales:

```text
Scenario : create-post-demo
Target   : POST https://jsonplaceholder.typicode.com/posts
Users    : 5
Ramp-up  : 10 s
Duration : 60 s
```

Estos valores son únicamente para la demostración aprobada.

## Resultados

Cada ejecución genera una carpeta única bajo `results/`.

Puede contener:

- `results.jtl`
- `jmeter.log`
- `analysis.json`
- `metadata.json`
- `trend.json`
- `intelligence.json`

Los reportes se almacenan bajo `reports/`:

- `executive-report.html`
- `jmeter/index.html`
- `intelligence-report.md`

## Interpretación

Orden recomendado:

1. estado técnico;
2. evidencia;
3. errores;
4. SLA;
5. throughput;
6. p95/p99;
7. history;
8. trend;
9. intelligence;
10. limitaciones;
11. hipótesis;
12. siguiente experimento.

Un `PASS` de SLA no demuestra por sí solo capacidad productiva o estabilidad sostenida.

## Observabilidad

Prometheus:

```text
http://localhost:9090
```

Grafana:

```text
http://localhost:3000
```

JMeter Prometheus Listener durante ejecución:

```text
http://localhost:9270/metrics
```

La ausencia de métricas server-side debe tratarse como una brecha de evidencia, no como permiso para inferir CPU, memoria, DB, GC o red.

## Comandos principales

```bash
make help
make validate
make smoke
make review-plan
make validate-plan
make approve-plan APPROVED_BY="Nombre Apellido"
make generate-jmx
make run-demo
make status
make clean-runtime
```

`make clean-runtime` elimina únicamente caches y temporales regenerables. No elimina history, results ni reports.

## Smoke Test

```bash
make smoke
```

El smoke test no ejecuta carga. Valida estructura, configuración, scripts, Skills, plan, JMX y Docker.

## Troubleshooting

### Docker no disponible

Abrir Docker Desktop y ejecutar:

```bash
docker info
docker compose ps
```

### Plan inválido

```bash
make review-plan
make validate-plan
```

No corregir mecánicamente artefactos a mano si el reviewer/Designer puede regenerarlos o sincronizarlos.

### Primera ejecución sin Trend

Es esperado. Se necesitan al menos dos ejecuciones comparables del mismo escenario para calcular tendencia.

## Principio de la demo

```text
AI proposes.
Deterministic controls verify.
Humans approve.
JMeter executes.
Evidence decides.
AI explains.
```
