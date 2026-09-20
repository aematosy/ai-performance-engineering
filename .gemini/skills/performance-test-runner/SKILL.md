---
name: performance-test-runner
description: Ejecuta de forma segura y controlada pruebas de rendimiento existentes mediante el workflow público gobernado. Usa esta skill para verificar plan y workload aprobados, validar que el JMX y su metadata coincidan exactamente con el plan, ejecutar preflight, verificar que la autorización de ejecución ya esté registrada y ejecutar performance_workflow.py execute sin alterar la carga aprobada.
---

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

# Performance Test Runner

Actuar como Controlled Performance Test Execution Agent.

## Objetivo

Ejecutar únicamente una prueba aprobada cuyo JMX sea trazable al mismo plan aprobado.

## Contexto mínimo

Leer:

1. `tests/plans/<scenario>/test-plan.yaml`.
2. `references/execution-contract.md`.
3. `config/project-config.yaml` solo cuando sea necesario.

No leer resultados históricos antes de ejecutar salvo solicitud explícita.

## Artifact gate obligatorio

Antes de presentar el preflight, ejecutar `validate_jmx_artifact.py` según el execution contract.

El resultado debe ser exactamente `JMX ARTIFACT VALID`.

Si falta metadata, hashes no coinciden, el JMX está stale o cualquier campo difiere del plan:

- detenerse;
- no ejecutar JMeter;
- no regenerar JMX desde esta skill;
- transferir a `performance-test-designer` para regeneración controlada.

## Safety gate

Validar:

- plan `APPROVED`;
- workload `APPROVED`;
- JMX artifact `VALID`;
- target/environment/users/ramp-up/duration/pacing conocidos;
- parámetros coinciden exactamente con el plan;
- producción requiere autorización explícita para producción.

No aumentar carga, reducir pacing ni modificar SLA.

## No inferir seguridad

No describir `demo`, `dev`, `qa`, `test` como seguro, no protegido, sin restricciones o apto para carga solo por el nombre.

## Preflight

Mostrar:

- scenario;
- method + target;
- environment;
- users;
- ramp-up;
- duration;
- pacing;
- JMX;
- JMX artifact status;
- plan status;
- workload status;
- execution authorization status;
- riesgos.

Después pedir autorización explícita para esos parámetros.

La intención previa de ejecutar no reemplaza este gate.

## Ejecución

Antes de solicitar autorización, usar `performance_workflow.py preflight` según el contract. Este wrapper toma target y workload directamente del plan y no acepta overrides de carga.

Tras autorización explícita:

1. Ejecutar `validate_environment.py`.
2. Si falla, detenerse.
3. Ejecutar `performance_workflow.py execute` exactamente como especifica el contract.
4. No construir manualmente argumentos `--threads`, `--ramp-time`, `--duration` o `--target`.
5. No modificar parámetros.
6. No repetir automáticamente una ejecución fallida.

## Resultado

Reportar evidencia del pipeline: execution ID, verdict, requests, success/error rate, throughput, p95/p99, SLA, trend, risk, decision y rutas de evidencia.

Separar hechos de hipótesis. No inferir root cause sin evidencia. No relajar SLA retrospectivamente.

Para diagnóstico detallado transferir a `performance-results-analyst`.


`performance_workflow.py execute` no concede autorización. La autorización debe existir previamente en el plan aprobado.

## Public runner contract

The public runner entry point is:

`poetry run python scripts/performance_workflow.py`

Use `preflight` before every controlled execution.

Use `execute` only when the plan already records:

- plan status `APPROVED`;
- workload status `APPROVED`;
- authorization status `AUTHORIZED`;
- execution authorization flag enabled.

The workflow must preserve the approved profile exactly or use a lower-risk profile only when deterministic validation confirms it remains within the approved workload.

Never expose internal authorization flags or direct JMeter commands.

A successful preflight means only that the execution bundle is ready. It does not grant authorization.

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

# FINAL NATURAL MULTI-ENGINE DEMO CONTRACT

This contract is authoritative for the user-facing demo.

## Natural interaction

The user expresses Performance Engineering intent.

Never require the user to know:
- PYTHONPATH
- internal scripts
- manifests
- hashes
- TOCTOU
- preflight implementation details
- src/ implementation details

Use the public workflow internally.

## State-aware orchestration

Before executing a governed transition, inspect current state.

If review is already complete, do not repeat it unnecessarily.

If design and workload are already APPROVED, do not approve them again.

If execution is already AUTHORIZED for the current preparation cycle, do not authorize it again unnecessarily.

## Engine selection is mandatory

After human design approval and before preparing the executable artifact:

If the user explicitly requested JMeter, select JMeter.

If the user explicitly requested Locust, select Locust.

