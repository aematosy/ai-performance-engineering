#!/usr/bin/env bash

set -euo pipefail

ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." \
    >/dev/null 2>&1
  pwd
)"

cd "${ROOT}"

# Natural executions always request the post-execution professional bundle.
# Report generation is post-execution and must never start load by itself.
export PERF_AUTO_PROFESSIONAL_REPORT="${PERF_AUTO_PROFESSIONAL_REPORT:-1}"

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

    curl \
      -fsS \
      -X POST \
      http://localhost:9271/finish \
      >/dev/null 2>&1 \
      || true

    # Prometheus scrapes Locust every 2 seconds.
    # Keep the exporter alive long enough to publish
    # the final INACTIVE/zero sample before shutdown.
    sleep 4

    kill "${EXPORTER_PID}" \
      >/dev/null 2>&1 || true

    wait "${EXPORTER_PID}" \
      >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

exec_status=0

RESOLVED_ARGS=("$@")

REQUESTED_SCENARIO="${SCENARIO}"
CANONICAL_SCENARIO="${SCENARIO}"

for ((i=0; i<${#RESOLVED_ARGS[@]}; i++)); do
  if [ "${RESOLVED_ARGS[$i]}" = "--scenario" ]; then

    if [ $((i + 1)) -ge "${#RESOLVED_ARGS[@]}" ]; then
      echo "ERROR: --scenario requires a value." >&2
      exit 2
    fi

    REQUESTED_SCENARIO="${RESOLVED_ARGS[$((i + 1))]}"

    CANONICAL_SCENARIO="$(
      "${PYTHON}"         scripts/resolve_execution_scenario.py         --scenario "${REQUESTED_SCENARIO}"
    )"

    if [ "${CANONICAL_SCENARIO}" != "${REQUESTED_SCENARIO}" ]; then
      echo
      echo "[OK] Execution scenario resolved:"
      echo "     Request   : ${REQUESTED_SCENARIO}"
      echo "     Canonical : ${CANONICAL_SCENARIO}"
      echo
    fi

    RESOLVED_ARGS[$((i + 1))]="${CANONICAL_SCENARIO}"

    break
  fi
done

PROFILE_PATH="${ROOT}/workspaces/${REQUESTED_SCENARIO}/execution-profile.yaml"

ENGINE=""

if [ -f "${PROFILE_PATH}" ]; then
  ENGINE="$(
    "${PYTHON}" - "${PROFILE_PATH}" <<'PY'
import sys
from pathlib import Path
import yaml

path = Path(sys.argv[1])
payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
print(str(payload.get("engine", "")).strip().lower())
PY
  )"
fi

if [ "${ENGINE}" = "locust" ]; then
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
    --scenario "${CANONICAL_SCENARIO}" \
    --port 9271 \
    >/tmp/demo-agent-perf-locust-exporter.log \
    2>&1 &

  EXPORTER_PID="$!"
  EXPORTER_STARTED="true"

  EXPORTER_READY="false"

  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS http://localhost:9271/metrics >/dev/null 2>&1; then
      EXPORTER_READY="true"
      break
    fi

    sleep 0.2
  done

  if [ "${EXPORTER_READY}" != "true" ]; then
    echo "ERROR: Locust metrics exporter did not become ready on port 9271." >&2
    exit 2
  fi
fi

PERF_REQUESTED_SCENARIO="${REQUESTED_SCENARIO:-}" \
"${PYTHON}" \
  scripts/natural_performance_execute.py \
  "${RESOLVED_ARGS[@]}" \
  || exec_status="$?"

if [ "${exec_status}" -eq 0 ]; then
  CHECK_ONLY_REQUESTED="false"

  for ARG in "$@"; do
    if [ "${ARG}" = "--check-only" ]; then
      CHECK_ONLY_REQUESTED="true"
      break
    fi
  done

  if [ "${CHECK_ONLY_REQUESTED}" = "true" ]; then
    echo
    echo "[CHECK ONLY] Finalizer omitido: no existe ejecución real que registrar."
  else
    "${PYTHON}" \
      scripts/finalize_execution_state.py \
      -- \
      "${RESOLVED_ARGS[@]}" \
      || echo "[WARN] Execution completed but state pointer synchronization failed."
  fi
fi

exit "${exec_status}"
