# Natural Design Command Contract

## Single public front door

Use only:

scripts/natural_performance_design_request.sh

## Postman

Supported invocation:

scripts/natural_performance_design_request.sh \
  --scenario "<scenario>" \
  --collection "<collection>" \
  --environment "<environment>" \
  --users <users> \
  --ramp-time-seconds <seconds> \
  --duration-seconds <seconds> \
  --pacing-seconds <seconds>

The front door owns routing into the deterministic Postman workflow.

Do not call:

- performance_workflow.py directly;
- prepare_postman_design.py directly;
- postman_pipeline.py directly;
- generate_postman_jmx.py directly;
- review_test_plan.py directly;
- validate_test_plan.py directly.

Design never executes performance load.

Design never chooses JMeter or Locust.

Human approval occurs after the validated design summary.
