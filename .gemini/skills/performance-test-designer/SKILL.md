---
name: performance-test-designer
description: Diseña y valida pruebas de Performance Engineering desde APIs, cURL y Postman usando únicamente los front doors públicos del proyecto, sin ejecutar carga.
---

## EXACT POSTMAN PUBLIC CLI CONTRACT

Esta sección es autoritativa y tiene prioridad sobre cualquier ejemplo anterior.

Para diseño Postman desde Gemini, usar únicamente este front door:

    scripts/natural_performance_design_request.sh

Contrato exacto de argumentos:

    --scenario "<scenario>"
    --collection "<collection.json>"
    --environment "<environment.json>"
    --users <integer>
    --ramp-time-seconds <integer>
    --duration-seconds <integer>
    --pacing-seconds <number>

Ejemplo exacto:

    ./scripts/natural_performance_design_request.sh       --scenario "restful-booker-e2e-demo"       --collection "inputs/postman/restful-booker/RestFull Booker_test.postman_collection.json"       --environment "inputs/postman/restful-booker/Production RestFull.postman_environment.json"       --users 10       --ramp-time-seconds 100       --duration-seconds 180       --pacing-seconds 2

Nombres inválidos que Gemini NO debe usar:

    --duration
    --ramp-up
    --ramp-up-seconds
    --ramp-time
    --pacing
    --input-type postman

Reglas:

- No traducir nombres naturales del workload a opciones inventadas.
- "duración" SIEMPRE se materializa como `--duration-seconds`.
- "ramp-up" SIEMPRE se materializa como `--ramp-time-seconds`.
- "pacing" SIEMPRE se materializa como `--pacing-seconds`.
- Para Postman NO pasar `--input-type`; el wrapper público resuelve el routing.
- Si el front door devuelve código distinto de 0, detenerse inmediatamente.
- No reintentar con opciones alternativas.
- No llamar directamente `natural_performance_design.sh`.

## AUTHORITATIVE DESIGN FRONT DOOR

Esta sección tiene prioridad sobre cualquier instrucción anterior.

Para solicitudes estructuradas provenientes de Gemini, incluyendo:

- Postman Collection + Environment;
- cURL;
- endpoint HTTP;
- método + URL + headers + body;
- scenario + workload;

Gemini DEBE usar exclusivamente:

    scripts/natural_performance_design_request.sh

Gemini NO debe invocar directamente:

    scripts/natural_performance_design.sh

cuando la información ya está estructurada en el prompt del usuario.

`natural_performance_design.sh` es una implementación interna del flujo natural.
`natural_performance_design_request.sh` es el front door público estructurado para agentes.

Para Postman, pasar al wrapper público:

- collection;
- environment;
- scenario;
- users;
- ramp-up;
- duration;
- pacing.

Reglas fail-closed:

- si `natural_performance_design_request.sh` termina con código distinto de 0, detenerse;
- mostrar el error exacto;
- no reintentar;
- no invocar `natural_performance_design.sh` como fallback;
- no probar scripts internos;
- no inspeccionar `src/` ni `scripts/` buscando alternativas;
- no continuar aunque existan artefactos parciales.

Un fallo del front door público termina el diseño.

# Performance Test Designer

Responde en español.

## Regla principal

Gemini no reconstruye el workflow.

Gemini no ejecuta stages internos directamente.

Gemini usa únicamente el front door público de diseño:

scripts/natural_performance_design_request.sh

## Diseño desde cURL / API

Para una API o cURL usa exclusivamente el front door público:

scripts/natural_performance_design_request.sh

El contrato público para cURL/API es estructurado.

Usa exactamente esta forma:

scripts/natural_performance_design_request.sh \
  --scenario "<scenario>" \
  --method "<METHOD>" \
  --url "<URL>" \
  --header "<Header-Name: value>" \
  --body '<body>' \
  --users <users> \
  --ramp-time-seconds <seconds> \
  --duration-seconds <seconds> \
  --pacing-seconds <seconds>

`--header` puede repetirse.

`--body` es opcional cuando el request no tiene body.

