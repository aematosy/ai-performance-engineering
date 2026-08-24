# Execution Profile Contract v1

Execution load is supplied by a file, not by ad-hoc manual CLI values.

## Modes

Exactly one execution mode is active:

- `DURATION`
- `ITERATIONS`

`DURATION` requires:

- `duration_seconds >= 1`
- `iterations: null`

`ITERATIONS` requires:

- `iterations >= 1`
- `duration_seconds: null`

## Data policy

The execution profile controls CSV behavior:

- `recycle`
- `stop_thread_on_eof`
- `sharing_mode`
- `row_consumption`

Supported row-consumption modes:

- `PER_ITERATION`
- `PER_THREAD`

## Capacity safety

For finite iteration executions with `PER_ITERATION` and `all_threads` sharing:

`required rows = threads × iterations`

For duration-based `PER_ITERATION` execution with recycling disabled, exact
capacity cannot be proven from configuration alone. Execution-ready validation
therefore blocks the run.

This deliberately favors deterministic safety over guessing throughput.

## Next governance layer

This profile validates only internal consistency and CSV capacity.

A later validator must compare the requested profile against the workload
limits approved in the Performance Test Plan. A valid profile is not, by
itself, authorization to execute.
