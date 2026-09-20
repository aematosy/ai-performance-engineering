**# AI-Assisted Performance Engineering Platform**

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

**## Language**

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

**## Core Principles**

Always follow these principles:

1\. Evidence before assumptions.

2\. Deterministic analysis before generative AI interpretation.

3\. Human authorization before load execution.

4\. Human approval before high-impact changes.

5\. Never invent metrics, results, bottlenecks or root causes.

6\. Never expose credentials, tokens, cookies or sensitive headers.

7\. Preserve execution evidence and previous results.

8\. Prefer reproducible and parametrized workflows.

9\. Do not duplicate functionality already implemented by project scripts.

10\. Clearly distinguish facts, hypotheses, risks and recommendations.

**## Source of Truth**

**### Project Configuration**

Primary configuration:

`config/project-config.yaml`

SLA configuration:

`config/sla.json`

Do not hardcode values already available through configuration.

**### Execution Evidence**

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

**## Deterministic and AI Responsibilities**

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

**## Root Cause Policy**

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

**## AI-First Performance Test Design**

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

→ Discovery / Intake

→ Structured Performance Test Plan

→ JMX / Data / Correlation Design Artifacts

→ Deterministic Review

→ Human Design and Workload Approval

→ Explicit Execution Authorization

→ Preflight

→ Human `RUN` Confirmation

→ Controlled Execution

The target canonical test-design artifact is:

`tests/plans/<scenario>/test-plan.yaml`

Supporting artifacts may include:

`tests/plans/<scenario>/test-plan.md`

`tests/plans/<scenario>/data-requirements.json`

For Postman input, JMX generation is part of governed intake/design preparation.
Generating a JMX is not execution authorization.

Never use `scripts/generate_jmx.py`, `scripts/generate_jmx_from_plan.py` or
`scripts/generate_postman_jmx.py` as a user-facing workflow command.

**## Performance Test Discovery**

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

**## Human Approval**

The future structured test plan must support at least:

- DRAFT

- APPROVED

A DRAFT plan may be analyzed or modified.

A DRAFT plan must not automatically trigger a load test.

Human approval is required before a generated design/workload may move to
execution authorization. Design artifacts such as JMX, CSV, correlation models
and plan companions may be generated during intake, but they must not be
executed merely because they exist.

**## Execution Safety Gate**

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

**## JMeter Rules**

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

**## Current Deterministic Backend**

The current backend includes:

- `scripts/config_loader.py`

- `scripts/validate_environment.py`

- `scripts/generate_jmx.py`

- `scripts/performance_workflow\.py`

- `scripts/analyze_results.py`

- `scripts/generate_report.py`

- `scripts/history_manager.py`

- `scripts/trend_analyzer.py`

- `scripts/intelligence_engine.py`

Prefer these components over manually rebuilding equivalent functionality.

**## Main Execution Orchestrator**

For a complete authorized execution, prefer:

`poetry run python scripts/performance_workflow\.py execute`

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

**## Result Interpretation Order**

Always interpret an execution in this order:

1\. Technical execution status.

2\. Evidence completeness.

3\. Functional/request errors.

4\. Error rate.

5\. SLA verdict.

6\. Throughput.

7\. p95 and p99.

8\. Historical comparison.

9\. Trend.

10\. Deterministic intelligence.

11\. Test-quality limitations.

12\. Observability gaps.

13\. Hypotheses.

14\. Recommended actions.

15\. Next test.

A PASS only means the configured SLA thresholds were satisfied.

PASS does not prove:

- unlimited capacity;

- production readiness;

- long-term stability;

- absence of bottlenecks;

- absence of regression;

- correct sizing for production.

**## Historical Analysis**

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

**## Trend Analysis**

Trend output is stored in:

`results/<execution-id>/trend.json`

Current classifications:

- IMPROVED

- STABLE

- DEGRADED

- INSUFFICIENT_DATA

Do not silently recalculate or override deterministic trend results.

**## Deterministic Intelligence**

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

**## Observability**

Current observability endpoints:

- Prometheus: `http\://localhost:9090`

- Grafana: `http\://localhost:3000`

- JMeter metrics: `http\://localhost:9270/metrics`

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

**## Knowledge Base**

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

**## Gemini Agent Skills**

