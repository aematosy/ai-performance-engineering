#!/usr/bin/env bash

set -euo pipefail

ROOT="$(
  cd "$(dirname "$0")/.." \
    && pwd
)"

cd "${ROOT}"

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

exec poetry run python \
  scripts/natural_performance_execute.py \
  "$@"
