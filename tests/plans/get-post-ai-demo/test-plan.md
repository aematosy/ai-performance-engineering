# Performance Test Plan: get-post-ai-demo

**Status:** `APPROVED`
**Workload Status:** `APPROVED`
**Authorization Status:** `PENDING`

## Overview
Baseline performance assessment for GET /posts/1 on jsonplaceholder.typicode.com

## Target
- **Protocol:** https
- **Host:** jsonplaceholder.typicode.com
- **Port:** 443
- **Environment:** demo

## Workload (PROPOSED)
- **Threads:** 2
- **Ramp-up:** 5 seconds
- **Duration:** 30 seconds
- **Pacing:** 1.0 second

## SLA (Source: config/sla.json)
- **Error Rate Threshold:** 1.0%
- **p95 Threshold:** 1000ms
- **p99 Threshold:** 2000ms
- **Min Throughput:** 1.0 req/sec

## Observability Gaps
- No server-side observability is available unless explicitly provided.

## Risks
- **Category:** Environment
  - **Description:** Public demo API, unpredictable performance.
  - **Impact:** MEDIUM
  - **Mitigation:** Ensure baseline comparison is meaningful, consider result variance.

## Open Questions
- None.
