# Controlled Runner v2

`run_approved_plan.py` becomes the only supported user-facing entry point for
controlled execution.

## Safety chain

Every invocation runs a fresh Pre-Execution Gate v2 for the exact artifacts
that may be executed.

The runner then verifies the SHA-256 values from the generated manifest.

For execution mode, the runner additionally requires:

- `plan.status == APPROVED`
- `workload.status == APPROVED`
- `authorization.status == AUTHORIZED`
- `approval.execution_authorized == true`
- an explicit non-generic `authorization.authorized_by`
- `authorization.authorized_at`

Only after those checks does the runner ask the human to type `RUN`.

A final hash verification is performed immediately before spawning the
low-level execution pipeline.

## Important semantic change

The low-level `run_test.py --authorized` flag is now an internal handoff only.

It is **not** the source of authorization.

Authorization comes from the approved plan state checked by the controlled
runner.

## Runtime compatibility in v2

The existing low-level runner currently accepts JMeter runtime properties for:

- threads
- ramp time
- duration
- Prometheus port

It does not yet expose deterministic runtime overrides for:

- iterations
- pacing

Therefore Controlled Runner v2 intentionally blocks:

- `ITERATIONS` execution profiles;
- a pacing value different from the approved plan/JMX value.

This is a fail-closed compatibility rule, not a permanent platform limitation.

## Preflight

`--preflight` executes all deterministic safety checks and verifies artifact
hashes, but never starts JMeter.

It may be used while authorization is still PENDING.

## Execute

`--execute` requires both authorization and final interactive confirmation.

`Type RUN` is confirmation only.

It never changes PENDING into AUTHORIZED.
