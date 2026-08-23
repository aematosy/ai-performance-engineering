# Prometheus and Grafana Guide

## Objetivo

Este documento define cómo utilizar Prometheus y Grafana dentro de la plataforma AI Performance Engineering.

Su propósito es garantizar que las métricas sean interpretadas correctamente y evitar conclusiones erróneas derivadas de la observabilidad.

---

# Arquitectura

```text
Apache JMeter
      │
      ▼
Prometheus Listener
      │
      ▼
http://localhost:9270/metrics
      │
      ▼
Prometheus
http://localhost:9090
      │
      ▼
Grafana
http://localhost:3000
```

---

# Flujo recomendado

```text
JMeter

↓

Expone métricas

↓

Prometheus realiza Scrape

↓

Grafana consulta Prometheus

↓

Chief analiza resultados
```

---

# Validaciones iniciales

Antes de ejecutar cualquier prueba verificar:

## Docker

```bash
docker compose ps
```

Todos los contenedores deben estar en estado **Up**.

---

## Prometheus

```bash
curl -fsS http://localhost:9090/-/ready
```

Debe responder:

```text
Prometheus Server is Ready.
```

---

## Grafana

```bash
curl -fsS http://localhost:3000/api/health
```

Debe devolver:

```json
{
  "database":"ok"
}
```

---

# Endpoint de métricas

JMeter expone métricas mediante:

```text
http://localhost:9270/metrics
```

Ese endpoint únicamente existe mientras JMeter está ejecutándose.

Por ello:

Durante la ejecución:

```text
UP
```

Después de finalizar:

```text
DOWN
```

Esto es un comportamiento esperado.

No debe reportarse como error.

---

# Prometheus Target

Validar en:

```text
http://localhost:9090/targets
```

Estados posibles:

## UP

Prometheus está leyendo correctamente las métricas.

## DOWN

Puede significar:

- JMeter aún no inició.
- JMeter ya terminó.
- Puerto incorrecto.
- Firewall.
- Listener no configurado.
- Error de red.

No asumir automáticamente que existe un problema.

---

# Datasource

Grafana debe utilizar:

```text
Prometheus
```

UID recomendado:

```text
prometheus
```

El dashboard debe utilizar el mismo UID.

---

# Consultas PromQL

## Total Requests

```promql
sum(jmeter_requests_total)
```

Con fallback:

```promql
sum(jmeter_requests_total) or vector(0)
```

---

## Throughput

```promql
sum(rate(jmeter_requests_total[$__rate_interval]))
```

Con fallback:

```promql
sum(rate(jmeter_requests_total[$__rate_interval])) or vector(0)
```

---

## Throughput por sampler

```promql
sum by(label)(
rate(jmeter_requests_total[$__rate_interval])
)
```

---

## Usuarios activos

```promql
sum(jmeter_threads{state="active"}) or vector(0)
```

---

## Usuarios por estado

```promql
sum by(state)(
jmeter_threads
)
```

---

## p50

```promql
max by(label)(
jmeter_response_time_ms{quantile="0.5"}
)
```

---

## p95

```promql
max by(label)(
jmeter_response_time_ms{quantile="0.95"}
)
```

---

## p99

```promql
max by(label)(
jmeter_response_time_ms{quantile="0.99"}
)
```

---

## Error Rate

```promql
(
sum(rate(jmeter_error_total[$__rate_interval])) or vector(0)
)
/
clamp_min(
sum(rate(jmeter_requests_total[$__rate_interval])) or vector(0),
0.000001
)
```

---

## Target Health

```promql
max(up{job="jmeter"}) or vector(0)
```

Resultado:

```
1 = UP

0 = DOWN
```

---

# No data

"No data" no siempre significa error.

Puede indicar:

- No hubo errores.
- No existen muestras.
- JMeter terminó.
- El rango temporal es incorrecto.
- La consulta no devuelve series.

Siempre validar el contexto antes de concluir.

---

# Dashboard recomendado

El dashboard oficial de este proyecto debe contener:

- Current Throughput
- Current p95
- Error Rate
- Active Virtual Users
- Total Requests
- Target Health
- Throughput Trend
- Response Time Percentiles
- Virtual Users
- Errors by Sampler

---

# Interpretación recomendada

## Throughput alto

No implica automáticamente buen rendimiento.

Debe correlacionarse con:

- Error Rate
- p95
- p99

---

## p95 bajo

Es una buena señal.

Pero no garantiza estabilidad prolongada.

---

## Usuarios activos

Representan únicamente los threads del generador.

No representan usuarios reales del negocio.

---

## Error Rate

Debe permanecer cercano a cero.

Si aumenta:

- revisar códigos HTTP;
- revisar logs;
- revisar infraestructura.

---

# Buenas prácticas

Actualizar el dashboard cada:

```text
5 segundos
```

Utilizar:

```text
Last 15 minutes
```

durante demos cortas.

---

# Limitaciones

Prometheus y Grafana muestran únicamente las métricas publicadas.

No permiten identificar por sí solos:

- CPU del servidor.
- Memoria.
- Base de datos.
- JVM.
- Red.
- GC.

Para eso se requiere instrumentación adicional.

---

# Checklist

Antes de interpretar el dashboard confirmar:

- Prometheus activo.
- Grafana activo.
- Target UP durante la prueba.
- Métricas visibles.
- Rango temporal correcto.
- Dashboard actualizado.

Solo entonces emitir conclusiones.