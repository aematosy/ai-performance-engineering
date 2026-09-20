#!/usr/bin/env bash

set -euo pipefail

ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." \
    >/dev/null 2>&1
  pwd
)"

cd "${ROOT}"

SCENARIO=""
METHOD=""
URL=""
BODY=""
USERS=""
RAMP=""
DURATION=""
PACING=""

HEADERS=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --scenario)
      SCENARIO="${2:-}"
      shift 2
      ;;

    --method)
      METHOD="${2:-}"
      shift 2
      ;;

    --url)
      URL="${2:-}"
      shift 2
      ;;

    --header)
      HEADERS+=("${2:-}")
      shift 2
      ;;

    --body)
      BODY="${2:-}"
      shift 2
      ;;

    --users)
      USERS="${2:-}"
      shift 2
      ;;

    --ramp-time-seconds)
      RAMP="${2:-}"
      shift 2
      ;;

    --duration-seconds)
      DURATION="${2:-}"
      shift 2
      ;;

    --pacing-seconds)
      PACING="${2:-}"
      shift 2
      ;;

    *)
      echo "DESIGN REQUEST ERROR: argumento no reconocido: $1" >&2
      exit 2
      ;;
  esac
done

require_value() {
  local name="$1"
  local value="$2"

  if [ -z "${value}" ]; then
    echo "DESIGN REQUEST ERROR: falta ${name}" >&2
    exit 2
  fi
}

require_value "--scenario" "${SCENARIO}"
require_value "--method" "${METHOD}"
require_value "--url" "${URL}"
require_value "--users" "${USERS}"
require_value "--ramp-time-seconds" "${RAMP}"
require_value "--duration-seconds" "${DURATION}"
require_value "--pacing-seconds" "${PACING}"

INPUT_DIR="${ROOT}/inputs/curl"
INPUT="${INPUT_DIR}/${SCENARIO}.curl"

mkdir -p "${INPUT_DIR}"

export DESIGN_METHOD="${METHOD}"
export DESIGN_URL="${URL}"
export DESIGN_BODY="${BODY}"
export DESIGN_INPUT="${INPUT}"

HEADER_FILE="$(
  mktemp
)"

cleanup() {
  rm -f "${HEADER_FILE}"
}

trap cleanup EXIT

if [ "${#HEADERS[@]}" -gt 0 ]; then
  printf '%s\n' "${HEADERS[@]}" > "${HEADER_FILE}"
fi

export DESIGN_HEADER_FILE="${HEADER_FILE}"

PYTHON="$(
  poetry run which python
)"

"${PYTHON}" - <<'PY'
from __future__ import annotations

import os
from pathlib import Path


method = os.environ["DESIGN_METHOD"].strip().upper()
url = os.environ["DESIGN_URL"].strip()
body = os.environ.get("DESIGN_BODY", "")
input_path = Path(os.environ["DESIGN_INPUT"])
header_file = Path(os.environ["DESIGN_HEADER_FILE"])


def quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


headers = []

if header_file.is_file():
    headers = [
        line.rstrip("\n")
        for line in header_file.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


parts = [
    f"curl --request {method}",
    f"--url {quote(url)}",
]

for header in headers:
    parts.append(
        f"--header {quote(header)}"
    )

if body:
    parts.append(
        f"--data {quote(body)}"
    )


lines = []

for index, part in enumerate(parts):
    suffix = " \\" if index < len(parts) - 1 else ""

    if index == 0:
        lines.append(
            part + suffix
        )
    else:
        lines.append(
            "  " + part + suffix
        )


input_path.write_text(
    "\n".join(lines) + "\n",
    encoding="utf-8",
)

print(
    "[OK] Input materializado:",
    input_path,
)
PY

echo
echo "======================================================================"
echo "DISEÑANDO PRUEBA"
echo "======================================================================"

scripts/natural_performance_design.sh \
  --input "${INPUT}" \
  --scenario "${SCENARIO}" \
  --users "${USERS}" \
  --ramp-time-seconds "${RAMP}" \
  --duration-seconds "${DURATION}" \
  --pacing-seconds "${PACING}"

PLAN="${ROOT}/tests/plans/${SCENARIO}/test-plan.yaml"

if [ ! -f "${PLAN}" ]; then
  echo "DESIGN REQUEST ERROR: no se generó ${PLAN}" >&2
  exit 2
fi

echo
echo "======================================================================"
echo "VALIDANDO CONTRATO HTTP"
echo "======================================================================"

NEEDS_CONTRACT="$(
  PLAN_PATH="${PLAN}" \
  "${PYTHON}" - <<'PY'
from __future__ import annotations

import os
from pathlib import Path

import yaml


path = Path(
    os.environ["PLAN_PATH"]
)

payload = yaml.safe_load(
    path.read_text(
        encoding="utf-8"
    )
)

transactions = (
    payload.get("transactions")
    or []
)

if not transactions:
    print("yes")
    raise SystemExit(0)

value = transactions[0].get(
    "expected_status"
)

unresolved = str(
    value
).strip().upper() in {
    "",
    "NONE",
    "UNRESOLVED",
}

print(
    "yes"
    if unresolved
    else "no"
)
PY
)"

