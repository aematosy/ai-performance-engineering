#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

# Internal runtime bootstrap.
# Users and AI clients must not need to configure PYTHONPATH.
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

SCENARIO=""

if \
  [ "$#" -ge 2 ] \
  && [ "$1" = "--scenario" ]
then
  SCENARIO="$2"
elif [ "$#" -ge 1 ]; then
  SCENARIO="$1"
fi

if [ -z "${SCENARIO}" ]; then
  echo
  echo "No se pudo determinar qué prueba deseas preparar."
  echo "No se ejecutó carga."
  exit 2
fi

PLAN="tests/plans/${SCENARIO}/test-plan.yaml"
WORKSPACE="workspaces/${SCENARIO}"
PROFILE="${WORKSPACE}/execution-profile.yaml"
MODEL="${WORKSPACE}/normalized-performance-model.json"

HUMAN="${PERF_HUMAN_NAME:-$(whoami)}"

for REQUIRED in \
  "${PLAN}" \
  "${PROFILE}" \
  "${MODEL}"
do
  if [ ! -f "${REQUIRED}" ]; then
    echo
    echo "Falta información necesaria para continuar."
    echo "No se ejecutó carga."
    exit 2
  fi
done

echo
echo "======================================================================"
echo "PREPARANDO LA PRUEBA PARA UNA POSIBLE EJECUCIÓN"
echo "======================================================================"
echo
echo "Voy a comprobar que el diseño tenga toda la información"
echo "funcional necesaria antes de presentar el resumen final."
echo
echo "Todavía NO voy a:"
echo "- ejecutar carga;"
echo "- seleccionar JMeter o Locust;"
echo "- cambiar el target;"
echo "- cambiar el workload aprobado."
echo "======================================================================"
echo

# Ask only meaningful functional questions.
poetry run python \
  scripts/resolve_response_contract.py \
  --plan "${PLAN}"

# Validate automatically. No additional human confirmation is needed.
poetry run python \
  scripts/validate_test_plan.py \
  --plan "${PLAN}"

PLAN_STATUS="$(
  poetry run python - "${PLAN}" <<'PY'
from pathlib import Path
import sys
import yaml

plan = yaml.safe_load(
    Path(
        sys.argv[1]
    ).read_text(
        encoding="utf-8"
    )
)

print(
    str(
        plan.get(
            "status",
            "",
        )
    ).upper()
)
PY
)"

if [ "${PLAN_STATUS}" != "APPROVED" ]; then
  poetry run python \
    scripts/performance_workflow.py \
    approve \
    --plan "${PLAN}" \
    --approved-by "${HUMAN}"
fi

echo
echo "======================================================================"
echo "RESUMEN FINAL ANTES DE EJECUTAR"
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
)

sla = plan.get(
    "sla",
    {},
)

print(
    f"Scenario       : "
    f"{metadata.get('name', path.parent.name)}"
)

print(
    f"Target         : "
    f"{method} "
    f"{protocol}://{host}{request_path}"
)

print(
    f"HTTP esperado  : "
    f"{expected}"
)

print(
    f"Usuarios       : "
    f"{params.get('threads')}"
)

print(
    f"Ramp-up        : "
    f"{params.get('ramp_time_seconds')} s"
)

print(
    f"Duración       : "
    f"{params.get('duration_seconds')} s"
)

print(
    f"Pacing         : "
    f"{params.get('pacing_seconds')} s"
)

print(
    f"Error rate SLA : "
    f"<= {sla.get('error_rate_threshold_pct')}%"
)

print(
    f"p95 SLA        : "
    f"<= {sla.get('p95_threshold_ms')} ms"
)

print(
    f"p99 SLA        : "
    f"<= {sla.get('p99_threshold_ms')} ms"
)

print(
    f"Plan           : "
    f"{plan.get('status')}"
)

print(
    f"Workload       : "
    f"{workload.get('status')}"
)
PY

echo "======================================================================"
echo
echo "Si continúas:"
echo "- elegirás JMeter o Locust;"
echo "- se preparará el artefacto para esa herramienta;"
echo "- se ejecutarán las validaciones de seguridad;"
echo "- y finalmente se iniciará la carga aprobada."
echo
echo "No se modificará el target ni el workload."
echo

read -r -p \
  "¿Deseas ejecutar esta prueba? [s/N]: " \
  EXECUTE_CONFIRMATION

case "${EXECUTE_CONFIRMATION}" in
  s|S|si|Si|SI|sí|Sí|SÍ|y|Y|yes|YES)
    ;;
  *)
    echo
    echo "Ejecución cancelada."
    echo "No se inició carga."
    exit 0
    ;;
esac

echo
echo "======================================================================"
echo "¿CON QUÉ HERRAMIENTA DESEAS EJECUTARLA?"
echo "======================================================================"
echo

poetry run python \
  scripts/performance_workflow.py \
  select-engine \
  --profile "${PROFILE}"

ENGINE="$(
  poetry run python - "${PROFILE}" <<'PY'
from pathlib import Path
import sys
import yaml

profile = yaml.safe_load(
    Path(
        sys.argv[1]
    ).read_text(
        encoding="utf-8"
    )
)

print(
    str(
        profile.get(
            "engine",
            "",
        )
    ).strip().lower()
)
PY
)"

if \
  [ "${ENGINE}" != "jmeter" ] \
  && [ "${ENGINE}" != "locust" ]
then
  echo
  echo "No se pudo determinar la herramienta seleccionada."
  echo "No se ejecutó carga."
  exit 2
fi

poetry run python \
  scripts/performance_workflow.py \
  prepare \
  --model "${MODEL}" \
  --profile "${PROFILE}"

case "${ENGINE}" in
  jmeter)
    ARTIFACT="tests/generated/${SCENARIO}.jmx"
    ;;
  locust)
    ARTIFACT="tests/generated/locust/${SCENARIO}/locustfile.py"
    ;;
esac

if [ ! -f "${ARTIFACT}" ]; then
  echo
  echo "No se pudo preparar correctamente la prueba."
  echo "No se ejecutó carga."
  exit 2
fi

poetry run python \
  scripts/performance_workflow.py \
  authorize \
  --plan "${PLAN}" \
  --profile "${PROFILE}" \
  --artifact "${ARTIFACT}" \
  --authorized-by "${HUMAN}" \
  --notes \
  "Authorized through the natural Performance Engineering flow."

poetry run python \
  scripts/performance_workflow.py \
  preflight \
  --plan "${PLAN}" \
  --profile "${PROFILE}" \
  --artifact "${ARTIFACT}"

echo
echo "======================================================================"
echo "VALIDACIONES COMPLETADAS"
echo "======================================================================"
echo "Herramienta : $(echo "${ENGINE}" | tr '[:lower:]' '[:upper:]')"
echo "Estado      : LISTO PARA EJECUTAR"
echo
echo "La carga comenzará ahora con los parámetros aprobados."
echo "======================================================================"
echo

printf 'RUN\n' \
  | poetry run python \
      scripts/performance_workflow.py \
      execute \
      --plan "${PLAN}" \
      --profile "${PROFILE}" \
      --artifact "${ARTIFACT}"
