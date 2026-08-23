# AI-Assisted Performance Engineering Platform

This repository implements an AI-assisted Performance Engineering platform
using Gemini CLI, Agent Skills, Apache JMeter, Python, Prometheus, Grafana,
Docker Compose and deterministic analysis components.

The platform supports the complete Performance Engineering lifecycle:

Discovery
→ Performance Test Design
→ Human Review and Approval
→ JMX Generation
→ Environment Validation
→ Authorized Execution
→ Observability
→ SLA Analysis
→ Historical Comparison
→ Trend Analysis
→ Deterministic Intelligence
→ AI-Assisted Interpretation
→ Recommendations
→ Next Test Design

## Language

User-facing responses must be written in Spanish unless the user explicitly
requests another language.

Keep in English only:

- file names;
- paths;
- commands;
- code;
- configuration keys;
- technical identifiers;
- official product and tool names.

## Core Principles

Always follow these principles:

1. Evidence before assumptions.
2. Deterministic analysis before generative AI interpretation.
3. Human authorization before load execution.
4. Human approval before high-impact changes.
5. Never invent metrics, results, bottlenecks or root causes.
6. Never expose credentials, tokens, cookies or sensitive headers.
7. Preserve execution evidence and previous results.
8. Prefer reproducible and parametrized workflows.
9. Do not duplicate functionality already implemented by project scripts.
10. Clearly distinguish facts, hypotheses, risks and recommendations.

## Source of Truth

### Project Configuration

Primary configuration:

`config/project-config.yaml`

SLA configuration:

`config/sla.json`

Do not hardcode values already available through configuration.

### Execution Evidence

Execution artifacts are stored under:

`results/<execution-id>/`

They may include:

- `results.jtl`
- `jmeter.log`
- `analysis.json`
- `metadata.json`
- `trend.json`
- `intelligence.json`

Reports are stored under:

`reports/<execution-id>/`

They may include:

- `executive-report.html`
- `jmeter/index.html`
- `intelligence-report.md`

When these artifacts exist, treat them as the source of truth.

## Deterministic and AI Responsibilities

The deterministic platform owns:

- JMeter execution;
- raw performance metrics;
- SLA evaluation;
- PASS or FAIL verdict;
- historical metrics;
- historical comparison;
- trend calculation;
- risk classification;
- deterministic ACCEPT, REVIEW or REJECT decision.

Gemini and Agent Skills may:

- perform test discovery;
- assist with test design;
- explain deterministic results;
- identify patterns;
- formulate hypotheses;
- identify missing evidence;
- prioritize recommendations;
- design the next test;
- create technical and executive explanations.

Gemini must never silently override deterministic evidence.

For example:

SLA Verdict: PASS
Trend: DEGRADED
Risk: HIGH
Decision: REJECT

must not be presented as a healthy execution merely because the SLA passed.

## Root Cause Policy

Never present a hypothesis as a confirmed root cause without sufficient
supporting evidence.

When evidence is incomplete, use language such as:

- hipótesis;
- posible causa;
- evidencia insuficiente;
- requiere correlación;
- requiere validación.

A performance hypothesis should include whenever possible:

- confidence level;
- supporting evidence;
- missing evidence;
- validation steps.

Valid confidence levels:

- LOW
- MEDIUM
- HIGH

High confidence requires multiple supporting evidence points.

## AI-First Performance Test Design

The target architecture starts before JMeter.

A Performance Engineering request may begin from:

- OpenAPI or Swagger;
- Postman Collection;
- cURL;
- API endpoint;
- HAR;
- web user flow;
- functional documentation;
- existing JMX;
- user description.

Do not jump directly from discovery to execution.

Preferred lifecycle:

Requirement
→ Discovery
→ Structured Performance Test Plan
→ Human Review
→ APPROVED
→ JMX Generation
→ Technical Validation
→ Authorized Execution

The target canonical test-design artifact is:

`tests/plans/<scenario>/test-plan.yaml`

Supporting artifacts may include:

`tests/plans/<scenario>/test-plan.md`

`tests/plans/<scenario>/data-requirements.json`

Until plan-based JMX generation is implemented, use the current
`scripts/generate_jmx.py` interface.

## Performance Test Discovery

Before creating an executable performance test, determine when applicable:

- business objective;
- scenario;
- system type;
- target;
- environment;
- HTTP method or user flow;
- authorization;
- authentication mechanism;
- expected workload;
- concurrency;
- ramp-up;
- duration;
- pacing or think time;
- SLA;
- test data;
- correlations;
- dependencies;
- observability requirements;
- known environment limitations.

Do not invent business workload, production traffic, SLA or authorization.

If critical information is missing, ask only for the information required to
continue safely.

## Human Approval

The future structured test plan must support at least:

- DRAFT
- APPROVED

A DRAFT plan may be analyzed or modified.

A DRAFT plan must not automatically trigger a load test.

Human approval is required before moving from design to executable load
generation when the operation may affect a real environment.

## Execution Safety Gate

Never execute a load test unless all required execution information is known.

At minimum confirm:

- target;
- environment;
- authorization;
- virtual users;
- ramp-up;
- duration;
- JMX or approved test plan.

Production environments require explicit authorization.

Never increase users, duration or load beyond approved values.

## JMeter Rules

Use Apache JMeter in non-GUI mode for actual performance executions.

Generated JMX files belong under:

`tests/generated/`

Prefer runtime properties instead of hardcoded workload values.

Current runtime properties include:

- `threads`
- `ramp_time`
- `duration`
- `prometheus_port`

Do not embed credentials or secrets directly in JMX files.

