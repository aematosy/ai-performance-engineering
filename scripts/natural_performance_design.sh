#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

INPUT=""
SCENARIO=""
USERS=""
RAMP_UP=""
DURATION=""
PACING=""
EXPECTED_STATUS=""

if [ "$#" -ge 1 ] && [[ "$1" == --* ]]; then
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --input)
        INPUT="$2"
        shift 2
        ;;
      --scenario)
        SCENARIO="$2"
        shift 2
        ;;
      --users)
        USERS="$2"
        shift 2
        ;;
      --ramp-time|--ramp-time-seconds)
        RAMP_UP="$2"
        shift 2
        ;;
      --duration|--duration-seconds)
        DURATION="$2"
        shift 2
        ;;
      --pacing|--pacing-seconds)
        PACING="$2"
        shift 2
        ;;
      --expected-status)
        EXPECTED_STATUS="$2"
        shift 2
        ;;
      *)
        echo
        echo "No se pudo interpretar la solicitud de diseño."
        echo "No se ejecutó carga."
        exit 2
        ;;
    esac
  done
else
  if [ "$#" -lt 6 ]; then
    echo
    echo "Faltan datos para diseñar la prueba."
    echo "No se ejecutó carga."
    exit 2
  fi

  INPUT="$1"
  SCENARIO="$2"
  USERS="$3"
  RAMP_UP="$4"
  DURATION="$5"
  PACING="$6"

  if [ "$#" -ge 7 ]; then
    EXPECTED_STATUS="$7"
  fi
fi

for VALUE in \
  "${INPUT}" \
  "${SCENARIO}" \
  "${USERS}" \
  "${RAMP_UP}" \
  "${DURATION}" \
  "${PACING}"
do
  if [ -z "${VALUE}" ]; then
    echo
    echo "Faltan datos necesarios para diseñar la prueba."
    echo "No se ejecutó carga."
    exit 2
  fi
done

WORKSPACE="workspaces/${SCENARIO}"
PLAN="tests/plans/${SCENARIO}/test-plan.yaml"

echo
echo "======================================================================"
echo "PREPARANDO EL DISEÑO DE LA PRUEBA"
echo "======================================================================"
echo
echo "Voy a:"
echo "- interpretar la API y el workload solicitado;"
echo "- generar el plan de prueba;"
echo "- validar que el diseño sea consistente;"
echo "- mantener el diseño neutral a JMeter y Locust."
echo
echo "No voy a:"
echo "- ejecutar carga;"
echo "- autorizar una ejecución;"
echo "- seleccionar JMeter o Locust;"
echo "- modificar el workload solicitado."
echo
echo "Scenario : ${SCENARIO}"
echo "Usuarios : ${USERS}"
echo "Ramp-up  : ${RAMP_UP} s"
echo "Duración : ${DURATION} s"
echo "Pacing   : ${PACING} s"
echo "======================================================================"
echo

poetry run python \
  scripts/performance_workflow.py \
  intake \
  --input "${INPUT}" \
  --input-type cli \
  --workspace "${WORKSPACE}" \
  --users "${USERS}" \
  --duration-seconds "${DURATION}" \
  --ramp-time-seconds "${RAMP_UP}" \
  --pacing-seconds "${PACING}"

if [ ! -f "${PLAN}" ]; then
  echo
  echo "No se pudo generar el plan de prueba."
  echo "No se ejecutó carga."
  exit 2
fi

if [ -n "${EXPECTED_STATUS}" ]; then
  poetry run python \
    scripts/normalize_design_contract.py \
    --plan "${PLAN}" \
    --expected-status "${EXPECTED_STATUS}"
else
  poetry run python \
    scripts/normalize_design_contract.py \
    --plan "${PLAN}" \
    --unresolved
fi

# Design must not retain an active engine-specific executable.
HISTORY="${WORKSPACE}/design-history/${STAMP:-$(date +%Y%m%d_%H%M%S)}"

JMETER_ARTIFACT="tests/generated/${SCENARIO}.jmx"
JMETER_METADATA="${JMETER_ARTIFACT}.meta.json"
LOCUST_DIR="tests/generated/locust/${SCENARIO}"