Gemini Agent Skills are stored under:

`.gemini/skills/`

Current intended responsibilities:

**### chief-performance-engineer**

Coordinates requests spanning multiple Performance Engineering stages and

consolidates evidence, risk and recommendations.

**### performance-test-designer**

Performs Performance Test discovery and safe test design.

**### performance-test-runner**

Controls authorized execution and evidence collection.

**### performance-results-analyst**

Interprets existing execution evidence, SLA, history, trend and intelligence.

**### performance-engineer**

Provides specialized Performance Engineering technical review and guidance.

Use the most specific Skill for the user's request.

Use `chief-performance-engineer` when the request spans multiple stages.

**## Evidence Preservation**

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

**## Security**

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

**## Final Performance Assessment**

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

**## Platform Direction**

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

**

## Canonical Public Performance Workflow

This section is authoritative. If any earlier project text appears to conflict
with this section, this section wins.

For user-facing Performance Engineering orchestration, the ONLY supported
entrypoint is:

`poetry run python scripts/performance_workflow.py`

Supported public operations:

- `contract`
- `intake`
- `review`
- `approve`
- `authorize`
- `preflight`
- `execute`

The public workflow delegates to internal implementation scripts. Gemini must
not invoke those implementation scripts directly during a normal workflow.

### Internal-only scripts

Never invoke these directly as part of a user-facing workflow:

- `scripts/approve_test_plan.py`
- `scripts/authorize_execution.py`
- `scripts/run_approved_plan.py`
- `scripts/pre_execution_gate.py`
- `scripts/run_test.py`
- `scripts/generate_jmx.py`
- `scripts/generate_jmx_from_plan.py`
- `scripts/generate_postman_jmx.py`
- `scripts/refresh_jmx_metadata.py`
- direct `jmeter`

They may be inspected only when the public workflow itself reports an
unexpected implementation defect and the human explicitly asks for debugging.

### Hard conversational state machine

For a new performance design, follow exactly:

`INTAKE`
→ `REVIEW`
→ `WAIT_FOR_DESIGN_APPROVAL`
→ `APPROVE`
→ `WAIT_FOR_EXECUTION_AUTHORIZATION`
→ `AUTHORIZE`
→ `PREFLIGHT`
→ `WAIT_FOR_RUN`
→ `EXECUTE`
→ `RESULT_SUMMARY`
→ `STOP`

Rules:

1. One state transition equals one public workflow command.
2. Never skip a state.
3. Never combine approval and authorization into one human question.
4. After `REVIEW`, stop and request explicit design/workload approval.
5. After `APPROVE`, stop and request explicit execution authorization.
6. After successful `PREFLIGHT`, stop and wait for the exact text `RUN`.
7. `RUN` is final execution confirmation, not approval and not authorization.
8. After `EXECUTE`, summarize the deterministic result and stop.
9. Do not automatically activate another skill after execution.
10. Do not automatically investigate a failure unless the human asks.

### Human identity

If `PERF_HUMAN_NAME` is configured, use its value for:

- `--approved-by`
- `--authorized-by`

Do not print the environment variable merely to confirm it.

If `PERF_HUMAN_NAME` is not configured and a human identity is required, ask
once for the explicit human name. Never guess identities such as `User`, shell
usernames, account names or email addresses.

### Canonical Postman intake

When a Postman collection and environment are available, use this exact command
shape on the first attempt:

```bash
poetry run python scripts/performance_workflow.py intake \
  --input "<collection.postman_collection.json>" \
  --environment "<environment.postman_environment.json>" \
  --input-type postman \
  --workspace "workspaces/<scenario>-gemini"
```

Rules:

- `--input` is mandatory.
- `--workspace` is mandatory.
- Include `--environment` on the first attempt when an environment file exists.
- Include `--input-type postman`.
- The default execution profile is accepted unless the human requested another approved profile.
- Do not call `intake --help`.
- Do not run a preliminary intake without the environment and then retry.
- After successful intake, never rerun intake to repair approval, authorization, provenance or preflight state.
- Reuse the artifacts generated by the successful intake.

### Postman artifact contract

For a successfully prepared Postman scenario `<scenario>`, the normal governed artifact paths are:

