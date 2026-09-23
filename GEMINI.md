## EXACT POSTMAN PUBLIC CLI CONTRACT

Esta sección es autoritativa y tiene prioridad sobre cualquier ejemplo anterior.

Para diseño Postman desde Gemini, usar únicamente este front door:

    scripts/natural_performance_design_request.sh

Contrato exacto de argumentos:

    --scenario "<scenario>"
    --collection "<collection.json>"
    --environment "<environment.json>"
    --users <integer>
    --ramp-time-seconds <integer>
    --duration-seconds <integer>
    --pacing-seconds <number>

Ejemplo exacto:

    ./scripts/natural_performance_design_request.sh       --scenario "restful-booker-e2e-demo"       --collection "inputs/postman/restful-booker/RestFull Booker_test.postman_collection.json"       --environment "inputs/postman/restful-booker/Production RestFull.postman_environment.json"       --users 10       --ramp-time-seconds 100       --duration-seconds 180       --pacing-seconds 2

Nombres inválidos que Gemini NO debe usar:

    --duration
    --ramp-up
    --ramp-up-seconds
    --ramp-time
    --pacing
    --input-type postman

Reglas:

- No traducir nombres naturales del workload a opciones inventadas.
- "duración" SIEMPRE se materializa como `--duration-seconds`.
- "ramp-up" SIEMPRE se materializa como `--ramp-time-seconds`.
- "pacing" SIEMPRE se materializa como `--pacing-seconds`.
- Para Postman NO pasar `--input-type`; el wrapper público resuelve el routing.
- Si el front door devuelve código distinto de 0, detenerse inmediatamente.
- No reintentar con opciones alternativas.
- No llamar directamente `natural_performance_design.sh`.

# AI Performance Engineering Platform

## Language

User-facing communication is Spanish unless the user explicitly requests
another language.

Keep technical identifiers, paths, commands, filenames and official tool names
in their original form.

## Core Principles

1. Evidence before assumptions.
2. Deterministic validation before AI interpretation.
3. Human approval before workload execution.
4. Never invent metrics, contracts, workload or authorization.
5. Never expose credentials, tokens, cookies or Authorization headers.
6. Preserve execution evidence.
7. Prefer reproducible and deterministic workflows.
8. Gemini explains decisions; the platform owns implementation details.

## Normal Performance Engineering UX

The human approves decisions, not internal commands.

The standard human-facing flow is:

User request
→ design
→ design summary
→ human approval
→ execution preparation
→ engine selection
→ final summary
→ RUN
→ execution
→ results

## Only Two Normal Entrypoints

Design:

`scripts/natural_performance_design_request.sh`

Execution:

`scripts/natural_performance_execute.sh`

These are the only normal entrypoints Gemini may invoke during a normal
Performance Engineering interaction.

## Internal Operations

The following are implementation details and MUST NOT be orchestrated manually
by Gemini during the normal flow:

- approve
- authorize
- select-engine
- prepare
- preflight
- execute
- direct `performance_workflow.py` operations
- direct engine runner operations
- direct JMeter execution
- direct Locust execution
- manifest manipulation
- hash manipulation
- JMX metadata synchronization

Gemini MUST NOT:

- construct these commands;
- inspect `--help` to discover their arguments;
- inspect source code during a successful normal workflow;
- retry failed argparse combinations;
- rebuild internal state manually;
- ask the user to approve technical commands.

If the natural entrypoint reports an implementation failure, report it
concisely and stop.

## Design Flow

For a design request:

1. Use `scripts/natural_performance_design_request.sh`.
2. Do not inspect the script first.
3. Do not call `--help`.
4. Do not execute load.
5. Present the resulting design in Spanish.
6. Ask only meaningful unresolved functional questions.
7. Wait for design/workload approval.

## Functional HTTP Contract Discovery

When the expected HTTP status is not declared, prefer a single functional
request.

A single functional request:

- is not a performance test;
- uses one request only;
- has no concurrency;
- has no ramp-up;
- has no repeated load.

A successful observed 2xx response may be proposed as the expected contract.

Do not silently treat arbitrary failure responses as the expected success
contract.

If the response is ambiguous or unsuccessful, keep the contract unresolved and
ask the human.

Examples requiring confirmation include:

- 401
- 403
- 404
- 409
- 429
- 5xx

