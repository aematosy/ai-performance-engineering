#!/usr/bin/env python3
"""
Administra el historial de ejecuciones de Performance Engineering.

Responsabilidades:

- Crear el archivo de historial si no existe.
- Registrar ejecuciones desde metadata.json y analysis.json.
- Evitar duplicados por execution_id.
- Listar ejecuciones recientes.
- Comparar una ejecución con la anterior del mismo escenario.
- Escribir el historial de forma atómica.

Comandos:

Registrar una ejecución:

    poetry run python scripts/history_manager.py add \
      --metadata results/<execution_id>/metadata.json

Listar ejecuciones:

    poetry run python scripts/history_manager.py list \
      --limit 10

Comparar la última ejecución:

    poetry run python scripts/history_manager.py compare \
      --scenario "Config Integrated Baseline"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from config_loader import ConfigurationError, ConfigLoader, load_config


HISTORY_SCHEMA_VERSION = "1.0"


class HistoryError(RuntimeError):
    """Error controlado del historial de ejecuciones."""


def resolve_path(
    path: str | Path,
    project_root: Path,
) -> Path:
    resolved = Path(path).expanduser()

    if not resolved.is_absolute():
        resolved = project_root / resolved

    return resolved.resolve()


def load_json_object(
    path: Path,
    description: str,
) -> dict[str, Any]:
    if not path.exists():
        raise HistoryError(
            f"No existe {description}: {path}"
        )

    if not path.is_file():
        raise HistoryError(
            f"{description} no es un archivo: {path}"
        )

    if path.stat().st_size == 0:
        raise HistoryError(
            f"{description} está vacío: {path}"
        )

    try:
        with path.open(encoding="utf-8") as file:
            payload = json.load(file)
    except OSError as exc:
        raise HistoryError(
            f"No se pudo leer {description} '{path}': {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise HistoryError(
            f"{description} no contiene JSON válido: {path}. "
            f"Detalle: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise HistoryError(
            f"{description} debe contener un objeto JSON."
        )

    return payload


def write_json_atomically(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{path.stem}-",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

            json.dump(
                payload,
                temporary_file,
                indent=2,
                ensure_ascii=False,
            )
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        temporary_path.replace(path)

    except OSError as exc:
        raise HistoryError(
            f"No se pudo escribir el historial '{path}': {exc}"
        ) from exc

    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def create_empty_history() -> dict[str, Any]:
    now = datetime.now().astimezone().isoformat()

    return {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "created_at": now,
        "updated_at": now,
        "total_executions": 0,
        "executions": [],
    }


def load_history(
    history_path: Path,
) -> dict[str, Any]:
    if not history_path.exists():
        return create_empty_history()

    history = load_json_object(
        history_path,
        "el archivo de historial",
    )

    executions = history.get("executions")

    if not isinstance(executions, list):
        raise HistoryError(
            "El historial no contiene una lista válida en 'executions'."
        )

    history.setdefault(
        "schema_version",
        HISTORY_SCHEMA_VERSION,
    )
    history.setdefault(
        "created_at",
        datetime.now().astimezone().isoformat(),
    )
    history.setdefault(
        "updated_at",
        datetime.now().astimezone().isoformat(),
    )
    history["total_executions"] = len(executions)

    return history


def get_nested(
    payload: dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:
    current: Any = payload

    for key in keys:
        if not isinstance(current, dict):
            return default

        if key not in current:
            return default

        current = current[key]

    return current


def normalize_number(
    value: Any,
) -> float | int | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return value

    try:
        numeric = float(str(value))
    except (TypeError, ValueError):
        return None

    if numeric.is_integer():
        return int(numeric)

    return numeric


def build_history_entry(
    metadata: dict[str, Any],
    metadata_path: Path,
) -> dict[str, Any]:
    execution_id = metadata.get("execution_id")

    if not isinstance(execution_id, str) or not execution_id.strip():
        raise HistoryError(
            "metadata.json no contiene un execution_id válido."
        )

    scenario = metadata.get("scenario")

    if not isinstance(scenario, str) or not scenario.strip():
        raise HistoryError(
            "metadata.json no contiene un scenario válido."
        )

    metrics = metadata.get("metrics") or {}

    if not isinstance(metrics, dict):
        metrics = {}

    response_time = metrics.get("response_time_ms") or {}

    if not isinstance(response_time, dict):
        response_time = {}

    test_configuration = (
        metadata.get("test_configuration") or {}
    )

    if not isinstance(test_configuration, dict):
        test_configuration = {}

    files = metadata.get("files") or {}

    if not isinstance(files, dict):
        files = {}

    entry = {
        "execution_id": execution_id.strip(),
        "generated_at": metadata.get("generated_at"),
        "scenario": scenario.strip(),
        "target": metadata.get("target"),
        "environment": metadata.get("environment"),
        "verdict": metadata.get("verdict"),
        "configuration": {
            "threads": normalize_number(
                test_configuration.get("threads")
            ),
            "ramp_time_seconds": normalize_number(
                test_configuration.get("ramp_time_seconds")
            ),
            "duration_seconds": normalize_number(
                test_configuration.get("duration_seconds")
            ),
            "prometheus_port": normalize_number(
                test_configuration.get("prometheus_port")
            ),
        },
        "metrics": {
            "total_requests": normalize_number(
                metrics.get("total_requests")
            ),
            "success_rate_pct": normalize_number(
                metrics.get("success_rate_pct")
            ),
            "error_rate_pct": normalize_number(
                metrics.get("error_rate_pct")
            ),
            "throughput_req_per_sec": normalize_number(
                metrics.get("throughput_req_per_sec")
            ),
            "p50_ms": normalize_number(
                response_time.get("p50")
            ),
            "p90_ms": normalize_number(
                response_time.get("p90")
            ),
            "p95_ms": normalize_number(
                response_time.get("p95")
            ),
            "p99_ms": normalize_number(
                response_time.get("p99")
            ),
            "maximum_ms": normalize_number(
                response_time.get("max")
            ),
        },
        "technical_error_count": len(
            metadata.get("technical_errors") or []
        ),
        "files": {
            "metadata": str(metadata_path),
            "analysis": files.get("analysis"),
            "jtl": files.get("jtl"),
            "executive_report": files.get(
                "executive_report"
            ),
            "jmeter_dashboard": files.get(
                "jmeter_dashboard"
            ),
        },
    }

    return entry


def register_execution(
    history_path: Path,
    metadata_path: Path,
    *,
    replace_existing: bool = False,
) -> dict[str, Any]:
    metadata = load_json_object(
        metadata_path,
        "metadata.json",
    )

    entry = build_history_entry(
        metadata,
        metadata_path,
    )

    history = load_history(history_path)
    executions = history["executions"]

    existing_index: int | None = None

    for index, existing in enumerate(executions):
        if not isinstance(existing, dict):
            continue

        if (
            existing.get("execution_id")
            == entry["execution_id"]
        ):
            existing_index = index
            break

    if existing_index is not None:
        if not replace_existing:
            raise HistoryError(
                "La ejecución ya está registrada: "
                f"{entry['execution_id']}. "
                "Usa --replace para actualizarla."
            )

        executions[existing_index] = entry
        action = "updated"

    else:
        executions.append(entry)
        action = "created"

    executions.sort(
        key=lambda item: str(
            item.get("generated_at") or ""
        )
    )

    history["schema_version"] = HISTORY_SCHEMA_VERSION
    history["updated_at"] = (
        datetime.now().astimezone().isoformat()
    )
    history["total_executions"] = len(executions)

    write_json_atomically(
        history_path,
        history,
    )

    return {
        "action": action,
        "entry": entry,
        "history_path": str(history_path),
        "total_executions": history["total_executions"],
    }


def format_number(
    value: Any,
    decimals: int = 3,
) -> str:
    if value is None:
        return "N/A"

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        return f"{value:.{decimals}f}".rstrip("0").rstrip(".")

    return str(value)


def list_executions(
    history_path: Path,
    *,
    limit: int,
    scenario: str | None = None,
) -> list[dict[str, Any]]:
    history = load_history(history_path)
    executions = history["executions"]

    filtered = []

    for entry in executions:
        if not isinstance(entry, dict):
            continue

        if scenario:
            entry_scenario = str(
                entry.get("scenario") or ""
            )

            if entry_scenario.casefold() != scenario.casefold():
                continue

        filtered.append(entry)

    filtered.sort(
        key=lambda item: str(
            item.get("generated_at") or ""
        ),
        reverse=True,
    )

    return filtered[:limit]


def calculate_change(
    previous: Any,
    current: Any,
) -> dict[str, Any]:
    previous_value = normalize_number(previous)
    current_value = normalize_number(current)

    if previous_value is None or current_value is None:
        return {
            "previous": previous_value,
            "current": current_value,
            "absolute_change": None,
            "percentage_change": None,
        }

    absolute_change = current_value - previous_value

    if previous_value == 0:
        percentage_change = None
    else:
        percentage_change = (
            absolute_change / previous_value
        ) * 100

    return {
        "previous": previous_value,
        "current": current_value,
        "absolute_change": round(
            absolute_change,
            4,
        ),
        "percentage_change": (
            round(percentage_change, 2)
            if percentage_change is not None
            else None
        ),
    }


def compare_latest_executions(
    history_path: Path,
    scenario: str,
) -> dict[str, Any]:
    executions = list_executions(
        history_path,
        limit=2,
        scenario=scenario,
    )

    if not executions:
        raise HistoryError(
            f"No existen ejecuciones para el escenario: {scenario}"
        )

    if len(executions) < 2:
        raise HistoryError(
            "Se necesitan al menos dos ejecuciones del mismo "
            f"escenario para comparar: {scenario}"
        )

    current = executions[0]
    previous = executions[1]

    current_metrics = current.get("metrics") or {}
    previous_metrics = previous.get("metrics") or {}

    comparison = {
        "scenario": scenario,
        "previous_execution_id": previous.get(
            "execution_id"
        ),
        "current_execution_id": current.get(
            "execution_id"
        ),
        "previous_verdict": previous.get("verdict"),
        "current_verdict": current.get("verdict"),
        "metrics": {
            "throughput_req_per_sec": calculate_change(
                previous_metrics.get(
                    "throughput_req_per_sec"
                ),
                current_metrics.get(
                    "throughput_req_per_sec"
                ),
            ),
            "p95_ms": calculate_change(
                previous_metrics.get("p95_ms"),
                current_metrics.get("p95_ms"),
            ),
            "p99_ms": calculate_change(
                previous_metrics.get("p99_ms"),
                current_metrics.get("p99_ms"),
            ),
            "error_rate_pct": calculate_change(
                previous_metrics.get(
                    "error_rate_pct"
                ),
                current_metrics.get(
                    "error_rate_pct"
                ),
            ),
            "total_requests": calculate_change(
                previous_metrics.get(
                    "total_requests"
                ),
                current_metrics.get(
                    "total_requests"
                ),
            ),
        },
    }

    return comparison


def print_execution_table(
    executions: list[dict[str, Any]],
) -> None:
    if not executions:
        print("No se encontraron ejecuciones.")
        return

    print(
        f"{'EXECUTION ID':<48} "
        f"{'VERDICT':<8} "
        f"{'THREADS':>7} "
        f"{'RPS':>10} "
        f"{'P95':>10} "
        f"{'ERROR %':>10}"
    )
    print("-" * 105)

    for entry in executions:
        configuration = entry.get("configuration") or {}
        metrics = entry.get("metrics") or {}

        print(
            f"{str(entry.get('execution_id', '')):<48} "
            f"{str(entry.get('verdict', 'N/A')):<8} "
            f"{format_number(configuration.get('threads')):>7} "
            f"{format_number(metrics.get('throughput_req_per_sec')):>10} "
            f"{format_number(metrics.get('p95_ms')):>10} "
            f"{format_number(metrics.get('error_rate_pct')):>10}"
        )


def print_comparison(
    comparison: dict[str, Any],
) -> None:
    print(
        f"Scenario: {comparison['scenario']}"
    )
    print(
        "Previous: "
        f"{comparison['previous_execution_id']} "
        f"({comparison['previous_verdict']})"
    )
    print(
        "Current : "
        f"{comparison['current_execution_id']} "
        f"({comparison['current_verdict']})"
    )
    print()

    labels = {
        "throughput_req_per_sec": "Throughput",
        "p95_ms": "p95",
        "p99_ms": "p99",
        "error_rate_pct": "Error rate",
        "total_requests": "Total requests",
    }

    for metric_name, change in comparison["metrics"].items():
        percentage = change.get("percentage_change")

        percentage_text = (
            f"{percentage:+.2f}%"
            if percentage is not None
            else "N/A"
        )

        print(
            f"{labels[metric_name]:<16}: "
            f"{format_number(change.get('previous'))} -> "
            f"{format_number(change.get('current'))} "
            f"({percentage_text})"
        )


def get_history_path(
    config: ConfigLoader,
    override: str | None,
) -> Path:
    if override:
        return resolve_path(
            override,
            config.project_root,
        )

    configured_path = config.get_path(
        "paths.files.history_index",
        required=True,
    )

    if configured_path is None:
        raise HistoryError(
            "No se pudo resolver paths.files.history_index."
        )

    return configured_path


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Administra el historial de ejecuciones de "
            "Performance Engineering."
        )
    )

    parser.add_argument(
        "--config",
        help="Ruta alternativa a project-config.yaml.",
    )
    parser.add_argument(
        "--history",
        help="Ruta alternativa al archivo history.json.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Muestra la respuesta en formato JSON.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    add_parser = subparsers.add_parser(
        "add",
        help="Registra una ejecución.",
    )
    add_parser.add_argument(
        "--metadata",
        required=True,
        help="Ruta a metadata.json.",
    )
    add_parser.add_argument(
        "--replace",
        action="store_true",
        help="Actualiza la entrada si ya existe.",
    )

    list_parser = subparsers.add_parser(
        "list",
        help="Lista ejecuciones recientes.",
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Número máximo de ejecuciones.",
    )
    list_parser.add_argument(
        "--scenario",
        help="Filtra por nombre exacto del escenario.",
    )

    compare_parser = subparsers.add_parser(
        "compare",
        help="Compara las dos últimas ejecuciones.",
    )
    compare_parser.add_argument(
        "--scenario",
        required=True,
        help="Escenario que será comparado.",
    )

    subparsers.add_parser(
        "init",
        help="Crea el historial vacío si no existe.",
    )

    return parser


def main() -> int:
    parser = create_parser()
    arguments = parser.parse_args()

    try:
        config = load_config(
            config_path=arguments.config,
        )

        history_path = get_history_path(
            config,
            arguments.history,
        )

        if arguments.command == "init":
            if history_path.exists():
                history = load_history(history_path)
                result = {
                    "action": "existing",
                    "history_path": str(history_path),
                    "total_executions": history[
                        "total_executions"
                    ],
                }
            else:
                history = create_empty_history()
                write_json_atomically(
                    history_path,
                    history,
                )
                result = {
                    "action": "created",
                    "history_path": str(history_path),
                    "total_executions": 0,
                }

            if arguments.json_output:
                print(
                    json.dumps(
                        result,
                        indent=2,
                        ensure_ascii=False,
                    )
                )
            else:
                print(
                    "Historial disponible: "
                    f"{history_path}"
                )
                print(
                    "Total executions: "
                    f"{result['total_executions']}"
                )

            return 0

        if arguments.command == "add":
            metadata_path = resolve_path(
                arguments.metadata,
                config.project_root,
            )

            result = register_execution(
                history_path,
                metadata_path,
                replace_existing=arguments.replace,
            )

            if arguments.json_output:
                print(
                    json.dumps(
                        result,
                        indent=2,
                        ensure_ascii=False,
                    )
                )
            else:
                print(
                    "Execution registered: "
                    f"{result['entry']['execution_id']}"
                )
                print(
                    f"Action: {result['action']}"
                )
                print(
                    "History: "
                    f"{result['history_path']}"
                )
                print(
                    "Total executions: "
                    f"{result['total_executions']}"
                )

            return 0

        if arguments.command == "list":
            if arguments.limit <= 0:
                raise HistoryError(
                    "--limit debe ser mayor que cero."
                )

            executions = list_executions(
                history_path,
                limit=arguments.limit,
                scenario=arguments.scenario,
            )

            if arguments.json_output:
                print(
                    json.dumps(
                        executions,
                        indent=2,
                        ensure_ascii=False,
                    )
                )
            else:
                print_execution_table(executions)

            return 0

        if arguments.command == "compare":
            comparison = compare_latest_executions(
                history_path,
                arguments.scenario,
            )

            if arguments.json_output:
                print(
                    json.dumps(
                        comparison,
                        indent=2,
                        ensure_ascii=False,
                    )
                )
            else:
                print_comparison(comparison)

            return 0

        raise HistoryError(
            f"Comando no soportado: {arguments.command}"
        )

    except (ConfigurationError, HistoryError) as exc:
        print(
            f"History error: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())