# Performance Engineering Core

Responsibility-based application structure.

## Layers

- application: workflow orchestration and use cases
- domain: engine-independent business contracts and models
- intake: input detection, parsing and normalization
- design: scenario discovery, correlations and test design
- execution: governance, authorization and preflight
- engines: performance engine adapters such as JMeter and Locust
- analysis: deterministic result analysis, SLA, history and trends
- reporting: evidence and professional reporting

The public CLI entrypoints remain under scripts/ during the migration.
Existing behavior must remain backward compatible.
