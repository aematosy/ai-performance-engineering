---
name: performance-test-designer
description: Diseña y valida pruebas de Performance Engineering desde APIs, cURL y Postman usando únicamente los front doors públicos del proyecto, sin ejecutar carga.
---

# Performance Test Designer

Responde en español.

## Regla principal

Gemini no reconstruye el workflow.

Gemini no ejecuta stages internos directamente.

Gemini usa únicamente el front door público de diseño:

scripts/natural_performance_design_request.sh

## Diseño desde cURL / API

Para una API o cURL, usa el contrato estructurado soportado por:

scripts/natural_performance_design_request.sh

No uses heredoc.

No uses stdin.

No crees archivos intermedios manualmente.

## Diseño desde Postman

Cuando el usuario proporcione una Postman Collection, usa exactamente:

scripts/natural_performance_design_request.sh \
  --scenario "<scenario>" \
  --collection "<collection>" \
  --environment "<environment>" \
  --users <users> \
  --ramp-time-seconds <seconds> \
  --duration-seconds <seconds> \
  --pacing-seconds <seconds>

El environment es opcional si el usuario no proporciona uno.

No leas la colección completa con IA antes de ejecutar el front door.

No ejecutes postman_pipeline.py directamente.

No ejecutes prepare_postman_design.py directamente.

No ejecutes performance_workflow.py directamente.

El front door enruta internamente al workflow determinístico.

## Qué debe descubrir Postman

El pipeline determinístico es responsable de:

- requests y orden del flujo;
- variables;
- environment;
- autenticación;
- dependencias;
- datos;
- correlaciones;
- contratos HTTP;
- cleanup;
- readiness.

Gemini interpreta únicamente los artefactos finales producidos.

## Seguridad

No persistir secretos reales.

No mostrar tokens, passwords, cookies o client secrets.

## Human gate

El diseño debe finalizar en DRAFT / PROPOSED.

No aprobar automáticamente.

No seleccionar JMeter o Locust durante diseño.

No ejecutar carga.

Cuando el diseño termine:

1. presentar resumen funcional;
2. presentar workload;
3. presentar transacciones;
4. presentar correlaciones y datos;
5. presentar SLA;
6. detenerse;
7. esperar aprobación humana.

## Fallos

Si el front door devuelve error:

- mostrar el error;
- detenerse;
- no intentar comandos alternativos;
- no leer documentación para inventar otra ruta;
- no ejecutar stages internos manualmente.
