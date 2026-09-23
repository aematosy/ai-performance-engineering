#!/usr/bin/env python3
"""Orquestador principal de AI-Assisted Performance Engineering.

Códigos de salida:
- 0: ejecución completada y SLA aprobado.
- 1: ejecución completada con incumplimiento de SLA.
- 2: error técnico, de configuración o de evidencias.
- 130: ejecución interrumpida por el usuario.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config_loader import ConfigurationError, ConfigLoader, load_config

PASS = 0
SLA_FAIL = 1
TECHNICAL_FAIL = 2
INTERRUPTED = 130

REQUIRED_JTL_COLUMNS = {
    "timeStamp",
    "elapsed",
    "label",
    "responseCode",
    "success",
}

ERROR_PATTERNS = (
    " ERROR ",
    " FATAL ",
    "CANNOTRESOLVECLASSEXCEPTION",
    "CLASSNOTFOUNDEXCEPTION",
    "OUTOFMEMORYERROR",
    "NOCLASSDEFFOUNDERROR",
)


class PipelineError(RuntimeError):
    """Error controlado del pipeline."""


@dataclass(frozen=True)
class RuntimeContext:
    config: ConfigLoader
    jmeter_command: list[str]
    docker_command: list[str]
    docker_compose_command: list[str]
    validate_environment_script: Path
    analyze_results_script: Path
    generate_report_script: Path
    history_manager_script: Path
    trend_analyzer_script: Path
    intelligence_engine_script: Path
    sla_file: Path
    results_directory: Path
    reports_directory: Path
    docker_compose_file: Path
    prometheus_ready_url: str
    grafana_health_url: str
    prometheus_base_url: str
    grafana_base_url: str
    jmeter_metrics_url: str


@dataclass(frozen=True)
class ExecutionPaths:
    execution_id: str
    result_directory: Path
    report_directory: Path
    jtl: Path
    jmeter_log: Path
    analysis: Path
    metadata: Path
    trend: Path
    intelligence: Path
    intelligence_report: Path
    executive_report: Path
    jmeter_dashboard_directory: Path


def print_header(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def split_command(value: str, key: str) -> list[str]:
    try:
        parts = shlex.split(value)
    except ValueError as exc:
        raise PipelineError(f"Comando inválido en {key}: {exc}") from exc

    if not parts:
        raise PipelineError(f"Comando vacío en {key}.")

    return parts


def format_command(command: Sequence[str]) -> str:
    return shlex.join(str(value) for value in command)


def build_url(base_url: str, endpoint: str) -> str:
    return base_url.rstrip("/") + "/" + endpoint.lstrip("/")


def require_script(config: ConfigLoader, name: str) -> Path:
    path = config.get_script_path(name, required=True)

    if path is None:
        raise PipelineError(f"No se pudo resolver el script: {name}")

    return path


def require_path(
    config: ConfigLoader,
    key: str,
    *,
    file: bool = False,
    create_directory: bool = False,
) -> Path:
    path = config.get_path(
        key,
        required=True,
        create=create_directory,
        directory=create_directory,
    )

    if path is None:
        raise PipelineError(f"No se pudo resolver la ruta: {key}")

    if file and not path.is_file():
        raise PipelineError(f"No existe el archivo configurado {key}: {path}")

    return path


def build_context(config: ConfigLoader) -> RuntimeContext:
    jmeter_value = config.get_command("jmeter_command", required=True)

    jmeter_command = split_command(
        jmeter_value,
        "runtime.jmeter_command",
    )

    runtime_properties_value = os.getenv(
        "PERF_JMETER_PROPERTIES_FILE",
        "",
    ).strip()

    if runtime_properties_value:
        runtime_properties = (
            Path(runtime_properties_value)
            .expanduser()
            .resolve()
        )

        if not runtime_properties.is_file():
            raise PipelineError(
                "JMeter runtime properties file "
                "does not exist: "
                f"{runtime_properties}"
            )

        jmeter_command.extend(
            [
                "-q",
                str(runtime_properties),
            ]
        )

        print(
            "JMeter runtime properties : CONFIGURED"
        )
        print(
            f"Properties file           : {runtime_properties}"
        )

    docker_value = config.get_command("docker_command", required=True)
    compose_value = config.get_command("docker_compose_command", required=True)

    if not jmeter_value or not docker_value or not compose_value:
        raise PipelineError("La configuración de comandos está incompleta.")

    prometheus = str(
        config.get("observability.prometheus.base_url", required=True)
    )
    grafana = str(
        config.get("observability.grafana.base_url", required=True)
    )
    metrics_host = str(
        config.get("observability.jmeter_metrics.host", default="localhost")
    )
    metrics_port = int(
        config.get("observability.jmeter_metrics.port", default=9270)
    )
    metrics_endpoint = str(
        config.get("observability.jmeter_metrics.endpoint", default="/metrics")
    )

    return RuntimeContext(
        config=config,
        jmeter_command=jmeter_command,
        docker_command=split_command(
            docker_value,
            "runtime.docker_command",
        ),
        docker_compose_command=split_command(
            compose_value,
            "runtime.docker_compose_command",
        ),
        validate_environment_script=require_script(
            config,
            "validate_environment",
        ),
        analyze_results_script=require_script(
            config,
            "analyze_results",
        ),
        generate_report_script=require_script(
            config,
            "generate_report",
        ),
        history_manager_script=require_script(
            config,
            "history_manager",
        ),
        trend_analyzer_script=require_script(
            config,
            "trend_analyzer",
        ),
        intelligence_engine_script=require_script(
            config,
            "intelligence_engine",
        ),
        sla_file=require_path(
            config,
            "paths.files.sla",
            file=True,
        ),
        results_directory=require_path(
            config,
            "paths.results_directory",
            create_directory=True,
        ),
        reports_directory=require_path(
            config,
            "paths.reports_directory",
            create_directory=True,
        ),
        docker_compose_file=require_path(
            config,
            "paths.files.docker_compose",
            file=True,
        ),
        prometheus_ready_url=build_url(
            prometheus,
            str(
                config.get(
                    "observability.prometheus.readiness_endpoint",
                    default="/-/ready",
                )
            ),
        ),
        grafana_health_url=build_url(
            grafana,
            str(
                config.get(
                    "observability.grafana.health_endpoint",
                    default="/api/health",
                )
            ),
        ),
        prometheus_base_url=prometheus,
        grafana_base_url=grafana,
        jmeter_metrics_url=(
            f"http://{metrics_host}:{metrics_port}/"
            f"{metrics_endpoint.lstrip('/')}"
        ),
    )


def run_command(
    command: Sequence[str],
    description: str,
    *,
    cwd: Path,
    allow_failure: bool = False,
    timeout_seconds: int | None = None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    print_header(description)
    print(f"$ {format_command(command)}")

    try:
        result = subprocess.run(
            [str(value) for value in command],
            cwd=str(cwd),
            text=True,
            capture_output=capture_output,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise PipelineError(
            f"{description} excedió {timeout_seconds} segundos."
        ) from exc
    except OSError as exc:
        raise PipelineError(
            f"No se pudo ejecutar '{command[0]}': {exc}"
        ) from exc

    if capture_output:
        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)

    if result.returncode != 0 and not allow_failure:
        raise PipelineError(
            f"{description} terminó con código {result.returncode}."
        )

    return result


def check_executable(command: Sequence[str], description: str) -> None:
    if shutil.which(command[0]) is None:
        raise PipelineError(
            f"No se encontró '{command[0]}' en PATH para {description}."
        )


def check_file(path: Path, description: str) -> None:
    if not path.is_file():
        raise PipelineError(f"No existe {description}: {path}")

    if path.stat().st_size == 0:
        raise PipelineError(f"{description} está vacío: {path}")


def wait_for_url(
    url: str,
    description: str,
    timeout_seconds: int,
) -> None:
    print(f"\nEsperando {description}...")
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        request = Request(
            url,
            headers={"User-Agent": "ai-performance-platform/1.0"},
        )

        try:
            with urlopen(request, timeout=5) as response:
                if 200 <= response.getcode() < 400:
                    print(f"[OK] {description} disponible: {url}")
                    return
        except (HTTPError, URLError, OSError) as exc:
            last_error = exc

        time.sleep(2)

    raise PipelineError(
        f"{description} no estuvo disponible después de "
        f"{timeout_seconds}s. Último error: {last_error}"
    )


def validate_jmx(path: Path) -> None:
    check_file(path, "el archivo JMX")

    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise PipelineError(f"JMX inválido: {exc}") from exc

    if root.tag != "jmeterTestPlan":
        raise PipelineError("El XML no tiene como raíz 'jmeterTestPlan'.")

    print(f"[OK] JMX válido: {path}")


def validate_jtl(path: Path) -> None:
    check_file(path, "el archivo JTL")

    try:
        with path.open(
            newline="",
            encoding="utf-8-sig",
            errors="replace",
        ) as file:
            reader = csv.reader(file)
            header = next(reader, None)
            sample = next(reader, None)
    except OSError as exc:
        raise PipelineError(f"No se pudo leer el JTL: {exc}") from exc

    if not header:
        raise PipelineError("El JTL no contiene cabecera CSV.")

    missing = REQUIRED_JTL_COLUMNS.difference(header)

    if missing:
        raise PipelineError(
            "El JTL no contiene las columnas requeridas: "
            + ", ".join(sorted(missing))
        )

    if sample is None:
        raise PipelineError("El JTL no contiene muestras.")

    print(f"[OK] JTL válido: {path}")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", value.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-._")
    return slug or "performance-test"


def create_paths(
    scenario: str,
    results_base: Path,
    reports_base: Path,
    timestamp_format: str,
) -> ExecutionPaths:
    execution_id = (
        f"{datetime.now().strftime(timestamp_format)}_{slugify(scenario)}"
    )
    result_directory = results_base / execution_id
    report_directory = reports_base / execution_id

    if result_directory.exists() or report_directory.exists():
        execution_id += f"_{time.time_ns() % 1_000_000:06d}"
        result_directory = results_base / execution_id
        report_directory = reports_base / execution_id

    try:
        result_directory.mkdir(parents=True, exist_ok=False)
        report_directory.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise PipelineError(
            f"No se pudieron crear los directorios de ejecución: {exc}"
        ) from exc

    return ExecutionPaths(
        execution_id=execution_id,
        result_directory=result_directory,
        report_directory=report_directory,
        jtl=result_directory / "results.jtl",
        jmeter_log=result_directory / "jmeter.log",
        analysis=result_directory / "analysis.json",
        metadata=result_directory / "metadata.json",
        trend=result_directory / "trend.json",
        intelligence=result_directory / "intelligence.json",
        intelligence_report=report_directory / "intelligence-report.md",
        executive_report=report_directory / "executive-report.html",
        jmeter_dashboard_directory=report_directory / "jmeter",
    )


def compose_command(context: RuntimeContext, *args: str) -> list[str]:
    return [
        *context.docker_compose_command,
        "-f",
        str(context.docker_compose_file),
        *args,
    ]


def start_observability(
    context: RuntimeContext,
    timeout: int,
) -> None:
    root = context.config.project_root

    run_command(
        compose_command(context, "config"),
        "Validando Docker Compose",
        cwd=root,
        timeout_seconds=60,
    )
    run_command(
        compose_command(context, "up", "-d"),
        "Levantando Prometheus y Grafana",
        cwd=root,
        timeout_seconds=180,
    )
    run_command(
        compose_command(context, "ps"),
        "Estado de los contenedores",
        cwd=root,
        timeout_seconds=60,
    )
    wait_for_url(
        context.prometheus_ready_url,
        "Prometheus",
        timeout,
    )
    wait_for_url(
        context.grafana_health_url,
        "Grafana",
        timeout,
    )


def inspect_log(path: Path, max_errors: int = 100) -> list[str]:
    if not path.exists():
        return ["JMeter no generó jmeter.log."]

    errors: list[str] = []

    try:
        with path.open(encoding="utf-8", errors="replace") as file:
            for line in file:
                upper = line.upper()

                if any(pattern in upper for pattern in ERROR_PATTERNS):
                    errors.append(line.rstrip())

                    if len(errors) >= max_errors:
                        errors.append(
                            f"Se alcanzó el límite de {max_errors} errores."
                        )
                        break
    except OSError as exc:
        return [f"No se pudo leer jmeter.log: {exc}"]

    return errors


def load_json(path: Path, description: str) -> dict[str, Any]:
    check_file(path, description)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineError(
            f"No se pudo leer {description}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise PipelineError(f"{description} debe contener un objeto JSON.")

    return data


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.stem}-",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary = Path(file.name)
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())

        temporary.replace(path)
    except OSError as exc:
        raise PipelineError(
            f"No se pudo escribir metadata.json: {exc}"
        ) from exc
    finally:
        if temporary and temporary.exists():
            temporary.unlink(missing_ok=True)


def register_execution_history(
    context: RuntimeContext,
    metadata_path: Path,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(context.history_manager_script),
        "--config",
        str(context.config.config_path),
        "add",
        "--metadata",
        str(metadata_path),
    ]

    return run_command(
        command,
        "Registrando ejecución en el historial",
        cwd=context.config.project_root,
        timeout_seconds=timeout_seconds,
    )


def compare_execution_history(
    context: RuntimeContext,
    *,
    scenario: str,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(context.history_manager_script),
        "--config",
        str(context.config.config_path),
        "compare",
        "--scenario",
        scenario,
    ]

    return run_command(
        command,
        "Comparando con la ejecución anterior",
        cwd=context.config.project_root,
        allow_failure=True,
        timeout_seconds=timeout_seconds,
    )


def generate_execution_trend(
    context: RuntimeContext,
    *,
    scenario: str,
    output_path: Path,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(context.trend_analyzer_script),
        "--config",
        str(context.config.config_path),
        "--scenario",
        scenario,
        "--output",
        str(output_path),
    ]

    return run_command(
        command,
        "Calculando tendencia de rendimiento",
        cwd=context.config.project_root,
        allow_failure=True,
        timeout_seconds=timeout_seconds,
    )


def generate_execution_intelligence(
    context: RuntimeContext,
    *,
    analysis_path: Path,
    metadata_path: Path,
    trend_path: Path | None,
    output_path: Path,
    markdown_output_path: Path,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(context.intelligence_engine_script),
        "--config",
        str(context.config.config_path),
        "--analysis",
        str(analysis_path),
        "--metadata",
        str(metadata_path),
        "--output",
        str(output_path),
        "--markdown-output",
        str(markdown_output_path),
    ]

    if trend_path is not None and trend_path.is_file():
        command.extend(["--trend", str(trend_path)])

    return run_command(
        command,
        "Generando inteligencia de rendimiento",
        cwd=context.config.project_root,
        allow_failure=True,
        timeout_seconds=timeout_seconds,
    )


def preliminary_config() -> str | None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config")
    args, _ = parser.parse_known_args()
    return args.config


def parse_arguments(context: RuntimeContext) -> argparse.Namespace:
    config = context.config
    threads = int(config.get("execution.defaults.threads", default=10))
    ramp = int(
        config.get("execution.defaults.ramp_time_seconds", default=10)
    )
    duration = int(
        config.get("execution.defaults.duration_seconds", default=60)
    )
    port = int(
        config.get("observability.jmeter_metrics.port", default=9270)
    )
    environment = str(
        config.get("execution.defaults.environment", default="demo")
    )

    parser = argparse.ArgumentParser(
        description="Ejecuta el pipeline completo de Performance Engineering."
    )
    parser.add_argument("--config")
    parser.add_argument("--jmx", required=True, type=Path)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--environment", default=environment)
    parser.add_argument("--threads", type=int, default=threads)
    parser.add_argument("--ramp-time", type=int, default=ramp)
    parser.add_argument("--duration", type=int, default=duration)
    parser.add_argument("--prometheus-port", type=int, default=port)
    parser.add_argument("--sla", type=Path, default=context.sla_file)
    parser.add_argument(
        "--properties",
        type=Path,
        help=(
            "Optional JMeter properties file loaded with -q. "
            "The file content is never printed by this runner."
        ),
    )
    parser.add_argument(
        "--results-directory",
        type=Path,
        default=context.results_directory,
    )
    parser.add_argument(
        "--reports-directory",
        type=Path,
        default=context.reports_directory,
    )
    parser.add_argument("--authorized", action="store_true")
    parser.add_argument(
        "--skip-environment-validation",
        action="store_true",
    )
    parser.add_argument("--skip-observability", action="store_true")
    parser.add_argument(
        "--skip-history",
        action="store_true",
        help="No registra ni compara la ejecución en el historial.",
    )
    parser.add_argument(
        "--skip-trend",
        action="store_true",
        help=(
            "No calcula trend.json. Este parámetro también se aplica "
            "automáticamente cuando se usa --skip-history."
        ),
    )
    parser.add_argument(
        "--skip-intelligence",
        action="store_true",
        help=(
            "No genera intelligence.json ni intelligence-report.md. "
            "Puede usarse de forma independiente de --skip-history."
        ),
    )
    parser.add_argument("--observability-timeout", type=int, default=60)
    parser.add_argument("--command-timeout", type=int, default=300)
    parser.add_argument(
        "--jmeter-timeout-buffer",
        type=int,
        default=None,
        help=(
            "Optional explicit JMeter shutdown timeout buffer. "
            "When omitted, the value is calculated from the "
            "configured execution.timeouts.jmeter policy."
        ),
    )
    return parser.parse_args()


def resolve_path(path: Path, root: Path) -> Path:
    expanded = path.expanduser()
    return (
        (root / expanded).resolve()
        if not expanded.is_absolute()
        else expanded.resolve()
    )


def prepare_directory(
    path: Path,
    root: Path,
    description: str,
) -> Path:
    resolved = resolve_path(path, root)

    try:
        resolved.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PipelineError(
            f"No se pudo preparar {description}: {exc}"
        ) from exc

    if not resolved.is_dir():
        raise PipelineError(f"{description} no es un directorio: {resolved}")

    return resolved


def calculate_jmeter_timeout(
    context: RuntimeContext,
    args: argparse.Namespace,
) -> tuple[int, int, str]:
    """Calculate the maximum JMeter process lifetime.

    Workload values come from the approved execution.
    Timeout policy values come exclusively from project configuration.

    An explicit --jmeter-timeout-buffer remains supported as
    an operational override and takes precedence over the
    configured dynamic policy.
    """

    if args.jmeter_timeout_buffer is not None:
        buffer_seconds = int(
            args.jmeter_timeout_buffer
        )
        source = "CLI_OVERRIDE"
    else:
        config = context.config

        minimum_buffer = int(
            config.get(
                "execution.timeouts.jmeter."
                "minimum_buffer_seconds",
                required=True,
            )
        )

        duration_ratio = float(
            config.get(
                "execution.timeouts.jmeter."
                "duration_buffer_ratio",
                required=True,
            )
        )

        ramp_ratio = float(
            config.get(
                "execution.timeouts.jmeter."
                "ramp_buffer_ratio",
                required=True,
            )
        )

        if minimum_buffer < 0:
            raise PipelineError(
                "execution.timeouts.jmeter."
                "minimum_buffer_seconds cannot be negative."
            )

        if duration_ratio < 0:
            raise PipelineError(
                "execution.timeouts.jmeter."
                "duration_buffer_ratio cannot be negative."
            )

        if ramp_ratio < 0:
            raise PipelineError(
                "execution.timeouts.jmeter."
                "ramp_buffer_ratio cannot be negative."
            )

        duration_buffer = int(
            round(
                args.duration
                * duration_ratio
            )
        )

        ramp_buffer = int(
            round(
                args.ramp_time
                * ramp_ratio
            )
        )

        buffer_seconds = max(
            minimum_buffer,
            duration_buffer,
            ramp_buffer,
        )

        source = "CONFIG_DYNAMIC_POLICY"

    timeout_seconds = (
        int(args.ramp_time)
        + int(args.duration)
        + buffer_seconds
    )

    if timeout_seconds <= 0:
        raise PipelineError(
            "Calculated JMeter timeout must be greater than zero."
        )

    return (
        timeout_seconds,
        buffer_seconds,
        source,
    )


def validate_arguments(
    context: RuntimeContext,
    args: argparse.Namespace,
) -> None:
    if args.threads <= 0:
        raise PipelineError("--threads debe ser mayor que cero.")

    if args.ramp_time < 0:
        raise PipelineError("--ramp-time no puede ser negativo.")

    if args.duration <= 0:
        raise PipelineError("--duration debe ser mayor que cero.")

    if not 1 <= args.prometheus_port <= 65535:
        raise PipelineError(
            "--prometheus-port debe estar entre 1 y 65535."
        )

    if min(args.observability_timeout, args.command_timeout) <= 0:
        raise PipelineError("Los timeouts deben ser mayores que cero.")

    if (
        args.jmeter_timeout_buffer is not None
        and args.jmeter_timeout_buffer < 0
    ):
        raise PipelineError(
            "--jmeter-timeout-buffer no puede ser negativo."
        )

    if not args.scenario.strip():
        raise PipelineError("--scenario no puede estar vacío.")

    if not args.target.strip():
        raise PipelineError("--target no puede estar vacío.")

    if not args.environment.strip():
        raise PipelineError("--environment no puede estar vacío.")

    require_authorization = bool(
        context.config.get(
            "execution.require_authorization",
            default=True,
        )
    )

    if require_authorization and not args.authorized:
        raise PipelineError(
            "Debes confirmar la autorización agregando --authorized."
        )

    protected = {
        str(value).strip().lower()
        for value in context.config.get(
            "security.protected_environments",
            default=[],
        )
        if str(value).strip()
    }

    if (
        args.environment.strip().lower() in protected
        and not bool(
            context.config.get(
                "security.allow_production_by_default",
                default=False,
            )
        )
    ):
        raise PipelineError(
            f"El ambiente '{args.environment}' está protegido y "
            "producción está deshabilitada por defecto."
        )

    max_users = int(
        context.config.get(
            "execution.parameters.users.maximum_without_confirmation",
            default=100,
        )
    )

    if args.threads > max_users:
        raise PipelineError(
            f"La carga de {args.threads} usuarios supera el máximo "
            f"configurado ({max_users})."
        )


def print_summary(
    context: RuntimeContext,
    paths: ExecutionPaths,
    analysis: dict[str, Any],
    errors: list[str],
    history_registered: bool,
    comparison_performed: bool,
    trend: dict[str, Any] | None,
    trend_status: str,
    intelligence: dict[str, Any] | None,
    intelligence_status: str,
) -> None:
    metrics = analysis.get("metrics") or {}
    response = metrics.get("response_time_ms") or {}

    print_header("RESUMEN DE LA EJECUCIÓN")
    print(f"Execution ID : {paths.execution_id}")
    print(f"Veredicto    : {analysis.get('verdict', 'UNKNOWN')}")
    print(f"Requests     : {metrics.get('total_requests', 'N/A')}")
    print(f"Success rate : {metrics.get('success_rate_pct', 'N/A')}%")
    print(f"Error rate   : {metrics.get('error_rate_pct', 'N/A')}%")
    print(
        "Throughput   : "
        f"{metrics.get('throughput_req_per_sec', 'N/A')} req/s"
    )
    print(f"p95          : {response.get('p95', 'N/A')} ms")
    print(f"p99          : {response.get('p99', 'N/A')} ms")
    print("Errores técnicos: ninguno" if not errors else "Errores técnicos:")

    for error in errors:
        print(f"- {error}")

    if history_registered:
        print("Historial     : registrado")
        print(
            "Comparación   : "
            + ("disponible" if comparison_performed else "sin historial suficiente")
        )
    else:
        print("Historial     : omitido")
        print("Comparación   : omitida")

    if trend:
        print(f"Tendencia     : {trend.get('classification', 'UNKNOWN')}")
        print(f"Trend score   : {trend.get('score', 'N/A')}")
        print(f"Trend summary : {trend.get('summary', 'N/A')}")
    else:
        print(f"Tendencia     : {trend_status}")

    if intelligence:
        risk = intelligence.get("risk") or {}
        decision = intelligence.get("decision") or {}
        print(f"Inteligencia  : AVAILABLE")
        print(
            "Riesgo        : "
            f"{risk.get('level', 'UNKNOWN')} "
            f"({risk.get('score', 'N/A')}/100)"
        )
        print(f"Decisión      : {decision.get('status', 'UNKNOWN')}")
        print(
            "AI summary    : "
            f"{intelligence.get('executive_summary', 'N/A')}"
        )
    else:
        print(f"Inteligencia  : {intelligence_status}")

    print(f"\nJTL              : {paths.jtl}")
    print(f"JMeter log       : {paths.jmeter_log}")
    print(f"Analysis JSON    : {paths.analysis}")
    print(f"Metadata         : {paths.metadata}")
    print(f"Trend JSON       : {paths.trend if paths.trend.exists() else 'no generado'}")
    print(
        "Intelligence JSON: "
        f"{paths.intelligence if paths.intelligence.exists() else 'no generado'}"
    )
    print(
        "Reporte inteligencia: "
        f"{paths.intelligence_report if paths.intelligence_report.exists() else 'no generado'}"
    )
    print(f"Reporte ejecutivo: {paths.executive_report}")
    print(
        "Reporte JMeter   : "
        f"{paths.jmeter_dashboard_directory / 'index.html'}"
    )
    print(f"\nPrometheus: {context.prometheus_base_url}")
    print(f"Grafana   : {context.grafana_base_url}")
    print(f"Metrics   : {context.jmeter_metrics_url}")


def main() -> int:
    try:
        config = load_config(config_path=preliminary_config())
        context = build_context(config)
        args = parse_arguments(context)
        validate_arguments(context, args)

        root = config.project_root
        jmx = resolve_path(args.jmx, root)
        sla = resolve_path(args.sla, root)
        properties_file = (
            resolve_path(args.properties, root)
            if args.properties is not None
            else None
        )
        results = prepare_directory(args.results_directory, root, "results")
        reports = prepare_directory(args.reports_directory, root, "reports")

        check_executable(context.jmeter_command, "Apache JMeter")

        if not args.skip_observability:
            check_executable(context.docker_command, "Docker")
            check_executable(
                context.docker_compose_command,
                "Docker Compose",
            )

        validate_jmx(jmx)
        check_file(sla, "el archivo SLA")

        if properties_file is not None:
            check_file(
                properties_file,
                "el archivo de propiedades JMeter",
            )
        check_file(
            context.validate_environment_script,
            "validate_environment.py",
        )
        check_file(
            context.analyze_results_script,
            "analyze_results.py",
        )
        check_file(
            context.generate_report_script,
            "generate_report.py",
        )
        if not args.skip_history:
            check_file(
                context.history_manager_script,
                "history_manager.py",
            )

            if not args.skip_trend:
                check_file(
                    context.trend_analyzer_script,
                    "trend_analyzer.py",
                )

        if not args.skip_intelligence:
            check_file(
                context.intelligence_engine_script,
                "intelligence_engine.py",
            )

        if not args.skip_environment_validation:
            run_command(
                [
                    sys.executable,
                    str(context.validate_environment_script),
                    "--config",
                    str(config.config_path),
                ],
                "Validando ambiente",
                cwd=root,
                timeout_seconds=180,
            )

        if not args.skip_observability:
            start_observability(
                context,
                args.observability_timeout,
            )

        timestamp_format = str(
            config.get(
                "naming.execution_timestamp_format",
                default="%Y%m%d_%H%M%S",
            )
        )

        paths = create_paths(
            args.scenario,
            results,
            reports,
            timestamp_format,
        )

        jmeter_command = [
            *context.jmeter_command,
        ]

        if properties_file is not None:
            jmeter_command.extend(
                [
                    "-q",
                    str(properties_file),
                ]
            )

        jmeter_command.extend(
            [
                "-n",
                "-t",
                str(jmx),
                "-l",
                str(paths.jtl),
                "-j",
                str(paths.jmeter_log),
                f"-Jthreads={args.threads}",
                f"-Jramp_time={args.ramp_time}",
                f"-Jduration={args.duration}",
                f"-Jprometheus_port={args.prometheus_port}",
            ]
        )

        (
            jmeter_timeout_seconds,
            jmeter_timeout_buffer,
            jmeter_timeout_source,
        ) = calculate_jmeter_timeout(
            context,
            args,
        )

        print()
        print("=" * 78)
        print("JMETER EXECUTION TIMEOUT POLICY")
        print("=" * 78)
        print(
            f"Ramp-up           : "
            f"{args.ramp_time} s"
        )
        print(
            f"Duration          : "
            f"{args.duration} s"
        )
        print(
            f"Shutdown buffer   : "
            f"{jmeter_timeout_buffer} s"
        )
        print(
            f"Maximum runtime   : "
            f"{jmeter_timeout_seconds} s"
        )
        print(
            f"Policy source     : "
            f"{jmeter_timeout_source}"
        )
        print("=" * 78)

        jmeter_result = run_command(
            jmeter_command,
            "Ejecutando prueba JMeter",
            cwd=root,
            allow_failure=True,
            timeout_seconds=(
                jmeter_timeout_seconds
            ),
        )

        validate_jtl(paths.jtl)
        technical_errors = inspect_log(paths.jmeter_log)

        analysis_result = run_command(
            [
                sys.executable,
                str(context.analyze_results_script),
                "--input",
                str(paths.jtl),
                "--sla",
                str(sla),
                "--output",
                str(paths.analysis),
            ],
            "Analizando resultados y evaluando SLA",
            cwd=root,
            allow_failure=True,
            timeout_seconds=args.command_timeout,
        )

        analysis = load_json(paths.analysis, "analysis.json")

        run_command(
            [
                sys.executable,
                str(context.generate_report_script),
                "--analysis",
                str(paths.analysis),
                "--jtl",
                str(paths.jtl),
                "--output",
                str(paths.executive_report),
                "--scenario",
                args.scenario,
                "--target",
                args.target,
            ],
            "Generando reporte ejecutivo HTML",
            cwd=root,
            timeout_seconds=args.command_timeout,
        )

        run_command(
            [
                *context.jmeter_command,
                "-g",
                str(paths.jtl),
                "-o",
                str(paths.jmeter_dashboard_directory),
            ],
            "Generando dashboard oficial de JMeter",
            cwd=root,
            timeout_seconds=args.command_timeout,
        )

        metadata = {
            "schema_version": "1.0",
            "execution_id": paths.execution_id,
            "generated_at": datetime.now().astimezone().isoformat(),
            "project": {
                "name": config.get("project.name"),
                "config_file": str(config.config_path),
            },
            "scenario": args.scenario,
            "target": args.target,
            "environment": args.environment,
            "authorized": args.authorized,
            "test_configuration": {
                "threads": args.threads,
                "ramp_time_seconds": args.ramp_time,
                "duration_seconds": args.duration,
                "prometheus_port": args.prometheus_port,
            },
            "files": {
                "jmx": str(jmx),
                "sla": str(sla),
                "properties_file": (
                    str(properties_file)
                    if properties_file is not None
                    else None
                ),
                "result_directory": str(paths.result_directory),
                "report_directory": str(paths.report_directory),
                "jtl": str(paths.jtl),
                "jmeter_log": str(paths.jmeter_log),
                "analysis": str(paths.analysis),
                "trend": str(paths.trend),
                "intelligence": str(paths.intelligence),
                "intelligence_report": str(paths.intelligence_report),
                "executive_report": str(paths.executive_report),
                "jmeter_dashboard": str(
                    paths.jmeter_dashboard_directory / "index.html"
                ),
            },
            "observability": {
                "prometheus": context.prometheus_base_url,
                "grafana": context.grafana_base_url,
                "jmeter_metrics": context.jmeter_metrics_url,
                "skipped": args.skip_observability,
            },
            "exit_codes": {
                "jmeter": jmeter_result.returncode,
                "analysis": analysis_result.returncode,
            },
            "technical_errors": technical_errors,
            "verdict": analysis.get("verdict"),
            "metrics": analysis.get("metrics"),
            "sla_checks": analysis.get("sla_checks"),
            "history": {
                "requested": not args.skip_history,
                "registered": False,
                "comparison_performed": False,
            },
            "trend": {
                "requested": (
                    not args.skip_history and not args.skip_trend
                ),
                "generated": False,
                "status": "PENDING",
                "classification": None,
                "score": None,
                "summary": None,
            },
            "intelligence": {
                "requested": not args.skip_intelligence,
                "generated": False,
                "status": "PENDING",
                "risk_level": None,
                "risk_score": None,
                "decision": None,
                "executive_summary": None,
            },
        }

        write_json_atomic(paths.metadata, metadata)

        history_registered = False
        comparison_performed = False
        trend: dict[str, Any] | None = None
        trend_status = "OMITTED"
        intelligence: dict[str, Any] | None = None
        intelligence_status = "OMITTED"

        if not args.skip_history:
            register_execution_history(
                context,
                paths.metadata,
                args.command_timeout,
            )
            history_registered = True

            comparison_result = compare_execution_history(
                context,
                scenario=args.scenario,
                timeout_seconds=args.command_timeout,
            )
            comparison_performed = comparison_result.returncode == 0

            if not args.skip_trend:
                trend_result = generate_execution_trend(
                    context,
                    scenario=args.scenario,
                    output_path=paths.trend,
                    timeout_seconds=args.command_timeout,
                )

                if trend_result.returncode == 0 and paths.trend.is_file():
                    trend = load_json(paths.trend, "trend.json")
                    trend_status = "AVAILABLE"
                elif trend_result.returncode == 1:
                    trend_status = "INSUFFICIENT_DATA"
                else:
                    trend_status = "ERROR"
            else:
                trend_status = "SKIPPED"
        else:
            trend_status = "SKIPPED_WITH_HISTORY"

        metadata["history"]["registered"] = history_registered
        metadata["history"]["comparison_performed"] = comparison_performed
        metadata["trend"]["generated"] = trend is not None
        metadata["trend"]["status"] = trend_status

        if trend:
            metadata["trend"]["classification"] = trend.get(
                "classification"
            )
            metadata["trend"]["score"] = trend.get("score")
            metadata["trend"]["summary"] = trend.get("summary")

        write_json_atomic(paths.metadata, metadata)

        if not args.skip_intelligence:
            intelligence_result = generate_execution_intelligence(
                context,
                analysis_path=paths.analysis,
                metadata_path=paths.metadata,
                trend_path=paths.trend if trend is not None else None,
                output_path=paths.intelligence,
                markdown_output_path=paths.intelligence_report,
                timeout_seconds=args.command_timeout,
            )

            if (
                intelligence_result.returncode == 0
                and paths.intelligence.is_file()
            ):
                intelligence = load_json(
                    paths.intelligence,
                    "intelligence.json",
                )
                intelligence_status = "AVAILABLE"
            else:
                intelligence_status = "ERROR"
        else:
            intelligence_status = "SKIPPED"

        metadata["intelligence"]["generated"] = intelligence is not None
        metadata["intelligence"]["status"] = intelligence_status

        if intelligence:
            risk = intelligence.get("risk") or {}
            decision = intelligence.get("decision") or {}
            metadata["intelligence"]["risk_level"] = risk.get("level")
            metadata["intelligence"]["risk_score"] = risk.get("score")
            metadata["intelligence"]["decision"] = decision.get("status")
            metadata["intelligence"]["executive_summary"] = (
                intelligence.get("executive_summary")
            )

        write_json_atomic(paths.metadata, metadata)

        print_summary(
            context,
            paths,
            analysis,
            technical_errors,
            history_registered,
            comparison_performed,
            trend,
            trend_status,
            intelligence,
            intelligence_status,
        )

        if technical_errors or jmeter_result.returncode != 0:
            print("Resultado final: FAIL por error técnico.")
            return TECHNICAL_FAIL

        if analysis_result.returncode not in (0, 1):
            print("Resultado final: FAIL por error del analizador.")
            return TECHNICAL_FAIL

        verdict = str(analysis.get("verdict", "")).upper()

        if verdict == "PASS":
            print("Resultado final: PASS")
            return PASS

        if verdict == "FAIL":
            print("Resultado final: FAIL por incumplimiento de SLA.")
            return SLA_FAIL

        raise PipelineError(
            "analysis.json no contiene un veredicto válido."
        )

    except (ConfigurationError, PipelineError, ValueError) as exc:
        print(f"\nERROR DEL PIPELINE: {exc}", file=sys.stderr)
        return TECHNICAL_FAIL
    except KeyboardInterrupt:
        print("\nEjecución interrumpida por el usuario.")
        return INTERRUPTED


if __name__ == "__main__":
    raise SystemExit(main())