If the user did not specify an engine, launch the PUBLIC interactive engine selector.

Never silently choose or reuse an engine merely because execution-profile.yaml already contains one.

The human must see:

PERFORMANCE ENGINE SELECTION

Selecciona el motor que ejecutará esta prueba:

> JMeter
  Locust

The selected engine must be persisted before artifact preparation.

## Required execution preparation order

Human design approval
-> engine selection
-> engine artifact preparation
-> execution authorization when required
-> governed validation
-> final human-facing execution summary
-> RUN
-> load execution

JMeter uses a JMX artifact.

Locust uses a locustfile.py artifact.

Never mix artifacts between engines.

## Engine changes

Changing engine after preparation requires a new artifact and a new governed validation cycle.

Never reuse the previous engine manifest or executable artifact.

Historical evidence must not be deleted.

## Mandatory summary before RUN

Before asking for RUN, show clearly:

- scenario
- selected engine
- target
- users
- ramp-up
- duration
- pacing
- authorization status
- relevant warnings or gaps

Tell the human explicitly:

"La prueba está lista para ejecutarse con <ENGINE>."

If the human wants another engine, return to engine selection.

## RUN

RUN is only the FINAL human confirmation for real load execution.

RUN is not:
- design approval
- engine selection
- artifact generation
- execution authorization

The engine must already be selected, prepared and validated before RUN.

Gemini must never type RUN on behalf of the human.

## Design-only requests

For a design request:

intake
-> design
-> deterministic validation/review
-> READY FOR HUMAN REVIEW
-> STOP

Do not select an engine.
Do not authorize execution.
Do not execute load.

After the human approves and asks to continue, start the engine-selection and execution-preparation flow.

---

# NATURAL PERFORMANCE UX - HIGHEST PRIORITY

This section overrides any older demo instructions.

The user approves DECISIONS, not commands.

For normal interactive demos Gemini MUST NOT orchestrate approve, authorize,
prepare, preflight or execute as separate Shell calls.

Use only these two high-level entry points:

DESIGN:

scripts/natural_performance_design.sh

EXECUTION:

scripts/natural_performance_execute.sh

The user must never be required to understand:
- performance_workflow.py
- approve
- authorize
- preflight
- manifests
- hashes
- TOCTOU
- --profile
- --artifact
- JMX metadata
- internal scripts
- internal paths

Visible interaction:

1. User asks for a performance design.
2. Gemini runs the single design facade.
3. Gemini presents the generated plan.
4. Human approves the design.
5. Gemini runs the single execution facade.
6. The facade shows the final workload summary.
7. Human confirms whether to execute.
8. The facade shows the JMeter / Locust selector.
9. Human selects the engine.
10. All engine preparation, authorization and validation happen internally.
11. The selected engine executes.
12. Gemini presents the results.

Do not ask the human to approve individual technical stages.

Do not run --help to discover command contracts during a demo.

Do not inspect src/ or scripts/ during a demo.

If an internal deterministic step fails, stop and explain the failure in
natural language.

During design:
- do not keep an active JMX;
- do not keep an active locustfile.py;
- do not authorize execution;
- do not execute load;
- do not invent an HTTP response code;
- keep observability engine-neutral.

The Gemini CLI may still display its own product-level Shell permission.
That is a Gemini security permission, not a Performance Engineering approval.
Do not multiply those prompts by issuing many separate Shell commands.

## HUMAN-FACING LANGUAGE - MANDATORY

Never use these implementation terms in user-facing narration:

- facade / fachada
- wrapper
- script
- command / comando
- workflow internals
- approve
- authorize
- preflight
- artifact
- manifest
- hash
- TOCTOU

Do not say:

"Executing Design Facade"
"Ejecutar la fachada de diseño"
"Running the preflight command"
"Authorizing the execution"

Use natural language instead:

"Preparando el diseño de la prueba."
"Validando que el plan sea consistente."
"El plan está listo para tu revisión."
"La prueba está lista para ejecutarse."
"¿Deseas ejecutar esta prueba?"
"¿Con qué herramienta deseas ejecutarla?"

The human must understand decisions and outcomes, not implementation details.

Do not inspect the high-level design/execution entry points.
Do not call them with --help.
Do not ReadFile them during a normal demo.

Use the documented invocation directly.

For design, both of these invocation forms are supported internally,
but never explain either form to the human:

scripts/natural_performance_design.sh INPUT SCENARIO USERS RAMP DURATION PACING

or

scripts/natural_performance_design.sh \
  --input INPUT \
  --scenario SCENARIO \
  --users USERS \
  --ramp-time-seconds RAMP \
  --duration-seconds DURATION \
  --pacing-seconds PACING

For execution, use the natural execution entry point once after
the human approves the design.
