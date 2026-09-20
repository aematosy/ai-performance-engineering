# Natural Execution Contract

## ONE PUBLIC ENTRYPOINT

Normal execution uses only:

scripts/natural_performance_execute.sh --scenario "<scenario>"

## HUMAN GATES

The only normal human decisions are:

1. design/workload approval;
2. engine selection: JMeter or Locust;
3. RUN.

## APPROVAL HANDOFF

After the human approves design and workload:

DO NOT call approve_test_plan.py.

DO NOT invoke approve, authorize, prepare, preflight or execute directly.

DO NOT invoke performance_workflow.py directly.

Enter the natural execution flow once.

## ENGINE SELECTION

ENGINE SELECTION happens before RUN.

Gemini never chooses the engine for the user.

RUN is not engine selection.

STOP FOR RUN only after PRE_EXECUTION_READY.

## EXECUTION COMPLETION

Successful natural execution must synchronize:

results/.state/last-execution.json

When a professional report exists it must synchronize:

results/.state/last-report.json

Reporting must never guess the newest report directory.
