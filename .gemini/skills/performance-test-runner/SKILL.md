---
name: performance-test-runner
description: Ejecuta de forma segura y controlada pruebas de rendimiento existentes mediante el workflow público gobernado. Usa esta skill para verificar plan y workload aprobados, validar que el JMX y su metadata coincidan exactamente con el plan, ejecutar preflight, verificar que la autorización de ejecución ya esté registrada y ejecutar performance_workflow.py execute sin alterar la carga aprobada.
---

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
