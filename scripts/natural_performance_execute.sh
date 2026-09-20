#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

SCENARIO=""

if [ "$#" -ge 2 ] && [ "$1" = "--scenario" ]; then
  SCENARIO="$2"
elif [ "$#" -ge 1 ]; then
  SCENARIO="$1"
fi

if [ -z "${SCENARIO}" ]; then
  echo "No se pudo determinar qué prueba deseas ejecutar."
  exit 2
fi

PLAN="tests/plans/${SCENARIO}/test-plan.yaml"
WORKSPACE="workspaces/${SCENARIO}"
PROFILE="${WORKSPACE}/execution-profile.yaml"
MODEL="${WORKSPACE}/normalized-performance-model.json"

HUMAN="${PERF_HUMAN_NAME:-$(whoami)}"

test -f "${PLAN}"
test -f "${PROFILE}"
test -f "${MODEL}"

PLAN_STATUS="$(
  python3 - "${PLAN}" <<'PY'
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
echo "============================================================"
echo "RESUMEN FINAL DE LA PRUEBA"
echo "============================================================"

python3 - "${PLAN}" <<'PY'
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

print(
    f"Scenario : "
    f"{metadata.get('name', path.parent.name)}"
)

print(
    f"Target   : "
    f"{method} "
    f"{protocol}://{host}{request_path}"
)

print(
    f"Usuarios : "
    f"{workload.get('users', workload.get('threads'))}"
)

print(
    f"Ramp-up  : "
    f"{workload.get('ramp_up_seconds', workload.get('ramp_time_seconds'))} s"
)

print(
    f"Duración : "
    f"{workload.get('duration_seconds')} s"
)

print(
    f"Pacing   : "
    f"{workload.get('pacing_seconds')} s"
)

print(
    f"Plan     : "
    f"{plan.get('status')}"
)

print(
    f"Workload : "
    f"{workload.get('status')}"
)
PY

echo "============================================================"
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
echo "Selecciona dónde deseas ejecutar la prueba:"
echo

poetry run python \
  scripts/performance_workflow.py \
  select-engine \
  --profile "${PROFILE}"

ENGINE="$(
  python3 - "${PROFILE}" <<'PY'
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
    ).lower()
)
PY
)"

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
  *)
    echo "Motor no soportado: ${ENGINE}"
    exit 2
    ;;
esac

test -f "${ARTIFACT}"

poetry run python \
  scripts/performance_workflow.py \
  authorize \
  --plan "${PLAN}" \
  --profile "${PROFILE}" \
  --artifact "${ARTIFACT}" \
  --authorized-by "${HUMAN}" \
  --notes "Authorized through natural Performance Engineering workflow."

poetry run python \
  scripts/performance_workflow.py \
  preflight \
  --plan "${PLAN}" \
  --profile "${PROFILE}" \
  --artifact "${ARTIFACT}"

echo
echo "============================================================"
echo "TODO VALIDADO"
echo "============================================================"
echo "Motor     : $(echo "${ENGINE}" | tr '[:lower:]' '[:upper:]')"
echo "Estado    : LISTO PARA EJECUTAR"
echo "============================================================"
echo

printf 'RUN\n' | \
  poetry run python \
    scripts/performance_workflow.py \
    execute \
    --plan "${PLAN}" \
    --profile "${PROFILE}" \
    --artifact "${ARTIFACT}"
