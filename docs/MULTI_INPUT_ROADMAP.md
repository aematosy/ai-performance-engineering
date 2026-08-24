# Multi-input Performance Engineering Core

## Phase 1 - Intake core

1. Detect input type.
2. Normalize JMX.
3. Normalize CLI.
4. Reuse existing Postman pipeline.
5. Validate common normalized model.
6. Produce an intake manifest.

## Phase 2 - Data model

1. Classify configuration vs test data vs runtime data vs secrets.
2. Generate CSV requirements.
3. Generate CSV template.
4. Validate row capacity and recycle strategy.

## Phase 3 - Execution profiles

1. Add `config/execution-profiles/*.yaml`.
2. Validate schema.
3. Compare requested execution with approved workload.
4. Block escalation beyond approved limits.

## Phase 4 - Correlation inference

1. Infer deterministic Postman JSON extractors.
2. Parse JMX existing extractors.
3. Represent both in normalized runtime correlations.

## Phase 5 - Designer integration

1. Feed only normalized/minimal design context to the AI designer.
2. Keep approval and execution authorization separate.
3. Preserve original JMX when imported in managed mode.

## Phase 6 - Execution

1. Generated-JMX path for Postman/CLI.
2. Existing-JMX path for imported JMX.
3. Common execution profile.
4. Common result analysis and observability.
