---
name: performance-test-runner
description: Prepara y ejecuta de forma gobernada pruebas de Performance Engineering previamente diseñadas y aprobadas.
---

# Performance Test Runner

Responde al usuario en español.

## Principio principal

El humano aprueba decisiones.

Gemini no orquesta operaciones internas.

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

La selección JMeter / Locust pertenece al flujo natural.

No selecciones el motor por el usuario.

Si el flujo solicita selección:

- presenta las opciones;
- espera la decisión humana;
- continúa con el mismo flujo natural.

No invoques select-engine directamente.

## RUN

RUN es el gate final de ejecución.

RUN no selecciona motor.

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