if \
  [ -f "${JMETER_ARTIFACT}" ] \
  || [ -f "${JMETER_METADATA}" ] \
  || [ -d "${LOCUST_DIR}" ]
then
  mkdir -p "${HISTORY}"

  if [ -f "${JMETER_ARTIFACT}" ]; then
    mv \
      "${JMETER_ARTIFACT}" \
      "${HISTORY}/"
  fi

  if [ -f "${JMETER_METADATA}" ]; then
    mv \
      "${JMETER_METADATA}" \
      "${HISTORY}/"
  fi

  if [ -d "${LOCUST_DIR}" ]; then
    mv \
      "${LOCUST_DIR}" \
      "${HISTORY}/locust"
  fi
fi

poetry run python \
  scripts/performance_workflow.py \
  review \
  --plan "${PLAN}"

# Re-apply canonical design semantics after review so a legacy
# generator/reviewer cannot reintroduce engine-specific defaults.
if [ -n "${EXPECTED_STATUS}" ]; then
  poetry run python \
    scripts/normalize_design_contract.py \
    --plan "${PLAN}" \
    --expected-status "${EXPECTED_STATUS}"
else
  poetry run python \
    scripts/normalize_design_contract.py \
    --plan "${PLAN}" \
    --unresolved
fi

poetry run python \
  scripts/validate_test_plan.py \
  --plan "${PLAN}"

echo
echo "======================================================================"
echo "PLAN LISTO PARA TU REVISIÓN"
echo "======================================================================"

poetry run python - "${PLAN}" <<'PY'
from pathlib import Path
import sys
import yaml

path = Path(
    sys.argv[1]
)

plan = yaml.safe_load(
    path.read_text(
        encoding="utf-8"
    )
)

metadata = plan.get(
    "metadata",
    {},
)

workload = plan.get(
    "workload",
    {},
)

params = workload.get(
    "parameters",
    {},
)

transactions = plan.get(
    "transactions",
    [],
)

tx = (
    transactions[0]
    if transactions
    else {}
)

target = plan.get(
    "target",
    {},
)

protocol = target.get(
    "protocol",
    "https",
)

host = target.get(
    "host",
    "",
)

method = tx.get(
    "method",
    "",
)

request_path = tx.get(
    "path",
    "",
)

expected = tx.get(
    "expected_status",
    "UNRESOLVED",
)

expected_text = (
    "Pendiente de definir"
    if str(expected).upper()
    == "UNRESOLVED"
    else str(expected)
)

sla = plan.get(
    "sla",
    {},
)

print(
    f"Scenario        : "
    f"{metadata.get('name', path.parent.name)}"
)

print(
    f"Target          : "
    f"{method} "
    f"{protocol}://{host}{request_path}"
)

print(
    f"Usuarios        : "
    f"{params.get('threads')}"
)

print(
    f"Ramp-up         : "
    f"{params.get('ramp_time_seconds')} s"
)

print(
    f"Duración        : "
    f"{params.get('duration_seconds')} s"
)

print(
    f"Pacing          : "
    f"{params.get('pacing_seconds')} s"
)

print(
    f"Contrato HTTP   : "
    f"{expected_text}"
)

print(
    f"Error rate SLA  : "
    f"<= {sla.get('error_rate_threshold_pct')}%"
)

print(
    f"p95 SLA         : "
    f"<= {sla.get('p95_threshold_ms')} ms"
)

print(
    f"p99 SLA         : "
    f"<= {sla.get('p99_threshold_ms')} ms"
)

print(
    f"Plan            : "
    f"{plan.get('status')}"
)

print(
    f"Workload        : "
    f"{workload.get('status')}"
)

questions = plan.get(
    "open_questions",
    [],
)

if questions:
    print()
    print(
        "Información pendiente:"
    )

    for question in questions:
        print(
            f"- {question}"
        )
PY

echo
echo "---------------------------------------------------------------------"
echo "No se seleccionó herramienta de ejecución."
echo "No se autorizó ejecución."
echo "No se ejecutó carga."
echo "---------------------------------------------------------------------"
echo
echo "Revisa el diseño y decide si lo apruebas."
echo