- plan: `tests/plans/<scenario>/test-plan.yaml`
- plan companion: `tests/plans/<scenario>/test-plan.md`
- data requirements: `tests/plans/<scenario>/data-requirements.json`
- JMX: `tests/generated/<scenario>.jmx`
- CSV: `data/<scenario>/test-data.csv`
- design context: `work/postman/<scenario>/executable-model.json`
- optional secrets template: `data/<scenario>/secrets.properties.template`
- optional runtime properties: `data/<scenario>/secrets.properties`
- preflight manifest: `work/pre-execution/<scenario>.json`

Do not use `ls`, `find`, `grep` or `--help` merely to rediscover these known paths after intake.

If intake reports a different explicit artifact path, use the path reported by intake rather than guessing.

### REVIEW command

After successful intake, run exactly:

```bash
poetry run python scripts/performance_workflow.py review \
  --plan "tests/plans/<scenario>/test-plan.yaml"
```

If review passes, summarize the selected scenario, workload, transactions, correlations and required secrets, then stop and ask whether the human approves the design/workload.

### APPROVE command

After explicit design/workload approval, run exactly:

```bash
poetry run python scripts/performance_workflow.py approve \
  --plan "tests/plans/<scenario>/test-plan.yaml" \
  --jmx "tests/generated/<scenario>.jmx" \
  --approved-by "<explicit human name>"
```

Never attempt `approve` without `--jmx`. The public workflow owns any required metadata/provenance refresh. Do not call metadata or JMX-generation scripts directly afterward.

If approval succeeds, report `APPROVED`, stop, and explicitly ask whether execution is authorized.

### AUTHORIZE command

After explicit execution authorization, run exactly:

```bash
poetry run python scripts/performance_workflow.py authorize \
  --plan "tests/plans/<scenario>/test-plan.yaml" \
  --jmx "tests/generated/<scenario>.jmx" \
  --authorized-by "<explicit human name>" \
  --notes "Authorized for controlled performance execution."
```

Never attempt `authorize` without `--jmx`. The public workflow owns any required provenance refresh. Do not regenerate the JMX after authorization.

### Runtime properties / secrets

Secrets are never placed in JMX, CSV, prompts, logs or report summaries.

If `data-requirements.json` declares `JMETER_PROPERTY` secrets, runtime execution requires the corresponding external properties file, normally `data/<scenario>/secrets.properties`.

If no runtime JMeter-property secrets are required, omit `--properties`. Never print the contents of the properties file.

### PREFLIGHT command

For a Postman scenario that requires runtime properties:

```bash
poetry run python scripts/performance_workflow.py preflight \
  --plan "tests/plans/<scenario>/test-plan.yaml" \
  --profile "config/execution-profiles/baseline.yaml" \
  --jmx "tests/generated/<scenario>.jmx" \
  --csv "data/<scenario>/test-data.csv" \
  --data-requirements "tests/plans/<scenario>/data-requirements.json" \
  --design-context "work/postman/<scenario>/executable-model.json" \
  --manifest "work/pre-execution/<scenario>.json"
```

If the scenario does not require JMeter-property secrets, use the same command without `--properties`.

Never attempt preflight without `--plan`, `--profile` and `--jmx`. For generated Postman E2E scenarios, also pass the generated CSV, data-requirements and design-context artifacts.

If preflight succeeds, report `PRE_EXECUTION_READY`, report authorization state, stop, and request exact `RUN`.

If preflight fails, report the failing deterministic stage and exact error; do not rerun intake; do not regenerate JMX; do not call internal scripts; do not alter workload, target, data or authorization; do not perform speculative repairs; stop and ask the human before any state-changing action.

Maximum automatic retry after a public workflow failure: zero for argument, contract, provenance, authorization or deterministic gate failures. A retry is allowed only for a clearly transient transport/tool failure and only once.

### EXECUTE command

Only after the human types exactly `RUN`, execute the same validated bundle.

```bash
poetry run python scripts/performance_workflow.py execute \
  --plan "tests/plans/<scenario>/test-plan.yaml" \
  --profile "config/execution-profiles/baseline.yaml" \
  --jmx "tests/generated/<scenario>.jmx" \
  --csv "data/<scenario>/test-data.csv" \
  --data-requirements "tests/plans/<scenario>/data-requirements.json" \
  --design-context "work/postman/<scenario>/executable-model.json" \
  --manifest "work/pre-execution/<scenario>.json"
```

