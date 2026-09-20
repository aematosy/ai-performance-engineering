<!-- FINAL_NATURAL_UX_V3_START -->

# FINAL NATURAL PERFORMANCE UX CONTRACT - ABSOLUTE PRIORITY

This contract overrides older command-by-command instructions.

## Primary product principle

The human approves decisions, not implementation commands.

The normal user is NOT expected to know Python, shell commands,
YAML internals, JMeter internals, Locust internals or repository
architecture.

## Human-visible flow

The intended interaction is:

1. User requests a performance-test design.
2. Explain in Spanish what will happen and what will NOT happen.
3. Run the single high-level design entry point.
4. Present the plan in Spanish.
5. Wait for human design approval.
6. After approval, explain in Spanish that the test will be prepared.
7. Run the single high-level execution entry point.
8. If functional information is missing, ask only the meaningful
   functional question.
9. Present one final execution summary.
10. Ask whether the human wants to execute.
11. If yes, show the JMeter / Locust selector.
12. Prepare, authorize, validate and execute internally.
13. Present results.

## Only two normal high-level entry points

Design:

`scripts/natural_performance_design.sh`

Execution:

`scripts/natural_performance_execute.sh`

Do NOT orchestrate these normal flows by separately invoking:

- approve;
- authorize;
- preflight;
- validate_test_plan.py;
- prepare;
- execute;
- run_test.py;
- JMeter directly;
- Locust directly.

Those are internal implementation details.

## Mandatory explanation before a Shell permission

Before any user-visible Shell action, explain in Spanish:

1. what is going to happen;
2. why it is necessary;
3. what will NOT happen;
4. the target/workload impact when relevant.

Never present a raw technical command for approval without this
human explanation.

Example for design:

"Voy a preparar y validar el plan de prueba con el target y workload
que me diste. Esto generará los artefactos de diseño y verificará su
consistencia. No ejecutará carga, no autorizará ejecución y no
seleccionará JMeter ni Locust."

Example for execution:

"Voy a comprobar que el diseño tenga toda la información funcional
necesaria y luego te mostraré el resumen final. Todavía no ejecutaré
carga hasta que tú lo confirmes."

## Technical recovery

Do not involve the human in technical retries.

If an internal non-destructive technical action fails because of:

- interpreter selection;
- missing PYTHONPATH;
- Poetry environment;
- equivalent command invocation;
- another recoverable implementation detail;

recover internally when safe.

Do not ask the human:

"python3 failed, may I try poetry?"

Do not expose stack traces as the primary user explanation.

If recovery is impossible, explain the functional impact in Spanish.

## HTTP response contract

Never infer:

- GET -> 200;
- POST -> 201;
- missing contract -> 200;
- missing contract -> 0.

When the input does not declare an expected HTTP response:

`expected_status: UNRESOLVED`

During design:

- UNRESOLVED is valid;
- RESPONSE_CODE assertion must not be invented;
- the open question must be shown to the human;
- the design can be reviewed.

Before execution:

- every HTTP response contract must be explicit;
- ask the human for the expected HTTP status in natural language;
- do not prepare or execute an engine until the gap is resolved.

## Engine neutrality during design

Before engine selection:

- do not keep an active JMX;
- do not keep an active locustfile.py;
- do not include JMeter-specific metrics;
- do not include Locust-specific metrics.

Prometheus and Grafana may remain as neutral platform observability.

Engine-specific instrumentation is introduced only after the human
selects JMeter or Locust.

## Language

Avoid these terms in normal user-facing narration:

- facade / fachada;
- wrapper;
- approve;
- authorize;
- preflight;
- artifact;
- manifest;
- hash;
- TOCTOU;
- internal command names.

Prefer:

- "Preparando el diseño";
- "Validando el plan";
- "Plan listo para revisión";
- "Información funcional pendiente";
- "Prueba lista para ejecutar";
- "¿Deseas ejecutar esta prueba?";
- "¿Con qué herramienta deseas ejecutarla?".

## Human checkpoints

