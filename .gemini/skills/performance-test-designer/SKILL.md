---
name: performance-test-designer
description: Diseña pruebas de Performance Engineering seguras y reproducibles a partir de APIs, OpenAPI, Postman, cURL, HAR, documentación o JMX.
---

# Performance Test Designer

Responde en español.

## Public entrypoint

Usa únicamente:

`scripts/natural_performance_design.sh`

## Objetivo

Transformar la intención del usuario en un plan reproducible de performance sin
ejecutar carga.

## Flujo

1. Recibe el input y workload.
2. Ejecuta el flujo natural de diseño.
3. Valida el diseño.
4. Presenta el resumen.
5. Si falta el contrato HTTP, intenta resolverlo mediante una única solicitud
   funcional segura.
6. Si sigue sin resolverse, pregunta al usuario.
7. Espera aprobación del diseño y workload.

## Functional probe

Cuando el HTTP esperado no esté declarado, se permite una single functional
request.

Esa solicitud:

- se ejecuta una sola vez;
- no usa concurrencia;
- no usa ramp-up;
- no es una prueba de performance.

Un 2xx observado puede proponerse como contrato esperado.

Un error o respuesta ambigua no debe convertirse automáticamente en contrato
de éxito.

## Prohibido

No invoques directamente:

- approve
- authorize
- prepare
- preflight
- execute
- JMeter
- Locust

No uses `--help`.

No inspecciones scripts durante una ejecución normal.

No inventes status HTTP.

No ejecutes carga.

## Resultado

Presenta:

- scenario;
- target;
- workload;
- SLA;
- expected HTTP;
- riesgos;
- información funcional pendiente.

Luego espera aprobación humana.