## Current Deterministic Backend

The current backend includes:

- `scripts/config_loader.py`
- `scripts/validate_environment.py`
- `scripts/generate_jmx.py`
- `scripts/run_test.py`
- `scripts/analyze_results.py`
- `scripts/generate_report.py`
- `scripts/history_manager.py`
- `scripts/trend_analyzer.py`
- `scripts/intelligence_engine.py`

Prefer these components over manually rebuilding equivalent functionality.

## Main Execution Orchestrator

For a complete authorized execution, prefer:

`poetry run python scripts/run_test.py`

The orchestrator currently coordinates:

Environment Validation
→ Docker Compose
→ Prometheus
→ Grafana
→ JMeter
→ JTL Validation
→ SLA Analysis
→ Reporting
→ Metadata
→ History
→ Historical Comparison
→ Trend
→ Deterministic Intelligence

Do not manually reproduce the complete workflow unless debugging a specific
stage.

## Result Interpretation Order

Always interpret an execution in this order:

1. Technical execution status.
2. Evidence completeness.
3. Functional/request errors.
4. Error rate.
5. SLA verdict.
6. Throughput.
7. p95 and p99.
8. Historical comparison.
9. Trend.
10. Deterministic intelligence.
11. Test-quality limitations.
12. Observability gaps.
13. Hypotheses.
14. Recommended actions.
15. Next test.

A PASS only means the configured SLA thresholds were satisfied.

PASS does not prove:

- unlimited capacity;
- production readiness;
- long-term stability;
- absence of bottlenecks;
- absence of regression;
- correct sizing for production.

## Historical Analysis

Execution history is stored in:

`history/history.json`

Historical comparisons must use meaningfully comparable executions.

Compare, when possible:

- same scenario;
- same target;
- same environment;
- same users;
- same ramp-up;
- same duration;
- equivalent test data and system conditions.

A single improved or degraded execution indicates a change.

It does not prove a persistent trend.

Prefer multiple comparable executions before declaring a regression or stable
improvement.

## Trend Analysis

Trend output is stored in:

`results/<execution-id>/trend.json`

Current classifications:

- IMPROVED
- STABLE
- DEGRADED
- INSUFFICIENT_DATA

Do not silently recalculate or override deterministic trend results.

## Deterministic Intelligence

Intelligence output is stored in:

`results/<execution-id>/intelligence.json`

Current risk levels:

- LOW
- MEDIUM
- HIGH

Current deterministic decisions:

- ACCEPT
- REVIEW
- REJECT

The AI may explain and contextualize these decisions.

The AI must not silently replace them.

## Observability

Current observability endpoints:

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- JMeter metrics: `http://localhost:9270/metrics`

The JMeter Prometheus endpoint exists only while JMeter is exposing metrics.

A Prometheus JMeter target becoming DOWN after a completed test is expected
behavior and must not automatically be reported as an error.

Current observability does not by itself provide complete server-side metrics
such as:

- application CPU;
- application memory;
- database performance;
- garbage collection;
- network saturation;
- downstream dependency health.

Never invent these measurements when they are unavailable.

## Knowledge Base

Project-specific Performance Engineering guidance is stored under:

`knowledge/`

Important references include:

- `knowledge/performance-testing-strategy.md`
- `knowledge/jmeter-best-practices.md`
- `knowledge/sla-and-analysis-guidelines.md`
- `knowledge/prometheus-grafana-guide.md`
- `knowledge/troubleshooting-guide.md`
- `knowledge/glossary.md`

Use the relevant project knowledge before providing specialized technical
recommendations.

## Gemini Agent Skills

Gemini Agent Skills are stored under:

`.gemini/skills/`

Current intended responsibilities:

### chief-performance-engineer

Coordinates requests spanning multiple Performance Engineering stages and
consolidates evidence, risk and recommendations.

### performance-test-designer

Performs Performance Test discovery and safe test design.

### performance-test-runner

Controls authorized execution and evidence collection.

### performance-results-analyst

Interprets existing execution evidence, SLA, history, trend and intelligence.

### performance-engineer

Provides specialized Performance Engineering technical review and guidance.

Use the most specific Skill for the user's request.

Use `chief-performance-engineer` when the request spans multiple stages.

## Evidence Preservation

Never overwrite historical execution directories.

Execution evidence belongs under:

`results/`

Reports belong under:

`reports/`

Historical index belongs under:

`history/`

Generated JMX files belong under:

`tests/generated/`

Future structured Performance Test Plans belong under:

`tests/plans/`

## Security

Never expose or persist:

- passwords;
- OAuth tokens;
- API keys;
- session cookies;
- Authorization headers;
- Proxy-Authorization headers;
- credentials contained in source requests.

When authentication is required, prefer environment variables or an external
secret-management mechanism.

Redact sensitive values before sending contextual information to a generative
model.

## Final Performance Assessment

When reporting a completed execution, clearly separate:

- Deterministic Verdict
- Trend
- Risk
- Deterministic Decision
- Evidence
- Test Limitations
- Observability Gaps
- AI Hypotheses
- Recommended Actions
- Next Test

Keep every conclusion proportional to the available evidence.

## Platform Direction

The long-term goal is not merely to automate JMeter.

The platform should progressively support:

Requirement
→ AI Discovery
→ AI-Assisted Test Design
→ Human Approval
→ Automated Test Generation
→ Controlled Execution
→ Observability
→ Deterministic Analysis
→ Historical Learning
→ AI-Assisted Reasoning
→ Recommended Next Experiment

AI assists engineering decisions.

Deterministic evidence remains the source of truth.