IMPORTANTE:

- NO pases `--input-type` al front door público.
- NO pases `--curl` al front door público.
- NO pases el comando cURL completo como un único argumento.
- NO invoques `natural_performance_design.sh` directamente.
- NO invoques `natural_performance_design_http.sh` directamente.
- NO invoques `performance_workflow.py` directamente.

El front door público es responsable de:

1. materializar el cURL canónico;
2. enrutarlo internamente como input CLI;
3. ejecutar intake;
4. generar el plan;
5. resolver el contrato HTTP cuando sea necesario;
6. ejecutar review y validation;
7. detenerse antes de aprobación y carga.

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


## Validación funcional de contratos Postman

El front door puede ejecutar internamente una única traversía funcional E2E,
engine-neutral, cuando la colección no declara todos los HTTP status esperados.

Esa traversía:

- NO es carga de performance;
- usa una sola ejecución funcional secuencial del journey;
- preserva assertions HTTP explícitas de Postman;
- descubre únicamente contratos faltantes a partir de respuestas reales;
- valida que un contrato explícito coincida con la respuesta observada;
- ejecuta cleanup DELETE de forma best-effort si el journey falla después de crear datos;
- debe terminar con todos los contratos HTTP resueltos antes de mostrar el diseño como listo para aprobación.

Si la traversía funcional falla o un contrato permanece sin resolver, el front door falla cerrado.
Gemini muestra el error y se detiene.

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

## Non-interactive runtime secrets

Never ask the user to type passwords, tokens, API keys, client secrets, or
other runtime secrets into Gemini or into an interactive Shell prompt.

For Postman input, runtime secrets that are already declared in the source
collection, collection variables, or environment are materialized
deterministically by the public design front door.

Do not call materialize_runtime_properties.py interactively.

Do not use getpass.

Do not request secret values through chat.

If a required secret cannot be resolved from the declared input sources,
stop the design with a deterministic missing-secret error. Do not continue
toward execution.


## Dual scenario identity - authoritative handoff

Esta regla tiene prioridad sobre cualquier instrucción anterior que pueda
confundir el scenario solicitado por el usuario con el scenario canónico
descubierto por Postman.

Para diseños Postman pueden coexistir dos identidades válidas:

- REQUESTED SCENARIO: identidad pública solicitada por el usuario y usada
  para `workspaces/<requested-scenario>/`.
- CANONICAL SCENARIO: identidad técnica descubierta por el análisis Postman
  y usada para `tests/plans/<canonical-scenario>/`, `work/postman/...`,
  `data/...`, artefactos de motor, resultados y reportes.

Ejemplo válido:

```text
requested: restful-booker-e2e-demo
canonical: booking-e2e
```

El front door público de ejecución SIEMPRE debe invocarse con el REQUESTED
SCENARIO original:

```bash
scripts/natural_performance_execute.sh   --scenario "restful-booker-e2e-demo"
```

NUNCA sustituir manualmente ese argumento por el scenario canónico:

```text
booking-e2e
```

El front door ya es responsable de resolver internamente:

```text
requested scenario
    -> workspace/execution-profile.yaml
    -> resolve_execution_scenario.py
    -> canonical scenario
    -> plan / model / artifact / execution
```

Por lo tanto:

- no construir `workspaces/<canonical-scenario>/execution-profile.yaml`
  cuando el diseño Postman usa dual identity;
- no copiar ni renombrar el workspace para igualarlo al scenario canónico;
- no invocar `natural_performance_execute.sh` con el canonical scenario
  después de una aprobación del diseño solicitado bajo otro nombre;
- conservar el REQUESTED SCENARIO durante approval -> preparation handoff;
- permitir que `natural_performance_execute.sh` resuelva el CANONICAL SCENARIO;
- si el front door falla, detenerse y mostrar el error exacto, sin intentar
  rutas alternativas.

Antes de preparar ejecución, si existe:

```text
workspaces/<requested-scenario>/execution-profile.yaml
```

y el plan está bajo otra identidad canónica, esto NO es un error: es el
contrato esperado de dual scenario identity.
