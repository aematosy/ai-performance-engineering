---
name: performance-test-runner
description: Prepara y ejecuta de forma gobernada pruebas de Performance Engineering previamente diseñadas y aprobadas.
---

# Performance Test Runner

Responde al usuario en español.

## Principio principal

El humano aprueba decisiones.

aXet Code no orquesta operaciones internas.

## Único entrypoint normal de ejecución

Usa exclusivamente:

scripts/natural_performance_execute.sh

Para continuar un escenario aprobado:

scripts/natural_performance_execute.sh --scenario "<scenario>"

No inspecciones el script.

No ejecutes --help.

No reconstruyas internamente el workflow.

## Después de aprobación humana

Cuando el usuario diga que aprueba el diseño y el workload:

NO invoques:

- scripts/approve_test_plan.py;
- approve;
- authorize;
- prepare;
- preflight;
- execute;
- performance_workflow.py;
- run_governed_engine.py.

La aprobación humana ya fue expresada en conversación.

Continúa únicamente mediante:

scripts/natural_performance_execute.sh --scenario "<scenario>"

## Selección de motor

La selección del motor ocurre antes de preparar la ejecución.

Si el usuario NO indica motor:

- no selecciones JMeter ni Locust silenciosamente;
- invoca el front door natural de ejecución;
- deja que el workflow solicite la selección humana del motor.

Si el usuario indica explícitamente JMeter o Locust, esa decisión humana
es autoritativa y DEBE persistirse antes de preparar la ejecución.

Usa únicamente el workflow público:

```bash
poetry run python scripts/performance_workflow.py select-engine \
  --profile "<execution-profile.yaml>" \
  --engine "<jmeter|locust>" \
  --allow-change
```

Solo si esa selección termina correctamente, continúa mediante:

```bash
scripts/natural_performance_execute.sh --scenario "<scenario>"
```

Reglas obligatorias:

- nunca pasar `--engine` a `natural_performance_execute.sh`;
- nunca pasar `--engine` a `natural_performance_execute.py`;
- nunca ignorar un motor solicitado explícitamente por el usuario;
- si `select-engine` falla, detenerse y mostrar el error exacto;
- no investigar, reintentar ni probar rutas alternativas tras un error;
- un cambio de motor invalida únicamente el estado derivado que dependa del motor;
- no borrar evidencia histórica de ejecuciones anteriores;
- después de cambiar motor, preparar/validar el artefacto correspondiente y ejecutar preflight;
- antes de pedir `RUN`, verificar que el motor persistido coincide con el solicitado.

## RUN

RUN es el gate final de ejecución.

RUN no selecciona motor.
RUN no cambia motor.
RUN no aprueba diseño.
RUN únicamente confirma el inicio de la carga ya preparada, autorizada y validada.

Antes de RUN debe existir un resumen PRE_EXECUTION_READY.

## Reanudación

Si existe estado válido:

- reutiliza aprobación;
- reutiliza autorización;
- reutiliza engine;
- reutiliza preflight;
- reutiliza artefactos válidos.

No repitas etapas completadas.

## Errores

Si el entrypoint natural devuelve un error técnico:

- informa el error;
- detente.

No pruebes comandos internos alternativos.

No hagas retries manuales con approve, authorize, prepare, preflight o execute.

## Finalización

Después de ejecución:

- presenta el resumen devuelto por el flujo;
- no reconstruyas métricas por tu cuenta;
- no selecciones un reporte histórico distinto;
- utiliza el estado/reporting asociado a esa ejecución.

## Runtime secret rule

Execution is non-interactive with respect to secrets.

Never request passwords, tokens, API keys, client secrets, or other secret
values from the user through chat or Shell.

Never call an interactive secret materializer.

The runner consumes only runtime properties already materialized by the
approved design flow or another explicitly configured non-interactive secret
provider.

If required runtime properties are unavailable, stop before load.

## Regla de cierre después de ejecutar

Cuando el workflow público termine correctamente y muestre
`EJECUCIÓN FINALIZADA`:

- no activar automáticamente `performance-results-analyst`;
- no volver a leer `analysis.json`;
- no volver a leer `metadata.json`;
- no leer JTL, CSV, logs ni reportes salvo solicitud explícita;
- no ejecutar comandos adicionales;
- no iniciar investigación adicional;
- no reconstruir métricas que el workflow ya calculó.

La respuesta final debe usar únicamente el resumen ya producido por el
workflow y terminar inmediatamente.

Mostrar solamente:

- scenario;
- engine;
- resultado/veredicto;
- requests;
- error rate;
- throughput;
- p95;
- p99;
- ruta de resultados;
- ruta del reporte.

`performance-results-analyst` se activa únicamente si el usuario pide
explícitamente analizar, interpretar, comparar, diagnosticar o explicar
los resultados.



## Dual scenario identity - authoritative handoff

Esta regla tiene prioridad sobre cualquier instrucción anterior que pueda
confundir el scenario solicitado por el usuario con el scenario canónico
descubierto por Postman.

Para diseños Postman pueden coexistir dos identidades válidas:

- REQUESTED SCENARIO: identidad pública solicitada por el usuario y usada
  para `workspaces/<requested-scenario>/`.
- CANONICAL SCENARIO: identidad técnica descubierta por el análisis Postman
  y usada para `tests/plans/<canonical-scenario>/`, `work/postman/...`,
  `data/...`, artefactos de motor, resultados y reportes.

Ejemplo válido:

```text
requested: restful-booker-e2e-demo
canonical: booking-e2e
```

El front door público de ejecución SIEMPRE debe invocarse con el REQUESTED
SCENARIO original:

```bash
scripts/natural_performance_execute.sh   --scenario "restful-booker-e2e-demo"
```

NUNCA sustituir manualmente ese argumento por el scenario canónico:

```text
booking-e2e
```

El front door ya es responsable de resolver internamente:

```text
requested scenario
    -> workspace/execution-profile.yaml
    -> resolve_execution_scenario.py
    -> canonical scenario
    -> plan / model / artifact / execution
```

Por lo tanto:

- no construir `workspaces/<canonical-scenario>/execution-profile.yaml`
  cuando el diseño Postman usa dual identity;
- no copiar ni renombrar el workspace para igualarlo al scenario canónico;
- no invocar `natural_performance_execute.sh` con el canonical scenario
  después de una aprobación del diseño solicitado bajo otro nombre;
- conservar el REQUESTED SCENARIO durante approval -> preparation handoff;
- permitir que `natural_performance_execute.sh` resuelva el CANONICAL SCENARIO;
- si el front door falla, detenerse y mostrar el error exacto, sin intentar
  rutas alternativas.

Antes de preparar ejecución, si existe:

```text
workspaces/<requested-scenario>/execution-profile.yaml
```

y el plan está bajo otra identidad canónica, esto NO es un error: es el
contrato esperado de dual scenario identity.
