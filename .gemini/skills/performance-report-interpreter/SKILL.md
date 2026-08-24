---
name: performance-report-interpreter
description: Interpreta resultados determinísticos de pruebas de performance y genera explicación ejecutiva en español claro, PDF profesional visual, métricas por transacción y mejoras no destructivas del reporte HTML con exportación PDF y accesos a Grafana/Prometheus. Usar para explicar p95, p99, throughput, éxito/error o SLA a personas técnicas y no técnicas y producir reportes para cualquier aplicación web o API HTTP medida con JMeter/JTL/JMX.
---

# Performance Report Interpreter

Usar los artefactos determinísticos como fuente de verdad. No reemplazar ni reinterpretar el PASS/FAIL oficial del motor de SLA.

## Flujo

1. Leer `analysis.json`, `intelligence.json` opcional, execution profile aprobado, JTL/JMX y evidencia disponible.
2. Calcular métricas faltantes directamente desde JTL con `JtlMetricsAnalyzer`; no mostrar `N/A` cuando el dato pueda derivarse de runtime.
3. Derivar el objetivo general desde los orígenes HTTP del JTL cuando no se proporcione uno explícito. Nunca usar automáticamente el primer endpoint como objetivo del proyecto.
4. Construir evidencia representativa con `evidence_collector.py`.
5. Interpretar métricas en español natural con `PerformanceResultInterpreter`.
6. Generar PDF profesional con `ProfessionalPdfReportGenerator`; conservar la evidencia detallada fuera del PDF ejecutivo.
7. Mejorar `executive-report.html` con `HtmlReportEnhancer`: españolizar etiquetas, corregir el objetivo general, agregar un único `Exportar PDF` sin solapar controles existentes y mostrar accesos de observabilidad.
8. Preferir `PerformanceReportBundleBuilder` para generar todo en una sola operación.

## Lenguaje para personas no expertas

Evitar frases mecánicas como `la decisión informada es ACCEPT` o `el veredicto determinístico es PASS` como explicación principal.

Traducir el resultado a lenguaje natural:

- `PASS`: `La prueba cumplió con los criterios de rendimiento definidos para la carga ejecutada.`
- `FAIL`: `La prueba no cumplió uno o más criterios de rendimiento definidos para la carga ejecutada.`
- `LOW`: `Riesgo bajo`.
- `ACCEPT`: `Apto para conservar como evidencia de esta ejecución`.

Explicar siempre:

- p95 como `95 de cada 100 solicitudes respondieron en X ms o menos`;
- p99 como `99 de cada 100 solicitudes respondieron en X ms o menos`;
- throughput como el ritmo observado con esa carga, no como capacidad máxima;
- 100% success como cumplimiento de las validaciones configuradas, no como prueba absoluta de ausencia de defectos funcionales.

## Compatibilidad

No hardcodear nombres como Booking, Auth, Claims ni endpoints concretos.

Soportar:

- APIs REST/HTTP;
- backends y aplicaciones web medidas a nivel HTTP;
- escenarios single-request o multi-request;
- uno o varios hosts/orígenes;
- labels/transacciones arbitrarios presentes en JTL;
- JTL CSV o XML.

## Objetivo general

Si `--target` no se pasa, derivarlo del JTL:

- un único origen: mostrar `scheme://host[:port]`;
- múltiples orígenes: mostrar que es un flujo multi-servicio y resumir los destinos;
- nunca presentar `/auth`, `/login` u otro primer endpoint como si fuera el objetivo completo del proyecto.

## Evidencia y falsos positivos

Mantener `evidence.json` como artefacto técnico de trazabilidad. No incluir request/response representativos ni la sección de evidencia detallada en el PDF ejecutivo.

No incluir todas las muestras del load test en el reporte ejecutivo.

Por transacción/servicio seleccionar como máximo:

- un éxito representativo;
- un fallo representativo si existe;
- un outlier lento cuando aporte valor.

Redactar Authorization, Cookie, passwords, tokens, API keys, sesiones y secretos comunes.

Usar exactamente uno de estos niveles:

- `RUNTIME_REQUEST_RESPONSE_VERIFIED`
- `REQUEST_TEMPLATE_PLUS_RUNTIME_STATUS`
- `STATUS_ONLY`
- `NOT_AVAILABLE`

No afirmar que el response de runtime fue verificado si el JTL no lo contiene. Explicar la ausencia en español, no usar `N/A` como única explicación.

## PDF

El PDF debe ser visualmente profesional, no una exportación monocromática:

- paleta azul/índigo con verde para PASS y rojo para FAIL;
- jerarquía tipográfica clara;
- tarjetas de resultado, riesgo, conclusión y KPIs;
- callout `¿Qué significa este resultado?`;
- tablas con wrapping, padding y filas alternadas;
- no incluir request/response representativos ni dumps técnicos de evidencia;
- footer con paginación;
- sin texto superpuesto, cortado o pegado a bordes.

## HTML

Conservar selectores, gráficos, tema dark/light y cualquier funcionalidad existente.

El botón `Exportar PDF` debe:

- existir una sola vez aunque el enhancer se ejecute repetidamente;
- eliminar inyecciones antiguas v2/v3 antes de instalar la actual;
- estar fijo abajo a la derecha para no solapar controles de tema ubicados arriba;
- ocultarse al imprimir;
- ser usable en pantallas pequeñas;
- apuntar al `executive-report.pdf` generado.

Agregar una sección `Observabilidad en tiempo real` antes del resumen de tiempos con accesos configurables a Grafana, Prometheus y al endpoint de métricas. Indicar que funcionan cuando la stack local está activa.

Españolizar etiquetas visibles comunes del reporte y actualizar la tarjeta `Target/Objetivo` al objetivo general resuelto.

## Orden del PDF

1. Resultado, riesgo y conclusión en tarjetas uniformes
2. Explicación simple del resultado
3. Workload aprobado
4. Métricas clave en tarjetas uniformes
5. Cómo leer los resultados
6. Desglose por transacción/servicio
7. Cierre ejecutivo con limitaciones y recomendaciones

Mantener la evidencia detallada en `evidence.json`, no dentro del PDF.

## Clases incluidas

- `report_models.py`: modelos del reporte
- `jtl_metrics.py`: `JtlMetricsAnalyzer`
- `evidence_collector.py`: recolección/redacción de evidencia
- `interpret_results.py`: `PerformanceResultInterpreter`
- `generate_professional_pdf.py`: `ProfessionalPdfReportGenerator`
- `enhance_html_report.py`: `HtmlReportEnhancer`
- `build_report_bundle.py`: `PerformanceReportBundleBuilder`

Leer `references/report-contract.md` para semántica y `references/integration.md` para instalación/integración.
