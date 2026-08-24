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
