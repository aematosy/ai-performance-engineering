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

if [ -z "${PORT_PID}" ]; then
  "${PYTHON}" \
    scripts/locust_metrics_exporter.py \
    --results-root results \
    --port 9271 \
    >/tmp/demo-agent-perf-locust-exporter.log \
    2>&1 &

  EXPORTER_PID="$!"
  EXPORTER_STARTED="true"

  sleep 1
fi

exec_status=0

"${PYTHON}" \
  scripts/natural_performance_execute.py \
  "$@" \
  || exec_status="$?"

exit "${exec_status}"