## After Design Approval

After the human approves design and workload:

Use only:

`scripts/natural_performance_execute.sh`

Do not manually call:

- approve;
- authorize;
- prepare;
- preflight;
- execute.

The natural execution flow owns those operations internally.

## Engine Selection

Supported engines:

- JMeter
- Locust

If no engine was explicitly requested, allow the human to choose.

Do not silently change an engine after selection.

Before engine selection, keep the workflow engine-neutral.

Do not mention or generate JMX merely because JMeter exists.

Do not mention Locust-specific implementation details before Locust is selected.


For Postman design, do not describe the design as ready for approval while any selected
transaction has `expected_status: UNRESOLVED`. The public design front door owns any
engine-neutral functional contract discovery needed to close that gap. A single functional
E2E traversal is validation, not performance load.

## Final Summary Before Load

Before real load, show:

- scenario;
- target;
- expected HTTP contract;
- engine;
- users;
- ramp-up;
- duration;
- pacing;
- SLA thresholds;
- readiness state.

## RUN Gate

Real load starts only after exact:

`RUN`

Do not ask an additional yes/no question after RUN.

RUN is the final human execution confirmation.

## After RUN

After RUN:

- do not redesign;
- do not reapprove;
- do not reauthorize manually;
- do not repeat preflight manually;
- do not reselect the engine;
- do not change target;
- do not change workload.

Continue only through the natural execution flow.

## Observability

JMeter and Locust must expose the same conceptual experience:

- current throughput;
- current p95;
- error rate;
- active virtual users;
- engine ACTIVE / INACTIVE;
- throughput over time;
- response percentiles;
- virtual users over time;
- errors;
- total requests.

After execution:

- current throughput = 0;
- current p95 = 0;
- error rate = 0;
- active users = 0;
- engine state = INACTIVE;
- historical graphs remain visible for the selected time range.

## Results

After execution summarize only useful evidence:

- scenario;
- engine;
- total requests;
- successful requests;
- failed requests;
- error rate;
- throughput;
- p95;
- p99;
- SLA result;
- results location;
- report location.

A target HTTP error is test evidence.

It is not automatically an engine/runtime failure.

## Reporting Source of Truth

Reports must be generated from the execution that just completed.

Never silently select an unrelated previous execution.

The completed execution identifier must be propagated deterministically to the
reporting layer.

## Token and Tool Efficiency

During the normal flow:

- do not inspect unrelated files;
- do not load large files unnecessarily;
- do not call `--help`;
- do not rediscover known CLI syntax;
- do not rerun successful validation;
- do not perform speculative retries;
- do not continue reasoning after a complete deterministic result is already
  available.

After execution completes, summarize the deterministic result immediately and
stop.

## MULTI-ENGINE EXECUTION

ENGINE SELECTION happens before RUN.

Engine selection happens before RUN.

Do not change engine after preflight, readiness validation, or persisted engine
selection.

STOP FOR RUN happens only after the engine has been selected, prepared and validated.

RUN is not engine selection.

RUN only confirms execution of the already selected and validated engine.

Once the engine is persisted, subsequent preparation, resume and execution must
reuse that same engine unless the user explicitly starts a new approved flow.

<!-- NATURAL_EXECUTION_HANDOFF_START -->

## NATURAL EXECUTION HANDOFF

After the user approves design and workload, do not invoke internal approval,
authorization, prepare, preflight or execute operations directly.

Use only:

scripts/natural_performance_execute.sh --scenario "<scenario>"

The natural flow owns approval persistence, engine selection, preparation,
authorization, preflight, RUN gating, execution and completion state.

The human chooses JMeter or Locust when requested.

The human confirms actual load with RUN.

<!-- NATURAL_EXECUTION_HANDOFF_END -->

## Execution completion policy

After the public performance execution workflow completes successfully:

- stop orchestration immediately;
- do not activate `performance-results-analyst` automatically;
- do not re-read execution artifacts;
- do not inspect `analysis.json`, `metadata.json`, JTL, CSV, logs or reports;
- do not perform post-execution investigation unless explicitly requested.

Return a concise execution summary from the workflow output and end the turn.

Use `performance-results-analyst` only when the user explicitly requests
analysis, interpretation, comparison or diagnosis of an existing execution.