If no runtime JMeter-property secrets are required, omit `--properties`.

Do not change users/threads, ramp-up, duration, pacing, target, environment, data contract, JMX or profile between successful preflight and execute.

### Execution exit code versus test verdict

A completed test may return a non-zero process status because the deterministic SLA verdict is `FAIL`. Do not describe that automatically as a pipeline failure.

Distinguish:

- `EXECUTION_COMPLETED / SLA_PASS`
- `EXECUTION_COMPLETED / SLA_FAIL`
- `EXECUTION_INFRASTRUCTURE_ERROR`

If JMeter completed, evidence was produced, analysis ran and reports were generated, then an SLA `FAIL` is a valid test result, not evidence that the workflow itself malfunctioned.

### Result-summary contract

After execute, use the summary already printed by the public workflow whenever available. Present only execution ID, deterministic verdict, success rate, error rate, throughput, p95, p99, deterministic risk/decision when available, and the three report paths. Then stop.

Do not automatically `cat` the complete `analysis.json`, dump a JTL, dump a JMX, activate `performance-results-analyst`, activate `performance-engineer`, inspect correlations, grep samplers, propose JMX modifications or run another test. Root-cause analysis is a separate user-requested operation.

### Failure-analysis efficiency

When the human explicitly asks for failure analysis, start from deterministic `analysis.json`, `intelligence.json` and the intelligence report; inspect only summarized error groups and failing transactions; inspect only the specific JMX sections relevant to a hypothesis; never dump entire large JSON/JTL/XML files; classify root causes as hypotheses unless evidence confirms them; include confidence, supporting evidence, missing evidence and validation steps; do not modify an approved JMX without explicit human approval.

### Tool and token efficiency

Gemini must minimize unnecessary tool use.

Do not call `--help` for commands defined here, run a workflow command with knowingly missing required arguments, use `ls`/`find`/repeated `grep` for known paths, inspect source code during a successful normal workflow, repeat successful validations, rerun completed states, retry deterministic failures speculatively, load huge files when a summary is sufficient, activate additional skills unless the user asks, or continue working after a required human checkpoint.

Prefer one deterministic public workflow command per state.

### Multi-input compatibility

The public entrypoint also supports existing JMX and CLI inputs. Use `performance_workflow.py intake` for normalization/discovery, then follow the same governed lifecycle where the generated artifacts support it. Do not force Postman-specific assumptions onto services that do not require them. Authentication is optional and must be discovered from the source input.

### Safety invariants

Gemini must never bypass design/workload approval, bypass execution authorization, treat approval as authorization, treat preflight as authorization, treat `RUN` as authorization, increase the approved workload, reduce approved pacing, change target/environment after approval, expose secrets, inject secrets into CSV, execute JMeter directly, modify an approved JMX without explicit approval, or silently reinterpret deterministic PASS/FAIL, risk or decision.

### Final stop rule

When a requested state is complete, stop. When human input is required, ask one concise question and stop. When a deterministic gate fails, report it and stop. When execution completes, summarize the result and stop. Do not create work merely to keep the conversation active.

## DYNAMIC WORKLOAD - FINAL AUTHORITATIVE CONTRACT

This section overrides any earlier workload examples in GEMINI.md.

Performance workload is a DESIGN INPUT provided by the human.

For a new test, Gemini must obtain:

- virtual users;
- duration in seconds.

Optional values:

- ramp-up in seconds;
- pacing in seconds.

Never invent users or duration.

If users or duration are missing, ask once before INTAKE.

### Dynamic Postman intake

Use:

poetry run python scripts/performance_workflow.py intake \
  --input "<collection.postman_collection.json>" \
  --environment "<environment.postman_environment.json>" \
  --input-type postman \
  --workspace "workspaces/<scenario>-gemini" \
  --users <users> \
  --duration-seconds <duration> \
  --ramp-time-seconds <ramp> \
  --pacing-seconds <pacing>

The workflow generates:

workspaces/<scenario>-gemini/execution-profile.yaml

This generated execution profile is the source of truth for the proposed workload.

After REVIEW, Gemini must show the human:

