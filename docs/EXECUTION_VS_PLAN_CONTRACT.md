# Execution Profile vs Approved Plan Contract v1

This gate prevents an execution profile from increasing load beyond the
Performance Test Plan that a human approved.

## Safety comparison

The requested profile is blocked when it is more aggressive than the approved
workload.

### Concurrency

`requested threads <= approved threads`

### Ramp-up

A shorter ramp-up reaches target concurrency faster and is therefore more
aggressive:

`requested ramp-up >= approved ramp-up`

### Duration

For duration-mode plans:

`requested duration <= approved duration`

### Iterations

For iteration-mode plans:

`requested iterations <= approved iterations`

### Pacing

Lower pacing means requests may occur more frequently:

`requested pacing >= approved pacing`

### Mode

The execution mode must match the approved design:

`DURATION == DURATION`

or

`ITERATIONS == ITERATIONS`

## Approval vs authorization

This validator checks workload approval only.

It does not change or grant execution authorization.

A successful result means:

`PROFILE IS WITHIN APPROVED WORKLOAD`

It does not mean:

`EXECUTION AUTHORIZED`

A separate authorization gate remains mandatory before JMeter execution.
