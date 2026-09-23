# Contrato del reporte

## Fuentes de verdad

- `analysis.json`: veredicto y SLA determinísticos.
- `results.jtl`: métricas de runtime y labels/transacciones.
- `intelligence.json`: riesgo, tendencia y recomendación complementaria.
- `execution-profile.yaml`: workload aprobado.
- `JMX`: request template y correlaciones disponibles.

## Semántica ejecutiva

El reporte debe conservar el código técnico, pero explicar primero su significado humano:

- PASS -> Cumple los criterios configurados para esta carga.
- FAIL -> No cumple uno o más criterios configurados.
- LOW -> Riesgo bajo.
- ACCEPT -> Apto para conservar como evidencia de esta ejecución.

No afirmar capacidad máxima, estabilidad de largo plazo ni ausencia total de defectos a partir de una sola línea base.

## Objetivo

`Objetivo` describe qué se valida; `Target` describe dónde se ejecuta. Para una sola transacción, el objetivo puede describir `METHOD path` y el Target puede conservar `METHOD URL`. Para escenarios con varias transacciones, el objetivo describe el escenario/workload y el Target usa el sistema/base URL. Nunca duplicar ambos campos ni convertir `Target` en `Objetivo`.

## Evidencia

`RUNTIME_REQUEST_RESPONSE_VERIFIED` exige request y response reales de runtime.
`REQUEST_TEMPLATE_PLUS_RUNTIME_STATUS` combina request de JMX con estado real de JTL.
`STATUS_ONLY` solo prueba resultado HTTP/assertions.
`NOT_AVAILABLE` significa que no existe evidencia adicional.
