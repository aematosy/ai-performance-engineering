# Deterministic Command Contract

Ejecutar desde la raíz y siempre con Poetry.

## Review

```bash
poetry run python scripts/review_test_plan.py \
  --plan tests/plans/<scenario>/test-plan.yaml \
  --strict
```

## Validation

```bash
poetry run python scripts/validate_test_plan.py \
  --plan tests/plans/<scenario>/test-plan.yaml
```

## Design approval

Solo después de aprobación humana y con identidad explícita:

```bash
poetry run python scripts/approve_test_plan.py \
  --plan tests/plans/<scenario>/test-plan.yaml \
  --approved-by "<explicit human name>"
```

## JMX generation

```bash
poetry run python scripts/generate_jmx_from_plan.py \
  --plan tests/plans/<scenario>/test-plan.yaml
```

El generador es idempotente y administra su lifecycle mediante metadata SHA-256.

Nunca añadir `--force`, `--replace`, `--overwrite` o flags similares. Un JMX stale/legacy debe ser archivado y regenerado por el propio generador.

El resultado esperado incluye:

```text
tests/generated/<scenario>.jmx
tests/generated/<scenario>.jmx.meta.json
```

No ejecutar `run_test.py` desde esta skill.
