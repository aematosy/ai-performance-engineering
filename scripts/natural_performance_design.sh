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
      *)
        echo "No se pudo interpretar la solicitud de diseño."
        exit 2
        ;;
    esac
  done
else
  if [ "$#" -lt 6 ]; then
    echo "No se recibieron todos los datos necesarios para diseñar la prueba."
    exit 2
  fi

  INPUT="$1"
  SCENARIO="$2"
  USERS="$3"
  RAMP_UP="$4"
  DURATION="$5"
  PACING="$6"
fi

for VALUE in   "${INPUT}"   "${SCENARIO}"   "${USERS}"   "${RAMP_UP}"   "${DURATION}"   "${PACING}"
do
  if [ -z "${VALUE}" ]; then
    echo "Faltan datos necesarios para diseñar la prueba."
    exit 2
  fi
done

WORKSPACE="workspaces/${SCENARIO}"
PLAN="tests/plans/${SCENARIO}/test-plan.yaml"

echo
echo "============================================================"
echo "DISEÑANDO PRUEBA DE PERFORMANCE"
echo "============================================================"
echo

poetry run python \
  scripts/performance_workflow.py \
  intake \
  --input "${INPUT}" \
  --input-type cli \
  --workspace "${WORKSPACE}" \
  --users "${USERS}" \
  --ramp-time-seconds "${RAMP_UP}" \
  --duration-seconds "${DURATION}" \
  --pacing-seconds "${PACING}"

python3 - "${PLAN}" "${SCENARIO}" <<'PY'
from pathlib import Path
import shutil
import sys
import yaml

plan_path = Path(sys.argv[1])
scenario = sys.argv[2]

plan = yaml.safe_load(
    plan_path.read_text(
        encoding="utf-8"
    )
)

transactions = plan.get(
    "transactions",
    [],
)

for transaction in transactions:
    if not isinstance(
        transaction,
        dict,
    ):
        continue

    transaction["expected_status"] = "UNRESOLVED"

    assertions = transaction.get(
        "assertions"
    )

    if isinstance(
        assertions,
        list,
    ):
        transaction["assertions"] = [
            item
            for item in assertions
            if not (
                isinstance(
                    item,
                    dict,
                )
                and str(
                    item.get("type", "")
                ).upper()
                == "RESPONSE_CODE"
            )
        ]

observability = plan.get(
    "observability"
)

if isinstance(
    observability,
    dict,
):
    metrics = observability.get(
        "metrics"
    )

    if isinstance(
        metrics,
        list,
    ):
        observability["metrics"] = [
            item
            for item in metrics
            if not (
                isinstance(
                    item,
                    dict,
                )
                and "jmeter"
                in str(
                    item.get("source", "")
                ).lower()
            )
        ]

plan_path.write_text(
    yaml.safe_dump(
        plan,
        sort_keys=False,
        allow_unicode=True,
        width=1000,
    ),
    encoding="utf-8",
)

md_path = plan_path.with_suffix(
    ".md"
)

if md_path.is_file():
    output = []

    for line in md_path.read_text(
        encoding="utf-8"
    ).splitlines():
        if (
            "JMeter Prometheus Listener"
            in line
        ):
            continue

        if "Expected status:" in line:
            prefix = line.split(
                "Expected status:",
                1,
            )[0]

            line = (
                prefix
                + "Expected status: "
                + "`UNRESOLVED`"
            )

        output.append(line)

    md_path.write_text(
        "\n".join(
            output
        ).rstrip()
        + "\n",
        encoding="utf-8",
    )

jmx = Path(
    "tests/generated"
) / f"{scenario}.jmx"

if jmx.is_file():
    history = (
        Path("workspaces")
        / scenario
        / "design-history"
    )

    history.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = (
        history
        / jmx.name
    )

    if destination.exists():
        destination.unlink()

    shutil.move(
        str(jmx),
        str(destination),
    )

    meta = Path(
        str(jmx)
        + ".meta.json"
    )

    if meta.is_file():
        shutil.move(
            str(meta),
            str(
                history
                / meta.name
            ),
        )
PY

poetry run python \
  scripts/performance_workflow.py \
  review \
  --plan "${PLAN}"

echo
echo "============================================================"
echo "DISEÑO LISTO PARA REVISIÓN HUMANA"
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
    f"HTTP     : "
    f"{tx.get('expected_status', 'UNRESOLVED')}"
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
echo "No se ha seleccionado motor."
echo "No se ha autorizado ejecución."
echo "No se ha ejecutado carga."
echo
echo "Esperando aprobación humana del diseño."
