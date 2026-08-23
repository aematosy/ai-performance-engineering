# Performance Engineering Knowledge Base

Esta carpeta contiene las reglas técnicas y criterios de análisis utilizados por
los agentes del proyecto.

## Objetivo

Ayudar a los agentes a:

- diseñar pruebas de rendimiento seguras;
- seleccionar un tipo de prueba adecuado;
- interpretar métricas de JMeter;
- evaluar SLA;
- analizar riesgos sin inventar causas raíz;
- utilizar Prometheus y Grafana correctamente;
- entregar recomendaciones basadas en evidencia.

## Documentos

### `performance-testing-strategy.md`

Define:

- tipos de prueba;
- criterios de selección;
- perfiles de carga;
- requisitos mínimos antes de ejecutar;
- estrategia de crecimiento de carga.

### `jmeter-best-practices.md`

Define:

- ejecución no-GUI;
- uso de threads, ramp-up y duration;
- manejo de datos;
- assertions;
- logs;
- resultados JTL;
- prácticas para evitar errores del generador de carga.

### `sla-and-analysis-guidelines.md`

Define:

- métricas obligatorias;
- interpretación de percentiles;
- evaluación de SLA;
- diferencia entre fallo técnico y fallo de rendimiento;
- criterios para recomendaciones.

### `prometheus-grafana-guide.md`

Define:

- métricas expuestas por JMeter;
- consultas PromQL;
- interpretación del dashboard;
- comportamiento esperado de targets;
- limitaciones de observabilidad.

### `troubleshooting-guide.md`

Contiene diagnóstico para:

- JMeter;
- Prometheus;
- Grafana;
- Docker;
- JTL;
- reportes;
- puertos;
- errores de provisioning.

### `glossary.md`

Explica los términos principales de Performance Engineering.

## Reglas generales para los agentes

1. No inventar causas raíz.
2. No ejecutar pruebas sin autorización.
3. No afirmar escalabilidad de producción con una prueba corta.
4. Diferenciar:
   - error técnico;
   - error funcional;
   - incumplimiento de SLA;
   - limitación de observabilidad.
5. Usar scripts determinísticos para métricas y verdictos.
6. Mantener las respuestas al usuario en español.
7. Mantener en inglés únicamente nombres técnicos, comandos y rutas.
8. Conservar todas las evidencias generadas.
