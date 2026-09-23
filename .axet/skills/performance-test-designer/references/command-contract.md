## EXACT POSTMAN PUBLIC CLI CONTRACT

Esta sección es autoritativa y tiene prioridad sobre cualquier ejemplo anterior.

Para diseño Postman desde aXet Code, usar únicamente este front door:

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

Nombres inválidos que aXet Code NO debe usar:

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

Para solicitudes estructuradas provenientes de aXet Code, incluyendo:

- Postman Collection + Environment;
- cURL;
- endpoint HTTP;
- método + URL + headers + body;
- scenario + workload;

aXet Code DEBE usar exclusivamente:

    scripts/natural_performance_design_request.sh

aXet Code NO debe invocar directamente:

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

# Natural Design Command Contract

## Single public front door

aXet Code usa solamente:

scripts/natural_performance_design_request.sh

No debe reconstruir el workflow ni ejecutar stages internos.


## cURL / API

El contrato público para cURL/API es:

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

Reglas:

- `--header` puede repetirse.
- `--body` es opcional.
- `--input-type` NO pertenece al contrato público.
- `--curl` NO pertenece al contrato público.
- aXet Code NO materializa manualmente archivos `.curl`.
- aXet Code NO llama `natural_performance_design_http.sh`.
- aXet Code NO llama `natural_performance_design.sh`.
- aXet Code NO llama `performance_workflow.py`.

El front door materializa internamente el input cURL y lo enruta al
intake CLI determinístico.


## Postman

El contrato público para Postman es:

scripts/natural_performance_design_request.sh \
  --scenario "<scenario>" \
  --collection "<collection>" \
  --environment "<environment>" \
  --users <users> \
  --ramp-time-seconds <seconds> \
  --duration-seconds <seconds> \
  --pacing-seconds <seconds>

`--environment` es opcional cuando el usuario no proporciona uno.

El front door posee el routing hacia el workflow Postman determinístico.


## Forbidden direct commands

aXet Code no debe llamar directamente:

- performance_workflow.py;
- natural_performance_design.sh;
- natural_performance_design_http.sh;
- prepare_postman_design.py;
- postman_pipeline.py;
- generate_postman_jmx.py;
- review_test_plan.py;
- validate_test_plan.py.


## Fail closed

Si:

scripts/natural_performance_design_request.sh

termina con código distinto de cero:

1. mostrar el error real;
2. detenerse inmediatamente;
3. NO probar otro script;
4. NO quitar flags y reintentar;
5. NO buscar otra implementación;
6. NO ejecutar stages internos;
7. NO considerar el diseño completado porque existan archivos parciales.


## Design boundaries

Durante diseño:

- no seleccionar JMeter;
- no seleccionar Locust;
- no autorizar ejecución;
- no ejecutar performance load;
- no alterar el workload solicitado.

El resultado exitoso debe terminar en revisión/aprobación humana.


## Postman response-contract readiness

Antes de declarar un diseño Postman listo para revisión humana, cada
transacción seleccionada debe tener contrato HTTP explícito.

El front door puede ejecutar una única traversía funcional engine-neutral
para resolver contratos faltantes.

Esta traversía:

- no es performance load;
- conserva assertions explícitas de Postman;
- falla cerrado ante mismatch;
- ejecuta cleanup best-effort cuando corresponda.
