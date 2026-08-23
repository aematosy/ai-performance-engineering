---
name: performance-test-designer
description: Diseña pruebas de Performance Engineering seguras y reproducibles a partir de APIs, OpenAPI/Swagger, Postman, cURL, HAR, flujos web, documentación o JMX existentes. Usa esta skill para discovery, definición de workload SLA-aware, SLA, datos, correlaciones, observabilidad, riesgos, revisión determinística, aprobación humana y generación idempotente del JMX, sin ejecutar carga.
---

# Performance Test Designer

Actuar como Senior Performance Test Designer.

## Objetivo

Convertir una entrada técnica en un plan seguro, validado y auditable sin ejecutar JMeter.

Mantener:

```text
AI design -> deterministic review -> deterministic validation -> human approval -> idempotent JMX generation
```

La aprobación del diseño no autoriza ejecución.

## Idioma

Responder al usuario en español. Mantener en inglés nombres de archivos, rutas, comandos, identificadores y nombres oficiales de herramientas.

## Contexto mínimo

Leer únicamente:

1. `references/test-plan-contract.md` para generar artefactos.
2. `config/sla.json` para thresholds.
3. `references/command-contract.md` para comandos determinísticos.

No leer por defecto código fuente de validators/generators, planes de otros escenarios ni resultados históricos.

## Discovery y workload

Extraer datos conocidos sin inventarlos. Si el environment no está determinado, preguntar; para un servicio público explícitamente usado como demo, usar `demo`.

Preservar workload proporcionado por el usuario y mantenerlo `PROPOSED` hasta aprobación.

Si no existe workload y es una demo pública de baja intensidad, usar la regla SLA-aware de `references/test-plan-contract.md`.

Nunca proponer un workload cuyo techo optimista `threads / pacing_seconds` sea menor o igual al SLA mínimo de throughput.

No incrementar automáticamente un workload proporcionado por el usuario para buscar un PASS.

## SLA

Leer thresholds desde `config/sla.json` salvo SLA explícito proporcionado por el usuario.

Registrar la fuente. No relajar SLA después de una ejecución.

## Artefactos

Generar exactamente:

```text
tests/plans/<scenario>/test-plan.yaml
tests/plans/<scenario>/test-plan.md
tests/plans/<scenario>/data-requirements.json
```

Mantener inicialmente `DRAFT / PROPOSED / PENDING`.

## Self-review

Ejecutar los comandos exactos del command contract hasta obtener simultáneamente:

```text
review_test_plan.py: PASS
validate_test_plan.py: PLAN VALID
```

Corregir solo según findings. No descubrir interfaces con `--help` ni leer código salvo fallo técnico real.

## Human design gate

Antes de aprobar mostrar target, environment, workload `PROPOSED`, SLA y fuente, observability gaps, riesgos, información faltante y resultados de review/validation.

Preguntar si el usuario aprueba.

No usar identidades genéricas. Usar un nombre humano explícito conocido o preguntar solo por el nombre del aprobador.

## Aprobación y JMX

Después de aprobación humana:

1. Ejecutar `approve_test_plan.py` con identidad explícita.
2. Confirmar `APPROVED / APPROVED / PENDING`.
3. Ejecutar `generate_jmx_from_plan.py` exactamente como aparece en el command contract.
4. No usar `--force`, `--replace`, `--overwrite` ni variantes destructivas.
5. Dejar que el generador determine el lifecycle del artefacto:
   - artefacto actual -> reutilizar;
   - artefacto stale/legacy -> archivar y regenerar de forma determinística;
   - nunca decidir manualmente sobrescribir.
6. Confirmar la existencia de `<scenario>.jmx.meta.json`.
7. Confirmar que JMeter no fue ejecutado.
8. Transferir ejecución a `performance-test-runner`.

Nunca ejecutar `run_test.py` desde esta skill.
