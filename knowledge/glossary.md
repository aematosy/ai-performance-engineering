# Performance Engineering Glossary

## SLA (Service Level Agreement)

Conjunto de objetivos de rendimiento que una aplicación debe cumplir, como tiempo de respuesta, disponibilidad o tasa máxima de errores.

---

## Performance Test

Prueba diseñada para evaluar el comportamiento de un sistema bajo diferentes niveles de carga.

---

## Baseline Test

Prueba inicial utilizada para obtener una referencia del rendimiento antes de realizar optimizaciones o incrementar la carga.

---

## Load Test

Prueba que valida el comportamiento del sistema bajo la carga esperada de usuarios o transacciones.

---

## Stress Test

Prueba que incrementa progresivamente la carga hasta encontrar el límite operativo del sistema.

---

## Spike Test

Prueba que evalúa la capacidad del sistema para responder a incrementos repentinos de tráfico.

---

## Endurance Test

Prueba de larga duración utilizada para detectar degradación, fugas de memoria o problemas de estabilidad.

---

## Throughput

Cantidad de solicitudes o transacciones procesadas por unidad de tiempo, normalmente expresada en solicitudes por segundo (Requests/sec).

---

## Latency

Tiempo que transcurre entre el envío de una solicitud y la recepción de la respuesta.

---

## Response Time

Tiempo total que tarda una operación en completarse desde la perspectiva del cliente.

---

## Average Response Time

Promedio de todos los tiempos de respuesta registrados durante una prueba.

---

## Percentile

Medida estadística que indica el tiempo de respuesta por debajo del cual se encuentra un porcentaje determinado de las solicitudes.

---

## p50

Percentil que representa el comportamiento típico o mediano del sistema.

---

## p90

Tiempo de respuesta que no supera el 90% de las solicitudes.

---

## p95

Métrica utilizada habitualmente para evaluar el cumplimiento de los SLA de rendimiento.

---

## p99

Tiempo de respuesta de los casos más lentos. Es útil para detectar valores atípicos y degradaciones.

---

## Maximum Response Time

Mayor tiempo de respuesta registrado durante una ejecución.

---

## Error Rate

Porcentaje de solicitudes que finalizaron con error respecto al total de solicitudes ejecutadas.

---

## Success Rate

Porcentaje de solicitudes ejecutadas correctamente durante una prueba.

---

## Virtual User (VU)

Usuario simulado por la herramienta de pruebas de rendimiento.

---

## Thread

Unidad de ejecución utilizada por JMeter para representar un usuario virtual.

---

## Thread Group

Componente principal de JMeter que define el número de usuarios, el ramp-up y la duración de una prueba.

---

## Ramp-up

Tiempo que tarda JMeter en iniciar todos los usuarios virtuales configurados.

---

## Think Time

Tiempo de espera entre operaciones para simular el comportamiento de un usuario real.

---

## Sampler

Elemento de JMeter que ejecuta una solicitud hacia el sistema bajo prueba.

---

## HTTP Request

Sampler utilizado para enviar solicitudes HTTP o HTTPS.

---

## Assertion

Validación que verifica que la respuesta cumple las condiciones esperadas.

---

## Listener

Componente encargado de recopilar, visualizar o exportar los resultados de una prueba.

---

## JMX

Archivo XML que contiene el plan de pruebas de Apache JMeter.

---

## JTL

Archivo de resultados generado por JMeter con el detalle de todas las solicitudes ejecutadas.

---

## Prometheus

Sistema de monitoreo que recopila métricas expuestas por aplicaciones y herramientas.

---

## Scrape

Proceso mediante el cual Prometheus consulta periódicamente un endpoint de métricas.

---

## Metrics Endpoint

URL que expone las métricas de una aplicación, normalmente en formato Prometheus.

---

## Grafana

Herramienta utilizada para visualizar métricas mediante dashboards interactivos.

---

## Dashboard

Conjunto de paneles que muestran indicadores de rendimiento y observabilidad.

---

## PromQL

Lenguaje de consultas utilizado por Prometheus para recuperar y procesar métricas.

---

## Observability

Capacidad de comprender el comportamiento de un sistema mediante métricas, logs y trazas.

---

## Bottleneck

Componente o recurso que limita el rendimiento general del sistema.

---

## Root Cause

Causa principal que origina un problema de rendimiento. Debe confirmarse mediante evidencia y correlación de métricas.

---

## Evidence

Conjunto de archivos y métricas generados durante una ejecución, como JTL, logs, reportes y dashboards.

---

## PASS

Resultado que indica que la ejecución se completó correctamente y que los SLA configurados fueron cumplidos.

---

## FAIL

Resultado que indica un incumplimiento de SLA o un error técnico que requiere análisis.

---

## Executive Report

Reporte que resume los resultados, métricas, conclusiones y recomendaciones de una ejecución de rendimiento.

---

## Performance Engineering

Disciplina que combina pruebas, monitoreo, análisis y optimización para garantizar el rendimiento, estabilidad y escalabilidad de un sistema.