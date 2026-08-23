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
