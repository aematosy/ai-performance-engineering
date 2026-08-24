# Normalized Performance Model v1

This model is the neutral core between input adapters and downstream design,
validation, generation, and execution.

## Supported source types

- `POSTMAN`
- `JMX`
- `CLI`

Future adapters may add OpenAPI, HAR, k6, Gatling, Locust, or others without
changing downstream contracts.

## Core shape

```json
{
  "schema_version": "1.0",
  "source": {
    "type": "POSTMAN|JMX|CLI",
    "artifact": "optional path"
  },
  "system": {
    "type": "API"
  },
  "scenarios": [
    {
      "name": "scenario-name",
      "transactions": []
    }
  ],
  "data": {
    "strategy": "CSV|NONE_OR_PARAMETERIZED|NONE_OR_EMBEDDED",
    "csv_data_sets": [],
    "parameters": []
  },
  "runtime": {
    "correlations": []
  },
  "workload": {
    "source": "EXECUTION_PROFILE|JMX",
    "thread_groups": []
  },
  "assertions": [],
  "observability": [],
  "risks": [],
  "findings": []
}
```

## Rules

- The normalized model is not approval.
- A JMX may be accepted as input without modification.
- Postman input may later be transformed to JMX.
- CLI input should derive workload from an execution profile rather than from
  hard-coded defaults.
- Input adapters must redact secrets.
- Downstream components should depend on this model, not on raw Postman/JMX
  syntax wherever practical.
