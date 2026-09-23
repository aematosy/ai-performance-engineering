#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import shlex
import shutil
import subprocess
import sys
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from config_loader import ConfigurationError, ConfigLoader, load_config


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    command: list[str]
    required: bool = True
    version_pattern: str | None = None

@dataclass(frozen=True)
class ValidationResult:
    name: str
    status: str
    required: bool
    details: str
    command: str | None = None

    @property
    def passed(self) -> bool:
        return self.status == "OK"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Valida las herramientas, dependencias y configuraciones "
            "requeridas por la plataforma."
        )
    )

    parser.add_argument(
        "--config",
        help=(
            "Ruta alternativa al archivo de configuración. "
            "Por defecto se usa config/project-config.yaml."
        ),
    )

    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Muestra el resultado en formato JSON.",
    )

    parser.add_argument(
        "--skip-optional",
        action="store_true",
        help="Omite las herramientas opcionales.",
    )

    return parser.parse_args()


def split_command(command: str) -> list[str]:
    parts = shlex.split(command)

    if not parts:
        raise ValueError("El comando configurado está vacío.")

    return parts


def build_tool_definitions(config: ConfigLoader) -> list[ToolDefinition]:
    python_command = config.get_command("python_command", required=True)
    jmeter_command = config.get_command("jmeter_command", required=True)
    docker_command = config.get_command("docker_command", required=True)
    docker_compose_command = config.get_command(
        "docker_compose_command",
        required=True,
    )
    axet_command = config.get_command("axet_command", required=False)

    assert python_command is not None
    assert jmeter_command is not None
    assert docker_command is not None
    assert docker_compose_command is not None

    tools = [
        ToolDefinition(
            name="Python",
            command=[*split_command(python_command), "--version"],
        ),
        ToolDefinition(
            name="Java",
            command=["java", "-version"],
        ),
        ToolDefinition(
            name="JMeter",
            command=[*split_command(jmeter_command), "--version"],
            version_pattern=r"\b(\d+\.\d+(?:\.\d+)?)\s*$",
        ),
        ToolDefinition(
            name="Docker",
            command=[*split_command(docker_command), "--version"],
        ),
        ToolDefinition(
            name="Docker Compose",
            command=[*split_command(docker_compose_command), "version"],
        ),
        ToolDefinition(
            name="Google Cloud CLI",
            command=["gcloud", "--version"],
            required=False,
        ),
        ToolDefinition(
            name="Poetry",
            command=["poetry", "--version"],
            required=True,
        ),
    ]

    if axet_command:
        tools.append(
            ToolDefinition(
                name="aXet Code",
                command=[*split_command(axet_command), "--version"],
                required=False,
            )
        )

    return tools


def command_display(command: Sequence[str]) -> str:
    return shlex.join(command)


def extract_version_output(
    stdout: str,
    stderr: str,
    return_code: int,
    version_pattern: str | None = None,
) -> str:
    ignored_prefixes = (
        "WARN ",
        "WARNING:",
        "INFO ",
        "DEBUG ",
        "TRACE ",
    )

    output_lines: list[str] = []

    for content in (stdout, stderr):
        for line in content.splitlines():
            stripped = line.strip()

            if not stripped:
                continue

            if stripped.startswith(ignored_prefixes):
                continue

            output_lines.append(stripped)

    if version_pattern:
        compiled_pattern = re.compile(version_pattern)

        for line in reversed(output_lines):
            match = compiled_pattern.search(line)

            if match:
                version = match.group(1)
                return f"Apache JMeter {version}"

    preferred_patterns = (
        "Python ",
        "openjdk version",
        "Docker version",
        "Docker Compose version",
        "Google Cloud SDK",
        "Poetry ",
    )

    for pattern in preferred_patterns:
        for line in output_lines:
            if pattern.lower() in line.lower():
                return line

    if output_lines:
        return output_lines[0]

    if return_code == 0:
        return "Comando ejecutado correctamente sin salida relevante."

    return f"El comando terminó con código {return_code}."

    output_lines = []

    for content in (stdout, stderr):
        for line in content.splitlines():
            stripped = line.strip()

            if stripped:
                output_lines.append(stripped)

    if output_lines:
        return output_lines[0]

    if return_code == 0:
        return "Comando ejecutado correctamente sin salida."

    return f"El comando terminó con código {return_code}."


