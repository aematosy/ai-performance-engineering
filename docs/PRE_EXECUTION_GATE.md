# Unified Pre-Execution Gate v2

Version 2 integrates execution-bundle coherence into the mandatory pre-run
safety chain.

## Stage order

1. `VALIDATE_ENVIRONMENT`
2. `REVIEW_TEST_PLAN`
3. `VALIDATE_TEST_PLAN`
4. `VALIDATE_EXECUTION_PROFILE`
5. `COMPARE_PROFILE_TO_APPROVED_PLAN`
6. `VALIDATE_EXECUTION_BUNDLE`
7. `VALIDATE_DATA_CAPACITY` when CSV is supplied
8. `VALIDATE_DESIGN_CONTEXT` when a design context is supplied
9. `VALIDATE_JMX_ARTIFACT` when a JMX is supplied

## Input contract

A CSV cannot be supplied alone.

`--csv` requires `--data-requirements`.

A design context also requires `--data-requirements`.

This allows candidate identity to be proven through:

`plan source binding == design-context candidate == data-requirements candidate`

## JMX path

For JMX-only execution, bundle coherence validates:

`plan metadata.name == JMX metadata scenario`

No Postman source binding is required for plans that did not originate from
Postman.

## Manifest

Manifest schema v2 hashes:

- test plan;
- execution profile;
- JMX;
- CSV;
- data requirements;
- design context.

The manifest records deterministic validation only.

It never grants execution authorization and never executes JMeter.
