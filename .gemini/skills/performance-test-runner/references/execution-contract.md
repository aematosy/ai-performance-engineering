# Controlled Execution Contract

## Artifact validation

Antes del preflight:

```bash
poetry run python scripts/validate_jmx_artifact.py \
  --plan tests/plans/<scenario>/test-plan.yaml \
  --jmx tests/generated/<scenario>.jmx
```

Continuar solo si termina con `JMX ARTIFACT VALID`.

## Preflight inmutable

Ejecutar:

```bash
poetry run python scripts/run_approved_plan.py \
  --plan tests/plans/<scenario>/test-plan.yaml \
  --jmx tests/generated/<scenario>.jmx \
  --preflight
```

Este comando extrae del plan aprobado el target, environment, users, ramp-up, duration y pacing. No acepta overrides de carga.

Presentar al usuario exactamente el preflight devuelto y solicitar autorización explícita.

No inferir seguridad a partir del nombre del environment.

## Environment validation

Después de autorización explícita:

```bash
poetry run python scripts/validate_environment.py
```

Si falla, detenerse.

## Execution

Solo después de la autorización humana posterior al preflight:

```bash
poetry run python scripts/run_approved_plan.py \
  --plan tests/plans/<scenario>/test-plan.yaml \
  --jmx tests/generated/<scenario>.jmx \
  --authorized
```

No construir manualmente `run_test.py` ni introducir overrides de target/users/ramp-up/duration.

No introducir `--skip-*` salvo solicitud explícita y justificada.

No alterar valores aprobados para buscar un PASS.
