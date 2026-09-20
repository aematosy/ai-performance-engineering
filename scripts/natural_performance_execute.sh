#!/usr/bin/env bash

set -euo pipefail

ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." \
    >/dev/null 2>&1
  pwd
)"

cd "${ROOT}"

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

PYTHON="$(
  poetry run which python
)"

SCENARIO=""

ARGS=(
  "$@"
)

INDEX=0

while [ "${INDEX}" -lt "${#ARGS[@]}" ]; do
  CURRENT="${ARGS[$INDEX]}"

  case "${CURRENT}" in
    --scenario)
      NEXT_INDEX=$((INDEX + 1))

      if [ "${NEXT_INDEX}" -ge "${#ARGS[@]}" ]; then
        echo "ERROR: --scenario requiere un valor."
        exit 2
      fi

      SCENARIO="${ARGS[$NEXT_INDEX]}"
      INDEX=$((INDEX + 2))
      continue
      ;;
  esac

  INDEX=$((INDEX + 1))
done

if [ -z "${SCENARIO}" ] \
  && [ "${#ARGS[@]}" -gt 0 ] \
  && [[ "${ARGS[0]}" != --* ]]; then
  SCENARIO="${ARGS[0]}"
fi

if [ -z "${SCENARIO}" ]; then
  echo "ERROR: No se pudo determinar el escenario."
  exit 2
fi

EXPORTER_PID=""
EXPORTER_STARTED="false"

cleanup() {
  if [ "${EXPORTER_STARTED}" = "true" ] \
    && [ -n "${EXPORTER_PID}" ]; then

    kill "${EXPORTER_PID}" \
      >/dev/null 2>&1 || true

    wait "${EXPORTER_PID}" \
      >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

PORT_PID="$(
  lsof \
    -tiTCP:9271 \
    -sTCP:LISTEN \
    2>/dev/null \
    | head -1 \
    || true
)"

if [ -n "${PORT_PID}" ]; then
  kill "${PORT_PID}" \
    >/dev/null 2>&1 || true

  sleep 1
fi

"${PYTHON}" \
  scripts/locust_metrics_exporter.py \
  --results-root "${ROOT}/results" \
  --scenario "${SCENARIO}" \
  --port 9271 \
  >/tmp/demo-agent-perf-locust-exporter.log \
  2>&1 &

EXPORTER_PID="$!"
EXPORTER_STARTED="true"

sleep 1

exec_status=0

"${PYTHON}" \
  scripts/natural_performance_execute.py \
  "$@" \
  || exec_status="$?"

exit "${exec_status}"
