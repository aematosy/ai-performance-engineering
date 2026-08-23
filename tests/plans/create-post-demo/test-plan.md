# Plan de Pruebas de Rendimiento: create-post-demo

**Estado:** `APPROVED`  
**Versión:** 1.0  
**Fecha:** 2026-08-22  
**Autor:** Gemini CLI Performance Designer

---

## 1. Objetivo

Evaluar el comportamiento inicial del endpoint `POST /posts` bajo una carga simulada y controlada, estableciendo una línea base técnica para posteriores comparaciones.

Este escenario sirve para validar el flujo de Performance Engineering y observar métricas desde el cliente. No debe interpretarse como una prueba de capacidad productiva ni como benchmark de persistencia real.

## 2. Alcance

- **Transacción:** creación de posts mediante `POST /posts`.
- **Protocolo:** HTTPS.
- **Puerto:** 443.
- **Entorno:** `demo`.
- **Host:** `jsonplaceholder.typicode.com`.
- **Tipo de prueba:** `BASELINE`.
- **Estado del workload:** `PROPOSED`.

## 3. Fuera de alcance

- Stress testing.
- Spike testing.
- Endurance testing.
- Pruebas de producción.
- Browser automation.
- Validación de capacidad de base de datos.
- Análisis de CPU, memoria, GC, red o dependencias internas del servidor.
- Conclusiones de root cause server-side sin evidencia adicional.

## 4. Sistema bajo prueba

- **Nombre:** JSONPlaceholder API.
- **Tipo:** API REST pública de demostración.
- **Autenticación:** ninguna.
- **Persistencia real:** no aplicable para benchmark de almacenamiento.

## 5. Escenario

### create-post-demo

Enviar una request `POST /posts` con payload parametrizado:

```json
{
  "title": "${title}",
  "body": "${body}",
  "userId": ${userId}
}
```

Respuesta HTTP esperada:

`201 Created`

Validaciones:

- response code `201`;
- existencia de `$.id` en la respuesta.

## 6. Workload

El workload se mantiene en estado `PROPOSED`.

Valores propuestos:

- **Threads:** 5.
- **Ramp-up:** 10 segundos.
- **Duración:** 60 segundos.
- **Pacing:** 1.0 segundo.

Estos valores no están aprobados y pueden modificarse antes de la ejecución.

La intención es realizar una línea base técnica de baja intensidad sobre un servicio público compartido.

## 7. SLA

La referencia actual proviene de:

`config/sla.json`

Thresholds configurados:

| Métrica | Threshold |
| --- | ---: |
| Error rate | <= 1.0% |
| p95 | <= 1000 ms |
| p99 | <= 2000 ms |
| Minimum throughput | >= 1.0 req/s |

Estos thresholds corresponden a la configuración actual de la plataforma. Si existe un SLA específico del servicio, debe reemplazar o complementar estos valores mediante una decisión explícita.

## 8. Datos de prueba

Los requisitos se encuentran en:

`tests/plans/create-post-demo/data-requirements.json`

Campos:

- `title`
- `body`
- `userId`

Los datos son sintéticos o parametrizados.

No se requiere información sensible.

No se asume que los datos representen usuarios productivos reales.

## 9. Correlaciones

No se requiere correlación de entrada para ejecutar la transacción.

Se documenta una extracción de salida:

- **Variable:** `extracted_post_id`
- **Fuente:** `01_CreatePost`
- **Tipo:** `JSON_PATH`
- **Expression:** `$.id`

La extracción sirve para validación o para flujos posteriores si fueran agregados.

## 10. Observabilidad

Disponibilidad actual:

- JMeter Prometheus Listener: `http://localhost:9270/metrics`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Brecha de observabilidad:

No se dispone de métricas server-side de JSONPlaceholder, como:

- CPU;
- memoria;
- I/O;
- base de datos;
- GC;
- thread pools;
- connection pools;
- red interna;
- dependencias.

Por tanto, esta prueba permite describir el comportamiento observado desde el cliente, pero no atribuir una causa raíz al backend.

## 11. Riesgos

### RATE_LIMITING

**Impacto:** HIGH

JSONPlaceholder es un servicio público compartido. Una carga excesiva podría provocar throttling, HTTP 429, bloqueo temporal o aumento de latencia.

**Mitigación:** mantener una carga de baja intensidad y con pacing controlado hasta contar con autorización y límites explícitos del servicio.

### FAKE_PERSISTENCE

**Impacto:** MEDIUM

La operación de creación no representa persistencia real de base de datos para fines de benchmarking.

**Mitigación:** usar este escenario únicamente como validación técnica del flujo y línea base del endpoint.

## 12. Criterios de entrada

Antes de ejecutar:

- plan revisado;
- workload aprobado;
- autorización explícita;
- target confirmado;
- environment confirmado;
- JMX generado y validado;
- ambiente local validado;
- Prometheus y Grafana disponibles si se requiere observabilidad.

## 13. Criterios de salida

La ejecución posterior deberá:

- generar JTL válido;
- generar `jmeter.log`;
- generar `analysis.json`;
- generar `metadata.json`;
- evaluar SLA;
- preservar resultados;
- registrar history cuando corresponda;
- calcular trend cuando existan comparables;
- generar intelligence cuando esté habilitada.

## 14. Preguntas abiertas

1. ¿Cuál es el volumen de carga real esperado si este escenario se adapta a un servicio propietario?
2. ¿Existe un endpoint equivalente con persistencia real para una prueba más representativa?
3. ¿Existe un SLA específico para `POST /posts`?
4. ¿Qué workload debe aprobarse finalmente para la demo?

## 15. Estado de aprobación

- **Test Plan:** `APPROVED`
- **Workload:** `APPROVED`
- **Execution Authorization:** `PENDING`

No generar ni ejecutar carga hasta recibir aprobación explícita.
