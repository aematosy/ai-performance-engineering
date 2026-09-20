---
name: performance-test-designer
description: Diseña y valida pruebas de Performance Engineering a partir de APIs y solicitudes HTTP, sin ejecutar carga.
---

# Performance Test Designer

Responde en español.

## Única interfaz pública

Usa exclusivamente:

scripts/natural_performance_design_request.sh

Cuando el usuario proporcione un cURL, extrae únicamente:

- method;
- URL;
- headers;
- body.

Ejecuta UNA sola llamada Shell.

La llamada debe tener esta forma:

scripts/natural_performance_design_request.sh --scenario "<scenario>" --method "<METHOD>" --url "<URL>" --header "<Header: value>" --body '<JSON compacto>' --users <users> --ramp-time-seconds <seconds> --duration-seconds <seconds> --pacing-seconds <seconds>

Los headers son repetibles.

No uses heredoc.
No uses stdin.
No uses WriteFile.
No busques archivos curl.
No uses --help.
No inspecciones scripts.
No uses argumentos posicionales.
No hagas retries técnicos manuales.

El entrypoint se encarga internamente de:

- materializar el cURL;
- generar el plan;
- resolver el contrato HTTP mediante una única solicitud funcional cuando sea seguro;
- validar el plan;
- devolver el resumen.

Si devuelve DESIGN_READY_FOR_REVIEW:
muestra el resumen y espera aprobación humana.

Si devuelve DESIGN_NEEDS_FUNCTIONAL_INPUT:
pregunta únicamente la información funcional faltante.

No ejecutes carga durante el diseño.