- users;
- duration;
- ramp-up;
- pacing;

before asking for design/workload approval.

After APPROVE, these workload values are immutable.

### Dynamic profile rule

When dynamic workload was supplied during INTAKE, all later governed operations MUST use:

--profile "workspaces/<scenario>-gemini/execution-profile.yaml"

Never silently replace it with:

config/execution-profiles/baseline.yaml

The baseline profile is only a technical template used to create the generated design profile.

### Canonical PRELFIGHT with dynamic workload

poetry run python scripts/performance_workflow.py preflight \
  --plan "tests/plans/<scenario>/test-plan.yaml" \
  --profile "workspaces/<scenario>-gemini/execution-profile.yaml" \
  --jmx "tests/generated/<scenario>.jmx" \
  --csv "data/<scenario>/test-data.csv" \
  --data-requirements "tests/plans/<scenario>/data-requirements.json" \
  --design-context "work/postman/<scenario>/executable-model.json" \
  --manifest "work/pre-execution/<scenario>.json"


### Canonical EXECUTE with dynamic workload

Only after successful PREFLIGHT and exact human confirmation RUN:

poetry run python scripts/performance_workflow.py execute \
  --plan "tests/plans/<scenario>/test-plan.yaml" \
  --profile "workspaces/<scenario>-gemini/execution-profile.yaml" \
  --jmx "tests/generated/<scenario>.jmx" \
  --csv "data/<scenario>/test-data.csv" \
  --data-requirements "tests/plans/<scenario>/data-requirements.json" \
  --design-context "work/postman/<scenario>/executable-model.json" \
  --manifest "work/pre-execution/<scenario>.json"


Never change users, duration, ramp-up, pacing, target, profile or JMX between successful preflight and execute.

### Efficiency rule

A normal complete run must require only these public workflow state transitions:

INTAKE
REVIEW
STOP FOR DESIGN APPROVAL

APPROVE
STOP FOR EXECUTION AUTHORIZATION

AUTHORIZE
PREFLIGHT
STOP FOR RUN

EXECUTE
RESULT SUMMARY
STOP

Do not run --help.
Do not invoke internal scripts.
Do not rediscover known artifact paths.
Do not rerun successful states.
Do not automatically perform root-cause analysis after execution.

### Automatic runtime properties resolution

Runtime JMeter properties are resolved deterministically by the public
`performance_workflow.py` entrypoint.

Rules:

- Do not infer whether `--properties` is required.
- Do not inspect or print secret values.
- Invoke the public workflow normally.
- When the data contract declares `JMETER_PROPERTY` secrets, the workflow
  automatically resolves `data/<scenario>/secrets.properties`.
- If the required file exists and all required properties are configured,
  continue automatically without asking the human.
- If no `JMETER_PROPERTY` secrets are declared, no properties file is required.
- Stop only when the public workflow explicitly reports that a required
  properties file or required property is missing or empty.
- Never repeat INTAKE, REVIEW, APPROVE or AUTHORIZE because of a runtime
  properties validation failure.

### Human identity - final rule

When `PERF_HUMAN_NAME` is configured, always use its value for future
`approve` and `authorize` operations.

Never infer the human identity from:
- shell username;
- operating-system account;
- email;
- generic values such as `User`.

If an already-authorized historical plan contains a different authorized_by
value, do not silently rewrite that authorization during PREFLIGHT or EXECUTE.
Use the existing valid authorization for that immutable execution bundle.
New executions must use `PERF_HUMAN_NAME`.

## MULTI-ENGINE EXECUTION - AUTHORITATIVE CONTRACT

The governed platform supports two execution engines:

- JMeter
- Locust

The engine is selected before preflight and is persisted in the scenario execution profile.

Canonical state:

    engine: jmeter

or:

    engine: locust

### Governed lifecycle

    INTAKE
      |
      v
    REVIEW
      |
      v
    ENGINE SELECTION
      |
      v
    ENGINE ARTIFACT PREPARATION
      |
      v
    APPROVE
      |
      v
    AUTHORIZE
      |
      v
    PREFLIGHT
      |
      v
    STOP FOR RUN
      |
      v
    EXECUTE
      |
      v
    ANALYSIS
      |
      v
    COMMON REPORTING