def validate_tool(tool: ToolDefinition) -> ValidationResult:
    executable = tool.command[0]
    rendered_command = command_display(tool.command)

    if shutil.which(executable) is None:
        return ValidationResult(
            name=tool.name,
            status="NOT_INSTALLED",
            required=tool.required,
            details=f"No se encontró el ejecutable '{executable}' en PATH.",
            command=rendered_command,
        )

    try:
        result = subprocess.run(
            tool.command,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ValidationResult(
            name=tool.name,
            status="TIMEOUT",
            required=tool.required,
            details="La validación excedió el tiempo máximo de 20 segundos.",
            command=rendered_command,
        )
    except OSError as exc:
        return ValidationResult(
            name=tool.name,
            status="ERROR",
            required=tool.required,
            details=f"No se pudo ejecutar el comando: {exc}",
            command=rendered_command,
        )

    details = extract_version_output(
        result.stdout,
        result.stderr,
        result.returncode,
        tool.version_pattern,
    )

    if result.returncode != 0:
        return ValidationResult(
            name=tool.name,
            status="ERROR",
            required=tool.required,
            details=details,
            command=rendered_command,
        )

    return ValidationResult(
        name=tool.name,
        status="OK",
        required=tool.required,
        details=details,
        command=rendered_command,
    )


def validate_python_runtime() -> ValidationResult:
    version = platform.python_version()

    if sys.version_info < (3, 11):
        return ValidationResult(
            name="Python runtime",
            status="ERROR",
            required=True,
            details=(
                f"Python {version} detectado. "
                "Se requiere Python 3.11 o superior."
            ),
        )

    return ValidationResult(
        name="Python runtime",
        status="OK",
        required=True,
        details=f"Python {version}",
    )


def validate_python_dependency(
    package_name: str,
    import_name: str,
) -> ValidationResult:
    try:
        __import__(import_name)
        version = importlib.metadata.version(package_name)
    except ImportError:
        return ValidationResult(
            name=f"Python dependency: {package_name}",
            status="NOT_INSTALLED",
            required=True,
            details=(
                f"No se pudo importar '{import_name}'. "
                "Ejecuta 'poetry install'."
            ),
        )
    except importlib.metadata.PackageNotFoundError:
        return ValidationResult(
            name=f"Python dependency: {package_name}",
            status="ERROR",
            required=True,
            details=(
                "El módulo puede importarse, pero no se encontró "
                "metadata del paquete."
            ),
        )

    return ValidationResult(
        name=f"Python dependency: {package_name}",
        status="OK",
        required=True,
        details=f"{package_name} {version}",
    )


def validate_configuration(config: ConfigLoader) -> list[ValidationResult]:
    results: list[ValidationResult] = [
        ValidationResult(
            name="Project configuration",
            status="OK",
            required=True,
            details=str(config.config_path),
        )
    ]

    reference_errors = config.validate_referenced_files()

    if reference_errors:
        for error in reference_errors:
            results.append(
                ValidationResult(
                    name="Configured reference",
                    status="ERROR",
                    required=True,
                    details=error,
                )
            )
    else:
        results.append(
            ValidationResult(
                name="Configured references",
                status="OK",
                required=True,
                details="Todos los archivos y scripts configurados existen.",
            )
        )

    try:
        directories = config.ensure_project_directories()
    except OSError as exc:
        results.append(
            ValidationResult(
                name="Project directories",
                status="ERROR",
                required=True,
                details=f"No se pudieron preparar los directorios: {exc}",
            )
        )
    else:
        results.append(
            ValidationResult(
                name="Project directories",
                status="OK",
                required=True,
                details=(
                    "Directorios disponibles: "
                    + ", ".join(sorted(directories))
                ),
            )
        )

    return results


def validate_docker_daemon(config: ConfigLoader) -> ValidationResult:
    docker_command = config.get_command("docker_command", required=True)
    assert docker_command is not None

    command = [*split_command(docker_command), "info"]

    if shutil.which(command[0]) is None:
        return ValidationResult(
            name="Docker daemon",
            status="NOT_INSTALLED",
            required=True,
            details=f"No se encontró '{command[0]}' en PATH.",
            command=command_display(command),
        )

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ValidationResult(
            name="Docker daemon",
            status="TIMEOUT",
            required=True,
            details="Docker no respondió dentro de 20 segundos.",
            command=command_display(command),
        )
    except OSError as exc:
        return ValidationResult(
            name="Docker daemon",
            status="ERROR",
            required=True,
            details=f"No se pudo consultar Docker: {exc}",
            command=command_display(command),
        )

    if result.returncode != 0:
        details = extract_version_output(
            result.stdout,
            result.stderr,
            result.returncode,
        )

        return ValidationResult(
            name="Docker daemon",
            status="ERROR",
            required=True,
            details=(
                "Docker está instalado, pero el daemon no está disponible. "
                f"Detalle: {details}"
            ),
            command=command_display(command),
        )

    return ValidationResult(
        name="Docker daemon",
        status="OK",
        required=True,
        details="Docker daemon disponible.",
        command=command_display(command),
    )


def print_human_report(
    config: ConfigLoader,
    results: list[ValidationResult],
) -> None:
    line = "=" * 78

    print(line)
    print("Performance Engineering Environment Validation")
    print(line)
    print(f"Project: {config.get('project.name')}")
    print(f"Config: {config.config_path}")
    print(f"Python executable: {sys.executable}")
    print(line)

    for result in results:
        requirement = "required" if result.required else "optional"
        print(
            f"[{result.status:<13}] "
            f"{result.name} ({requirement})"
        )
        print(f"  {result.details}")

        if result.command:
            print(f"  Command: {result.command}")

    print(line)

    required_failures = [
        result
        for result in results
        if result.required and not result.passed
    ]

    optional_failures = [
        result
        for result in results
        if not result.required and not result.passed
    ]

    if required_failures:
        print(
            "Environment NOT READY: "
            f"{len(required_failures)} required validation(s) failed."
        )
    else:
        print("Environment OK")

    if optional_failures:
        print(
            "Optional warnings: "
            f"{len(optional_failures)} optional validation(s) failed."
        )


def print_json_report(
    config: ConfigLoader,
    results: list[ValidationResult],
) -> None:
    required_failures = [
        result
        for result in results
        if result.required and not result.passed
    ]

    payload = {
        "project": config.get("project.name"),
        "config_file": str(config.config_path),
        "python_executable": sys.executable,
        "status": "OK" if not required_failures else "NOT_READY",
        "results": [
            {
                "name": result.name,
                "status": result.status,
                "required": result.required,
                "details": result.details,
                "command": result.command,
            }
            for result in results
        ],
    }

    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> int:
    args = parse_arguments()

    try:
        config = load_config(config_path=args.config)
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    results: list[ValidationResult] = []

    results.append(validate_python_runtime())
    results.append(
        validate_python_dependency(
            package_name="PyYAML",
            import_name="yaml",
        )
    )
    results.extend(validate_configuration(config))

    tools = build_tool_definitions(config)

    for tool in tools:
        if args.skip_optional and not tool.required:
            continue

        results.append(validate_tool(tool))

    results.append(validate_docker_daemon(config))

    if args.json_output:
        print_json_report(config, results)
    else:
        print_human_report(config, results)

    required_failures = [
        result
        for result in results
        if result.required and not result.passed
    ]

    return 1 if required_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())