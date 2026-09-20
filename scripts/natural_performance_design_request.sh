#!/usr/bin/env bash

set -euo pipefail

ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1
  pwd
)"

cd "${ROOT}"

SCENARIO=""
COLLECTION=""
ENVIRONMENT=""
USERS=""
RAMP=""
DURATION=""
PACING=""

ORIGINAL_ARGS=("$@")

while [ "$#" -gt 0 ]; do
  case "$1" in
    --scenario)
      [ "$#" -ge 2 ] || {
        echo "DESIGN ERROR: --scenario requires a value." >&2
        exit 2
      }
      SCENARIO="$2"
      shift 2
      ;;

    --collection)
      [ "$#" -ge 2 ] || {
        echo "DESIGN ERROR: --collection requires a value." >&2
        exit 2
      }
      COLLECTION="$2"
      shift 2
      ;;

    --environment)
      [ "$#" -ge 2 ] || {
        echo "DESIGN ERROR: --environment requires a value." >&2
        exit 2
      }
      ENVIRONMENT="$2"
      shift 2
      ;;

    --users)
      [ "$#" -ge 2 ] || {
        echo "DESIGN ERROR: --users requires a value." >&2
        exit 2
      }
      USERS="$2"
      shift 2
      ;;

    --ramp-time-seconds)
      [ "$#" -ge 2 ] || {
        echo "DESIGN ERROR: --ramp-time-seconds requires a value." >&2
        exit 2
      }
      RAMP="$2"
      shift 2
      ;;

    --duration-seconds)
      [ "$#" -ge 2 ] || {
        echo "DESIGN ERROR: --duration-seconds requires a value." >&2
        exit 2
      }
      DURATION="$2"
      shift 2
      ;;

    --pacing-seconds)
      [ "$#" -ge 2 ] || {
        echo "DESIGN ERROR: --pacing-seconds requires a value." >&2
        exit 2
      }
      PACING="$2"
      shift 2
      ;;

    *)
      shift
      ;;
  esac
done

# ------------------------------------------------------------
# POSTMAN
# ------------------------------------------------------------

if [ -n "${COLLECTION}" ]; then

  [ -n "${SCENARIO}" ] || {
    echo "DESIGN ERROR: Postman design requires --scenario." >&2
    exit 2
  }

  [ -n "${USERS}" ] || {
    echo "DESIGN ERROR: Postman design requires --users." >&2
    exit 2
  }

  [ -n "${DURATION}" ] || {
    echo "DESIGN ERROR: Postman design requires --duration-seconds." >&2
    exit 2
  }

  [ -f "${COLLECTION}" ] || {
    echo "DESIGN ERROR: Postman collection not found: ${COLLECTION}" >&2
    exit 2
  }

  if [ -n "${ENVIRONMENT}" ] && [ ! -f "${ENVIRONMENT}" ]; then
    echo "DESIGN ERROR: Postman environment not found: ${ENVIRONMENT}" >&2
    exit 2
  fi

  WORKSPACE="workspaces/${SCENARIO}"

  rm -rf "${WORKSPACE}"

  COMMAND=(
    poetry run python
    scripts/performance_workflow.py
    intake
    --input "${COLLECTION}"
    --input-type postman
    --workspace "${WORKSPACE}"
    --users "${USERS}"
    --duration-seconds "${DURATION}"
  )

  if [ -n "${ENVIRONMENT}" ]; then
    COMMAND+=(
      --environment "${ENVIRONMENT}"
    )
  fi

  if [ -n "${RAMP}" ]; then
    COMMAND+=(
      --ramp-time-seconds "${RAMP}"
    )
  fi

  if [ -n "${PACING}" ]; then
    COMMAND+=(
      --pacing-seconds "${PACING}"
    )
  fi

  echo
  echo "======================================================================"
  echo "NATURAL PERFORMANCE DESIGN - POSTMAN"
  echo "======================================================================"
  echo "Scenario    : ${SCENARIO}"
  echo "Collection  : ${COLLECTION}"

  if [ -n "${ENVIRONMENT}" ]; then
    echo "Environment : ${ENVIRONMENT}"
  fi

  echo "Users       : ${USERS}"
  echo "Ramp-up     : ${RAMP:-profile default}"
  echo "Duration    : ${DURATION}"
  echo "Pacing      : ${PACING:-profile default}"
  echo "Load        : NOT EXECUTED"
  echo "======================================================================"
  echo

  "${COMMAND[@]}"

  MANIFEST="${WORKSPACE}/design-manifest.json"

  if [ ! -f "${MANIFEST}" ]; then
    echo
    echo "DESIGN ERROR: deterministic Postman intake completed but design-manifest.json was not produced:"
    echo "${MANIFEST}"
    echo
    echo "No performance load was executed."
    exit 2
  fi

  DESIGN_STATE="$(
    "${PYTHON:-python3}" - "${MANIFEST}" <<'PYJSON'
import json
import sys
from pathlib import Path

manifest = Path(sys.argv[1])

data = json.loads(
    manifest.read_text(
        encoding="utf-8"
    )
)

scenario = str(
    data.get(
        "scenario",
        ""
    )
).strip()

status = str(
    data.get(
        "status",
        ""
    )
).strip()

artifacts = (
    data.get(
        "artifacts"
    )
    or {}
)

plan_directory = str(
    artifacts.get(
        "plan_directory",
        ""
    )
).strip()

if not scenario:
    raise SystemExit(
        "design manifest has no canonical scenario"
    )

if status != "DESIGN_ARTIFACTS_READY":
    raise SystemExit(
        "design manifest is not DESIGN_ARTIFACTS_READY"
    )

if not plan_directory:
    raise SystemExit(
        "design manifest has no plan_directory"
    )

plan = (
    Path(plan_directory)
    / "test-plan.yaml"
).resolve()

if not plan.is_file():
    raise SystemExit(
        f"canonical plan does not exist: {plan}"
    )

print(
    scenario
)

print(
    plan
)
PYJSON
  )"

  CANONICAL_SCENARIO="$(
    printf '%s
' "${DESIGN_STATE}"       | sed -n '1p'
  )"

  PLAN="$(
    printf '%s
' "${DESIGN_STATE}"       | sed -n '2p'
  )"

  if [ -z "${CANONICAL_SCENARIO}" ]     || [ -z "${PLAN}" ]; then

    echo
    echo "DESIGN ERROR: unable to resolve canonical Postman design state."
    echo
    echo "No performance load was executed."
    exit 2
  fi

  echo
  echo "======================================================================"
  echo "POSTMAN DESIGN READY"
  echo "======================================================================"
  echo "Request id         : ${SCENARIO}"
  echo "Canonical scenario : ${CANONICAL_SCENARIO}"
  echo "Plan               : ${PLAN}"
  echo "Load               : NOT EXECUTED"
  echo "Next               : HUMAN REVIEW / APPROVAL"
  echo "======================================================================"

  exit 0
fi

# ------------------------------------------------------------
# HTTP / CURL / STRUCTURED SINGLE-API
# Preserve the already validated front door unchanged.
# ------------------------------------------------------------

exec \
  "${ROOT}/scripts/natural_performance_design_http.sh" \
  "${ORIGINAL_ARGS[@]}"