if [ "${NEEDS_CONTRACT}" = "yes" ]; then
  set +e

  "${PYTHON}" \
    scripts/resolve_functional_response_contract.py \
    --plan "${PLAN}" \
    --curl "${INPUT}"

  CONTRACT_RC="$?"

  set -e

  if [ "${CONTRACT_RC}" -ne 0 ] \
    && [ "${CONTRACT_RC}" -ne 2 ]; then

    echo "DESIGN REQUEST ERROR: falló la validación funcional." >&2
    exit "${CONTRACT_RC}"
  fi
fi

echo
echo "======================================================================"
echo "VALIDANDO PLAN FINAL"
echo "======================================================================"

"${PYTHON}" \
  scripts/validate_test_plan.py \
  --plan "${PLAN}"

echo
echo "======================================================================"
echo "RESUMEN DEL DISEÑO"
echo "======================================================================"

PLAN_PATH="${PLAN}" \
"${PYTHON}" - <<'PY'
from __future__ import annotations

import os
from pathlib import Path

import yaml


path = Path(
    os.environ["PLAN_PATH"]
)

payload = yaml.safe_load(
    path.read_text(
        encoding="utf-8"
    )
)

transactions = (
    payload.get("transactions")
    or []
)

workload = (
    payload.get("workload")
    or {}
)

parameters = (
    workload.get("parameters")
    or {}
)

sla = (
    payload.get("sla")
    or {}
)

transaction = (
    transactions[0]
    if transactions
    else {}
)

status = transaction.get(
    "expected_status",
    "UNRESOLVED",
)

method = transaction.get(
    "method",
    "",
)

target = payload.get(
    "target"
) or {}

protocol = target.get(
    "protocol",
    "https",
)

host = target.get(
    "host",
    "",
)

path_value = transaction.get(
    "path",
    "",
)

print(
    f"Escenario       : {payload.get('metadata', {}).get('name')}"
)

print(
    f"Target          : {method} {protocol}://{host}{path_value}"
)

print(
    f"HTTP esperado   : {status}"
)

print(
    f"Usuarios        : {parameters.get('threads')}"
)

print(
    f"Ramp-up         : {parameters.get('ramp_time_seconds')} s"
)

print(
    f"Duración        : {parameters.get('duration_seconds')} s"
)

print(
    f"Pacing          : {parameters.get('pacing_seconds')} s"
)

print(
    f"Error rate SLA  : <= {sla.get('error_rate_threshold_pct')}%"
)

print(
    f"p95 SLA         : <= {sla.get('p95_threshold_ms')} ms"
)

print(
    f"p99 SLA         : <= {sla.get('p99_threshold_ms')} ms"
)

unresolved = str(
    status
).strip().upper() in {
    "",
    "NONE",
    "UNRESOLVED",
}

print()

if unresolved:
    print(
        "Estado          : DESIGN_NEEDS_FUNCTIONAL_INPUT"
    )
else:
    print(
        "Estado          : DESIGN_READY_FOR_REVIEW"
    )

print()
print(
    "No se ejecutó carga de performance."
)
PY

echo
echo "======================================================================"
echo "DESIGN REQUEST COMPLETE"
echo "======================================================================"
