# Controlled execution contract

The only supported user-facing execution entry point is `run_approved_plan.py`.

Use `--preflight` for validation only and `--execute` for an already-authorized run.

`--execute` never grants authorization. The plan must already contain:

- `authorization.status: AUTHORIZED`
- an explicit `authorized_by`
- `authorized_at`
- `approval.execution_authorized: true`

`performance_workflow.py execute` is the supported public execution operation. It never grants authorization.

Never expose `run_test.py --authorized`, direct `run_test.py`, direct `pre_execution_gate.py`, direct JMeter execution, or `run_approved_plan.py --authorized` as public commands.

The low-level runner and its authorization compatibility flags are internal implementation details only.

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
