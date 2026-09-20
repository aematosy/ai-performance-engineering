---
name: performance-test-designer
description: Diseña y valida pruebas de Performance Engineering a partir de APIs, cURL, OpenAPI, Postman, HAR, documentación o JMX, sin ejecutar carga.
---

# Performance Test Designer

Responde en español.

## Única operación pública

Usa exclusivamente:

scripts/natural_performance_design.sh

No inspecciones el script.
No uses --help.
No uses heredoc.
No uses stdin.
No uses WriteFile.
No busques archivos curl alternativos.
No uses formas posicionales.
No inventes parámetros.

## Si el usuario proporciona un cURL

Extrae exclusivamente:

- método HTTP;
- URL;
- headers;
- body.

Ejecuta UNA sola llamada Shell con esta forma exacta, en una sola línea:

scripts/natural_performance_design.sh --scenario "<scenario>" --method "<METHOD>" --url "<URL>" --header "<Header-1: value>" --header "<Header-2: value>" --body '<JSON_BODY_COMPACTO>' --users <users> --ramp-time-seconds <seconds> --duration-seconds <seconds> --pacing-seconds <seconds>

El JSON de --body debe ir compacto en una sola línea.

Ejemplo conceptual de body:

{"title":"Performance Test Product"}

No incluyas delimitadores Markdown como parte del comando.
No incluyas triple backticks.
No incluyas etiquetas como text, bash o shell.
No abras una sesión interactiva.
No envíes contenido en varias entradas.

## Si el usuario proporciona explícitamente un archivo existente

Usa una única llamada:

scripts/natural_performance_design.sh --scenario "<scenario>" --input "<path>" --users <users> --ramp-time-seconds <seconds> --duration-seconds <seconds> --pacing-seconds <seconds>

Nunca descubras tú otro archivo.

## Responsabilidades internas del entrypoint

El entrypoint realiza internamente:

- materialización del cURL;
- normalización;
- creación del plan;
- functional probe cuando el HTTP esperado no está resuelto;
- sincronización del contrato;
- validación final;
- generación del resumen.

Gemini no debe reconstruir ninguno de esos pasos.

## Resultado

Si devuelve DESIGN_READY_FOR_REVIEW:
muestra el resumen y espera aprobación humana.

Si devuelve DESIGN_NEEDS_FUNCTIONAL_INPUT:
pregunta únicamente la información funcional pendiente.

Si devuelve error técnico:
repórtalo y detente.

## Prohibido

No invoques directamente approve, authorize, prepare, preflight o execute.
No invoques performance_workflow.py.
No invoques JMeter.
No invoques Locust.
No hagas retries técnicos manuales.
No ejecutes carga durante diseño.