Normal flow should require only meaningful human decisions:

1. approve/reject the design;
2. answer missing functional information if any;
3. approve/reject execution;
4. select JMeter or Locust.

Gemini CLI may still display its own product-level Shell security
permission. That permission is not part of the Performance Engineering
governance and must not be multiplied by issuing many separate commands.

## No discovery during demo

Do not:

- execute `--help` to discover contracts;
- inspect implementation scripts;
- ReadFile internal entry points;
- grep source code;
- inspect src/ to decide what to run.

The documented high-level flow is authoritative.

<!-- FINAL_NATURAL_UX_V3_END -->

# Performance Test Plan Contract

Usar esta estructura como contrato canónico. No inventar aliases de campos.

## YAML

```yaml
metadata:
  name: "<scenario>"
  version: "1.0"
  description: "<description>"
  created_at: "<YYYY-MM-DD>"
  author: "Gemini CLI Performance Designer"

status: "DRAFT"

objective: "<objective>"

system:
  type: "API"
  name: "<system name>"

environment: "<known environment>"

target:
  protocol: "https"
  host: "example.com"
  port: 443
  base_path: ""

authentication:
  type: "NONE"
  description: "<non-secret description>"

workload:
  type: "BASELINE"
  status: "PROPOSED"
  parameters:
    threads: 2
    ramp_time_seconds: 5
    duration_seconds: 30
    pacing_seconds: 1.0
  description: "<why this is only a proposal>"

sla:
  error_rate_threshold_pct: 1.0
  p95_threshold_ms: 1000
  p99_threshold_ms: 2000
  min_throughput_req_per_sec: 1.0
  source: "config/sla.json"

data:
  requirements_file: "tests/plans/<scenario>/data-requirements.json"
  source_type: "NONE_OR_PARAMETERIZED"
  fields: []

transactions:
  - name: "01_Request"
    method: "GET"
    path: "/resource"
    headers:
      Accept: "application/json"
    expected_status: 200

correlations:
  description: "None required."
  extractors: []

assertions:
  - type: "RESPONSE_CODE"
    expected_value: "200"
    description: "Validate expected HTTP status."

observability:
  metrics:
    - source: "JMeter Prometheus Listener"
      endpoint: "http://localhost:9270/metrics"
    - source: "Prometheus"
      url: "http://localhost:9090"
    - source: "Grafana"
      url: "http://localhost:3000"
  gaps:
    - "No server-side observability is available unless explicitly provided."

risks:
  - category: "<risk>"
    description: "<evidence-based description>"
    impact: "LOW|MEDIUM|HIGH"
    mitigation: "<mitigation>"

authorization:
  required: true
  status: "PENDING"
  authorized_by: null
  authorized_at: null
  notes: "Execution requires explicit authorization."

open_questions: []
```

## Workload proposal rule

Cuando no exista workload y se trate de demo pública de baja intensidad:

```text
pacing_seconds = 1.0
ramp_time_seconds = 5
duration_seconds = 30
threads = max(2, ceil(min_throughput_req_per_sec * pacing_seconds * 1.5))
```

Mantener `workload.status: PROPOSED`.

El reviewer rechazará una propuesta si el techo optimista `threads / pacing_seconds` no puede superar el SLA mínimo de throughput.

## Markdown

Usar al inicio:

```markdown
# Performance Test Plan: <scenario>

**Status:** `DRAFT`
**Workload Status:** `PROPOSED`
**Authorization Status:** `PENDING`
```

Después reflejar target, environment, workload, SLA y fuente, observability gaps, risks y open questions.

No introducir requisitos ausentes del YAML.

## data-requirements.json

```json
{
  "schema_version": "1.0",
  "scenario": "<scenario>",
  "status": "DRAFT",
  "data_strategy": "NONE_OR_PARAMETERIZED",
  "requirements": {
    "parameters": [],
    "uniqueness_required": false,
    "cleanup_required": false,
    "preconditions": [],
    "open_questions": []
  }
}
```