### Engine selection

If the human explicitly requested JMeter, use:

    poetry run python scripts/performance_workflow.py select-engine \
      --profile "workspaces/<scenario>-gemini/execution-profile.yaml" \
      --engine jmeter

If the human explicitly requested Locust, use:

    poetry run python scripts/performance_workflow.py select-engine \
      --profile "workspaces/<scenario>-gemini/execution-profile.yaml" \
      --engine locust

If no engine was explicitly requested, invoke:

    poetry run python scripts/performance_workflow.py select-engine \
      --profile "workspaces/<scenario>-gemini/execution-profile.yaml"

and allow the human to select JMeter or Locust interactively.

Never silently select an execution engine when the human has not specified one.

### Artifact preparation

After engine selection, prepare the executable artifact only through the public workflow:

    poetry run python scripts/performance_workflow.py prepare \
      --model "workspaces/<scenario>-gemini/normalized-performance-model.json" \
      --profile "workspaces/<scenario>-gemini/execution-profile.yaml"

The persisted engine determines the generated artifact.

For JMeter:

    engine: jmeter
      -> JMeterEngine
      -> governed JMX

For Locust:

    engine: locust
      -> LocustEngine
      -> locustfile.py

Do not call engine-specific generators directly.

### RUN checkpoint

RUN remains the final human confirmation immediately before real load execution.

RUN is not:

- design approval;
- execution authorization;
- engine selection.

Before requesting RUN, all of these states must already be satisfied:

    DESIGN        : APPROVED
    ENGINE        : SELECTED
    ARTIFACT      : VALID
    AUTHORIZATION : AUTHORIZED
    PREFLIGHT     : READY

After successful preflight:

1. Report the selected engine.
2. Report the validated executable artifact.
3. Report PRE_EXECUTION_READY.
4. Stop.
5. Request exact RUN.

Only after the human enters exactly RUN may real load execution begin.

### Immutability after preflight

After successful preflight, do not modify:

- selected engine;
- workload;
- users or threads;
- ramp-up;
- duration;
- pacing;
- target;
- execution profile;
- generated executable artifact;
- runtime data contract.

A different engine requires a new governed preparation/preflight cycle.

### Runtime dispatch

The selected engine controls execution.

JMeter:

    execution-profile.yaml
      engine: jmeter
          |
          v
      JMeterEngine
          |
          v
      JMX
          |
          v
      JMeter runtime

Locust:

    execution-profile.yaml
      engine: locust
          |
          v
      LocustEngine
          |
          v
      locustfile.py
          |
          v
      Locust runtime

Both execution paths must converge into deterministic analysis and the common HTML/PDF reporting layer.

### Safety invariants

Never:

- infer JMeter only because a JMX exists;
- infer Locust only because Locust is installed;
- switch engines silently;
- execute both engines for one approved execution;
- change engine after successful preflight;
- run load during intake, review or engine preparation;
- bypass performance_workflow.py for a normal governed execution.

---

## GOVERNED MULTI-ENGINE RUNTIME - FINAL CONTRACT

The governed execution path is engine-agnostic.

Mandatory order:

1. Engine is selected and persisted before preparation.
2. The engine artifact is generated and validated.
3. Preflight creates `controlled-engine-v3.json`.
4. The manifest records immutable SHA-256 hashes for:
   - approved plan;
   - execution profile;
   - selected engine artifact.
5. Preflight ends at `PRE_EXECUTION_READY`.
6. Execution MUST reuse the existing preflight manifest.
7. Execution MUST NOT regenerate or re-baseline that manifest.
8. The user must type exact `RUN`.
9. After `RUN`, the exact manifest and artifact hashes are verified again.
10. The persisted engine is resolved through the engine resolver.
11. Execution is dispatched only through the selected `PerformanceEngine.execute()` implementation:
    - `JMeterEngine.execute()` for JMeter;
    - `LocustEngine.execute()` for Locust.
12. Engine selection MUST NOT occur at `RUN`.
13. Changing engine requires a new preparation and preflight cycle.
14. Direct engine execution outside the governed workflow is not the public contract.

`RUN` authorizes only the exact engine, plan, profile and executable artifact protected by the existing `PRE_EXECUTION_READY` manifest.
