# Postman Design Context v1.2

## Runtime dependencies are not executable correlations

A Postman runtime variable producer/consumer relationship does not prove that
the Performance Engineering runtime knows how to extract the variable.

For every runtime dependency, the design context requires explicit extractor
metadata.

If normalized producer metadata contains:

```json
{
  "name": "access_token",
  "extraction": {
    "type": "JSON_PATH",
    "expression": "$.token"
  }
}
```

the requirement becomes:

`RUNTIME_VARIABLE / DETECTED`

Without deterministic extractor metadata it becomes:

`RUNTIME_VARIABLE / EXTRACTION_STRATEGY_REQUIRED`

and execution remains blocked.

## Resource safety

Mutating requests with static resource identifiers additionally require an
explicit resource strategy.

Blocking statuses:

- `EXTRACTION_STRATEGY_REQUIRED`
- `REVIEW_REQUIRED`
- `REQUIRED_NOT_DEFINED`

These statuses do not prevent design. They prevent execution readiness.
