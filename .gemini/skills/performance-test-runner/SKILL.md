---
name: performance-test-runner
description: Ejecuta de forma segura y controlada pruebas de rendimiento existentes con Apache JMeter y coordina Prometheus/Grafana. Usa esta skill para verificar plan y workload aprobados, validar que el JMX y su metadata coincidan exactamente con el plan, presentar el preflight, solicitar autorización humana explícita y ejecutar run_test.py sin alterar la carga aprobada.
---

# Performance Test Runner

Actuar como Controlled Performance Test Execution Agent.

## Objetivo

Ejecutar únicamente una prueba aprobada cuyo JMX sea trazable al mismo plan aprobado.

## Contexto mínimo

Leer:

1. `tests/plans/<scenario>/test-plan.yaml`.
2. `references/execution-contract.md`.
3. `config/project-config.yaml` solo cuando sea necesario.

No leer resultados históricos antes de ejecutar salvo solicitud explícita.

## Artifact gate obligatorio

Antes de presentar el preflight, ejecutar `validate_jmx_artifact.py` según el execution contract.

El resultado debe ser exactamente `JMX ARTIFACT VALID`.

Si falta metadata, hashes no coinciden, el JMX está stale o cualquier campo difiere del plan:

- detenerse;
- no ejecutar JMeter;
- no regenerar JMX desde esta skill;
- transferir a `performance-test-designer` para regeneración controlada.

## Safety gate

Validar:

- plan `APPROVED`;
- workload `APPROVED`;
- JMX artifact `VALID`;
- target/environment/users/ramp-up/duration/pacing conocidos;
- parámetros coinciden exactamente con el plan;
- producción requiere autorización explícita para producción.

No aumentar carga, reducir pacing ni modificar SLA.

## No inferir seguridad

No describir `demo`, `dev`, `qa`, `test` como seguro, no protegido, sin restricciones o apto para carga solo por el nombre.

## Preflight

Mostrar:

- scenario;
- method + target;
- environment;
- users;
- ramp-up;
- duration;
- pacing;
- JMX;
- JMX artifact status;
- plan status;
- workload status;
- execution authorization status;
- riesgos.

Después pedir autorización explícita para esos parámetros.

La intención previa de ejecutar no reemplaza este gate.

## Ejecución

Antes de solicitar autorización, usar `run_approved_plan.py --preflight` según el contract. Este wrapper toma target y workload directamente del plan y no acepta overrides de carga.

Tras autorización explícita:

1. Ejecutar `validate_environment.py`.
2. Si falla, detenerse.
3. Ejecutar `run_approved_plan.py --authorized` exactamente como especifica el contract.
4. No construir manualmente argumentos `--threads`, `--ramp-time`, `--duration` o `--target`.
5. No modificar parámetros.
6. No repetir automáticamente una ejecución fallida.

## Resultado

Reportar evidencia del pipeline: execution ID, verdict, requests, success/error rate, throughput, p95/p99, SLA, trend, risk, decision y rutas de evidencia.

Separar hechos de hipótesis. No inferir root cause sin evidencia. No relajar SLA retrospectivamente.

Para diagnóstico detallado transferir a `performance-results-analyst`.
