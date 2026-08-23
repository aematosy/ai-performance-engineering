# SLA and Analysis Guidelines

## Objetivo

Este documento define cómo deben interpretarse los resultados obtenidos durante una prueba de rendimiento.

El objetivo es garantizar que todas las conclusiones estén basadas en evidencia objetiva y no en suposiciones.

El veredicto técnico debe provenir siempre del análisis automático realizado por los scripts del proyecto.

---

# Principios

Toda conclusión debe cumplir las siguientes reglas:

- Basarse en métricas reales.
- Ser reproducible.
- Diferenciar un fallo técnico de un incumplimiento de SLA.
- No inventar causas raíz.
- Explicar las limitaciones de la evidencia disponible.

---

# Flujo de análisis

```text
JTL
 │
 ▼
analyze_results.py
 │
 ▼
analysis.json
 │
 ▼
generate_report.py
 │
 ▼
Executive Report
 │
 ▼
Chief Performance Engineer
```

---

# Orden recomendado de análisis

Siempre analizar en este orden:

1. Validar que la ejecución terminó correctamente.
2. Revisar errores técnicos.
3. Revisar tasa de error.
4. Revisar throughput.
5. Revisar percentiles.
6. Revisar SLA.
7. Emitir recomendaciones.

No invertir este orden.

---

# Métricas obligatorias

Toda ejecución debe reportar:

- Requests totales.
- Requests exitosos.
- Requests fallidos.
- Success Rate.
- Error Rate.
- Throughput.
- Tiempo mínimo.
- Tiempo promedio.
- p50.
- p90.
- p95.
- p99.
- Tiempo máximo.
- Duración.
- Errores por código HTTP.
- Errores por sampler.

---

# Success Rate

Representa el porcentaje de solicitudes exitosas.

No implica que el sistema sea escalable.

Un Success Rate de 100% con únicamente cinco usuarios no demuestra capacidad productiva.

---

# Error Rate

Debe calcularse como:

```text
Errores / Total de Requests
```

Interpretación sugerida:

| Error Rate | Riesgo |
|------------|---------|
| 0% | Excelente |
| 0 - 1% | Aceptable |
| 1 - 3% | Revisar |
| >3% | Riesgo Alto |

Los umbrales reales deben provenir de:

```text
config/sla.json
```

---

# Throughput

Representa la cantidad de solicitudes procesadas por segundo.

Debe analizarse junto con:

- usuarios;
- duración;
- ramp-up;
- errores;
- latencia.

Nunca analizar throughput de forma aislada.

---

# Latencia

La latencia representa el tiempo observado desde el punto de vista del cliente.

No permite determinar por sí sola la causa raíz.

---

# Promedio

El promedio puede ocultar degradaciones.

Ejemplo:

```text
100 respuestas

99 = 100 ms

1 = 8 segundos
```

El promedio podría seguir siendo aceptable.

Por ello deben utilizarse percentiles.

---

# Percentiles

## p50

Representa el comportamiento típico.

---

## p90

Permite observar el comportamiento de la mayoría de usuarios.

---

## p95

Debe considerarse la métrica principal para SLA de experiencia.

En la mayoría de organizaciones esta es la referencia principal.

---

## p99

Representa los casos extremos.

Es útil para detectar:

- bloqueos;
- colas;
- GC;
- dependencias lentas;
- operaciones poco frecuentes.

No debe utilizarse como única métrica.

---

# Tiempo máximo

El tiempo máximo debe revisarse únicamente como referencia.

No aprobar ni rechazar una prueba usando solamente el máximo.

---

# SLA PASS

Un PASS significa únicamente:

- la ejecución terminó correctamente;
- los umbrales configurados fueron cumplidos.

No significa:

- ausencia de riesgos;
- ausencia de cuellos de botella;
- capacidad ilimitada;
- estabilidad en producción.

---

# SLA FAIL

Cuando un SLA falla debe indicarse:

- métrica;
- umbral;
- valor observado;
- diferencia;
- posible impacto.

Ejemplo:

```text
p95

Observado:

1 250 ms

SLA:

<= 1 000 ms

Resultado:

FAIL
```

---

# Error técnico

Un error técnico invalida la ejecución.

Ejemplos:

- JTL vacío.
- Docker detenido.
- Plugin ausente.
- Grafana inaccesible.
- Prometheus inaccesible.
- JMX inválido.
- Error de escritura.
- Pipeline incompleto.

No debe generarse un PASS si existe un error técnico crítico.

---

# Riesgo

El Chief debe clasificar el riesgo.

## Bajo

- SLA aprobado.
- Sin errores.
- Evidencias completas.

---

## Medio

- SLA aprobado con poco margen.
- Duración corta.
- Observabilidad parcial.

---

## Alto

- SLA fallido.
- Error Rate elevado.
- Evidencias incompletas.
- Errores técnicos.

---

# Causa raíz

Nunca afirmar una causa raíz utilizando únicamente:

- JTL;
- Prometheus;
- Grafana.

Debe utilizarse lenguaje como:

- posible causa;
- requiere correlación;
- evidencia insuficiente;
- revisar métricas de infraestructura.

---

# Correlación recomendada

Cuando exista degradación revisar además:

- CPU.
- Memoria.
- JVM.
- Garbage Collection.
- Base de datos.
- Red.
- Dependencias externas.
- Logs de aplicación.

---

# Recomendaciones

Priorizar siempre:

1. Corregir errores técnicos.
2. Corregir SLA incumplidos.
3. Repetir la prueba.
4. Incrementar carga gradualmente.
5. Ampliar observabilidad.

No recomendar inmediatamente aumentar usuarios si la ejecución presenta problemas.

---

# Checklist del analista

Antes de emitir un resultado confirmar:

- JTL válido.
- analysis.json generado.
- Reporte generado.
- Log revisado.
- SLA evaluado.
- Errores técnicos revisados.
- Evidencias completas.

Solo entonces emitir el veredicto final.