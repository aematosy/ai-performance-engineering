# Performance Test Plan - axet-dummyjson-e2e-demo

**Status:** `APPROVED`
**Workload Status:** `APPROVED`
**Authorization Status:** `AUTHORIZED`
**Authorized By:** `Adrian Matos`
**Authorized At:** `2026-09-23T16:16:41.778664-05:00`

## Plan Status

- Scenario: `axet-dummyjson-e2e-demo`
- Version: `1.0`

## Objective

Evaluate the declared scenario under the proposed controlled workload and collect performance evidence without exceeding approved execution parameters.

## Target

- Protocol: `https`
- Host: `dummyjson.com`
- Port: `443`
- Base path: ``

## Authentication

- Type: `NONE`
- Description: No Authorization header is declared by the normalized scenario.

## Proposed Workload

- Users / threads: `10`
- Ramp-up: `30 s`
- Duration: `60 s`
- Pacing: `2.0 s`

## Transactions

### 1. POST /products/add

- Method: `POST`
- Path: `/products/add`
- Expected status: `UNRESOLVED`
- Headers:
  - `Content-Type: application/json`
  - `Accept: application/json`
- Body: declared in canonical YAML plan.

## Correlations

No runtime correlations are declared for this scenario.

## SLA

- error_rate_threshold_pct: `1.0`
- p95_threshold_ms: `1000`
- p99_threshold_ms: `2000`
- min_throughput_req_per_sec: `1.0`
- source: `config/sla.json`

## Observability

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

## Governance

- Human design/workload approval: `REQUIRED`

This Markdown document is generated from `test-plan.yaml`. The YAML plan remains the canonical governed artifact.
