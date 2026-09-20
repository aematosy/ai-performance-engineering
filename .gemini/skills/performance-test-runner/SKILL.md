---
name: performance-test-runner
description: Prepara y ejecuta de forma gobernada una prueba de rendimiento previamente aprobada usando JMeter o Locust.
---

# Performance Test Runner

Responde en español.

## Public entrypoint

Usa únicamente:

`scripts/natural_performance_execute.sh`

## Flujo

1. Reutiliza diseño aprobado.
2. Reutiliza cualquier estado válido persistido.
3. Permite seleccionar JMeter o Locust cuando corresponda.
4. Prepara internamente el motor seleccionado.
5. Presenta el resumen final.
6. Espera `RUN`.
7. Ejecuta.
8. Presenta resultados.

## Prohibido

No invoques directamente:

- `performance_workflow.py approve`
- `performance_workflow.py authorize`
- `performance_workflow.py prepare`
- `performance_workflow.py preflight`
- `performance_workflow.py execute`
- `run_governed_engine.py`
- JMeter
- Locust

No ejecutes `--help`.

No reconstruyas argumentos internos.

No hagas retries manuales.

No regeneres JMX en un flujo Locust.

No cambies target ni workload.

## RUN

La carga real requiere exactamente:

`RUN`

No agregues una segunda confirmación.

## Después de RUN

No repitas:

- aprobación;
- autorización;
- selección de motor;
- preparación;
- preflight.

Continúa únicamente con el flujo natural.

## Resultado

Muestra:

- requests;
- successes;
- failures;
- error rate;
- throughput;
- p95;
- p99;
- SLA;
- results path;
- report path.

Después detente.
