#!/usr/bin/env python3
"""
Genera planes Apache JMeter parametrizables para pruebas HTTP.

Características:

- Configuración central desde config/project-config.yaml.
- Propiedades JMeter sobrescribibles mediante -J.
- Validación de host, protocolo, puerto, método y tiempos.
- Restricción de salida al directorio configurado.
- Prometheus Listener parametrizable.
- Validación XML antes de confirmar el archivo.
- Escritura atómica para evitar JMX incompletos.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from config_loader import ConfigurationError, ConfigLoader, load_config


SUPPORTED_HTTP_METHODS = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
}

HOST_PATTERN = re.compile(
    r"^(?=.{1,253}$)"
    r"(localhost|"
    r"\d{1,3}(?:\.\d{1,3}){3}|"
    r"(?:[a-zA-Z0-9]"
    r"(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*"
    r"[a-zA-Z0-9]"
    r"(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)$"
)


class JmxGenerationError(RuntimeError):
    """Error controlado durante la generación del archivo JMX."""


def add_string(
    parent: ET.Element,
    name: str,
    value: Any,
) -> ET.Element:
    element = ET.SubElement(
        parent,
        "stringProp",
        {"name": name},
    )
    element.text = str(value)
    return element


def add_bool(
    parent: ET.Element,
    name: str,
    value: bool,
) -> ET.Element:
    element = ET.SubElement(
        parent,
        "boolProp",
        {"name": name},
    )
    element.text = "true" if value else "false"
    return element


def add_prometheus_collector(
    collectors: ET.Element,
    metric_name: str,
    help_text: str,
    collector_type: str,
    measuring: str,
    labels: list[str] | None = None,
    quantiles_or_buckets: str = "",
    listen_to: str = "samples",
) -> None:
    collector = ET.SubElement(
        collectors,
        "elementProp",
        {
            "name": "",
            "elementType": (
                "com.github.johrstrom.listener."
                "ListenerCollectorConfig"
            ),
        },
    )

    add_string(collector, "collector.help", help_text)
    add_string(collector, "collector.metric_name", metric_name)
    add_string(collector, "collector.type", collector_type)

    labels_property = ET.SubElement(
        collector,
        "collectionProp",
        {"name": "collector.labels"},
    )

    for index, label in enumerate(labels or []):
        add_string(
            labels_property,
            str(1000 + index),
            label,
        )

    add_string(
        collector,
        "collector.quantiles_or_buckets",
        quantiles_or_buckets,
    )
    add_string(
        collector,
        "listener.collector.listen_to",
        listen_to,
    )
    add_string(
        collector,
        "listener.collector.measuring",
        measuring,
    )


def normalize_scenario_name(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9._-]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized)
    normalized = normalized.strip("-._")

    if not normalized:
        raise JmxGenerationError(
            "El nombre del escenario no contiene caracteres válidos."
        )

    return normalized


def validate_host(host: str) -> str:
    value = host.strip()

    if "://" in value:
        raise JmxGenerationError(
            "El parámetro --host no debe incluir http:// ni https://."
        )

    if "/" in value:
        raise JmxGenerationError(
            "El parámetro --host no debe incluir rutas."
        )

    if not HOST_PATTERN.fullmatch(value):
        raise JmxGenerationError(
            f"Host inválido: {value}"
        )

    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", value):
        octets = value.split(".")

        if any(int(octet) > 255 for octet in octets):
            raise JmxGenerationError(
                f"Dirección IPv4 inválida: {value}"
            )

    return value


def validate_path(path: str) -> str:
    value = path.strip() or "/"

    if not value.startswith("/"):
        value = f"/{value}"

    if any(character in value for character in ("\n", "\r", "\x00")):
        raise JmxGenerationError(
            "El endpoint contiene caracteres no permitidos."
        )

    return value


def validate_positive_integer(
    name: str,
    value: int,
    minimum: int = 1,
    maximum: int | None = None,
) -> int:
    if value < minimum:
        raise JmxGenerationError(
            f"{name} debe ser mayor o igual a {minimum}."
        )

    if maximum is not None and value > maximum:
        raise JmxGenerationError(
            f"{name} no puede ser mayor que {maximum}."
        )

    return value


def validate_http_status(value: int) -> int:
    if not 100 <= value <= 599:
        raise JmxGenerationError(
            "--expected-status debe estar entre 100 y 599."
        )

    return value


def resolve_output_path(
    config: ConfigLoader,
    output_argument: str | None,
    scenario: str,
) -> Path:
    generated_directory = config.get_path(
        "paths.generated_jmx_directory",
        required=True,
        create=True,
        directory=True,
    )

    assert generated_directory is not None

    if output_argument:
        candidate = Path(output_argument).expanduser()

        if not candidate.is_absolute():
            candidate = config.project_root / candidate
    else:
        candidate = generated_directory / f"{scenario}.jmx"

    candidate = candidate.resolve()

    try:
        candidate.relative_to(generated_directory)
    except ValueError as exc:
        raise JmxGenerationError(
            "El archivo JMX debe generarse dentro de: "
            f"{generated_directory}"
        ) from exc

    if candidate.suffix.lower() != ".jmx":
        raise JmxGenerationError(
            "El archivo de salida debe tener extensión .jmx."
        )

    return candidate


def build_jmx_tree(
    *,
    project_name: str,
    scenario_name: str,
    host: str,
    port: int,
    protocol: str,
    endpoint_path: str,
    method: str,
    expected_status: int,
    connect_timeout_ms: int,
    response_timeout_ms: int,
    default_threads: int,
    default_ramp_time: int,
    default_duration: int,
    prometheus_port: int,
) -> ET.ElementTree:
    root = ET.Element(
        "jmeterTestPlan",
        {
            "version": "1.2",
            "properties": "5.0",
            "jmeter": "5.6.3",
        },
    )

    root_tree = ET.SubElement(root, "hashTree")

    test_plan = ET.SubElement(
        root_tree,
        "TestPlan",
        {
            "guiclass": "TestPlanGui",
            "testclass": "TestPlan",
            "testname": scenario_name,
            "enabled": "true",
        },
    )

    add_string(
        test_plan,
        "TestPlan.comments",
        f"Generated by {project_name}.",
    )
    add_bool(test_plan, "TestPlan.functional_mode", False)
    add_bool(test_plan, "TestPlan.tearDown_on_shutdown", True)
    add_bool(test_plan, "TestPlan.serialize_threadgroups", False)

    variables = ET.SubElement(
        test_plan,
        "elementProp",
        {
            "name": "TestPlan.user_defined_variables",
            "elementType": "Arguments",
            "guiclass": "ArgumentsPanel",
            "testclass": "Arguments",
            "testname": "User Defined Variables",
            "enabled": "true",
        },
    )

    ET.SubElement(
        variables,
        "collectionProp",
        {"name": "Arguments.arguments"},
    )

    plan_tree = ET.SubElement(root_tree, "hashTree")

    thread_group = ET.SubElement(
        plan_tree,
        "ThreadGroup",
        {
            "guiclass": "ThreadGroupGui",
            "testclass": "ThreadGroup",
            "testname": "Virtual Users",
            "enabled": "true",
        },
    )

    add_string(
        thread_group,
        "ThreadGroup.on_sample_error",
        "continue",
    )

    loop_controller = ET.SubElement(
        thread_group,
        "elementProp",
        {
            "name": "ThreadGroup.main_controller",
            "elementType": "LoopController",
            "guiclass": "LoopControlPanel",
            "testclass": "LoopController",
            "testname": "Loop Controller",
            "enabled": "true",
        },
    )

    add_bool(
        loop_controller,
        "LoopController.continue_forever",
        False,
    )
    add_string(
        loop_controller,
        "LoopController.loops",
        "-1",
    )

    add_string(
        thread_group,
        "ThreadGroup.num_threads",
        f"${{__P(threads,{default_threads})}}",
    )
    add_string(
        thread_group,
        "ThreadGroup.ramp_time",
        f"${{__P(ramp_time,{default_ramp_time})}}",
    )
    add_bool(
        thread_group,
        "ThreadGroup.scheduler",
        True,
    )
    add_string(
        thread_group,
        "ThreadGroup.duration",
        f"${{__P(duration,{default_duration})}}",
    )
    add_string(
        thread_group,
        "ThreadGroup.delay",
        "0",
    )

    thread_tree = ET.SubElement(plan_tree, "hashTree")

    headers = ET.SubElement(
        thread_tree,
        "HeaderManager",
        {
            "guiclass": "HeaderPanel",
            "testclass": "HeaderManager",
            "testname": "HTTP Headers",
            "enabled": "true",
        },
    )

    headers_collection = ET.SubElement(
        headers,
        "collectionProp",
        {"name": "HeaderManager.headers"},
    )

    accept_header = ET.SubElement(
        headers_collection,
        "elementProp",
        {
            "name": "Accept",
            "elementType": "Header",
        },
    )

    add_string(
        accept_header,
        "Header.name",
        "Accept",
    )
    add_string(
        accept_header,
        "Header.value",
        "application/json",
    )

    ET.SubElement(thread_tree, "hashTree")

    sampler = ET.SubElement(
        thread_tree,
        "HTTPSamplerProxy",
        {
            "guiclass": "HttpTestSampleGui",
            "testclass": "HTTPSamplerProxy",
            "testname": f"{method} {endpoint_path}",
            "enabled": "true",
        },
    )

    add_string(sampler, "HTTPSampler.domain", host)
    add_string(sampler, "HTTPSampler.port", port)
    add_string(sampler, "HTTPSampler.protocol", protocol)
    add_string(sampler, "HTTPSampler.path", endpoint_path)
    add_string(sampler, "HTTPSampler.method", method)
    add_string(
        sampler,
        "HTTPSampler.connect_timeout",
        connect_timeout_ms,
    )
    add_string(
        sampler,
        "HTTPSampler.response_timeout",
        response_timeout_ms,
    )
    add_bool(sampler, "HTTPSampler.follow_redirects", True)
    add_bool(sampler, "HTTPSampler.auto_redirects", False)
    add_bool(sampler, "HTTPSampler.use_keepalive", True)
    add_bool(sampler, "HTTPSampler.DO_MULTIPART_POST", False)

    sampler_tree = ET.SubElement(thread_tree, "hashTree")

    assertion = ET.SubElement(
        sampler_tree,
        "ResponseAssertion",
        {
            "guiclass": "AssertionGui",
            "testclass": "ResponseAssertion",
            "testname": f"Validate HTTP Status {expected_status}",
            "enabled": "true",
        },
    )

    assertion_patterns = ET.SubElement(
        assertion,
        "collectionProp",
        {"name": "Asserion.test_strings"},
    )

    add_string(
        assertion_patterns,
        "49586",
        expected_status,
    )
    add_string(
        assertion,
        "Assertion.custom_message",
        f"Expected HTTP status {expected_status}",
    )
    add_bool(
        assertion,
        "Assertion.assume_success",
        False,
    )
    add_string(
        assertion,
        "Assertion.test_field",
        "Assertion.response_code",
    )
    add_string(
        assertion,
        "Assertion.test_type",
        "8",
    )

    ET.SubElement(sampler_tree, "hashTree")

    prometheus_listener = ET.SubElement(
        thread_tree,
        "com.github.johrstrom.listener.PrometheusListener",
        {
            "guiclass": (
                "com.github.johrstrom.listener.gui."
                "PrometheusListenerGui"
            ),
            "testclass": (
                "com.github.johrstrom.listener."
                "PrometheusListener"
            ),
            "testname": "Prometheus Listener",
            "enabled": "true",
        },
    )

    collectors = ET.SubElement(
        prometheus_listener,
        "collectionProp",
        {"name": "prometheus.collector_definitions"},
    )

    add_prometheus_collector(
        collectors,
        metric_name="jmeter_requests_total",
        help_text="Total JMeter requests",
        collector_type="COUNTER",
        measuring="CountTotal",
        labels=["label"],
    )

    add_prometheus_collector(
        collectors,
        metric_name="jmeter_success_total",
        help_text="Successful JMeter requests",
        collector_type="COUNTER",
        measuring="SuccessTotal",
        labels=["label"],
    )

    add_prometheus_collector(
        collectors,
        metric_name="jmeter_error_total",
        help_text="Failed JMeter requests",
        collector_type="COUNTER",
        measuring="FailureTotal",
        labels=["label"],
    )

    add_prometheus_collector(
        collectors,
        metric_name="jmeter_response_time_ms",
        help_text="JMeter response time in milliseconds",
        collector_type="SUMMARY",
        measuring="ResponseTime",
        labels=["label"],
        quantiles_or_buckets=(
            "0.5,0.05|0.9,0.01|0.95,0.005|0.99,0.001"
        ),
    )

    add_string(
        prometheus_listener,
        "prometheus.port",
        f"${{__P(prometheus_port,{prometheus_port})}}",
    )
    add_string(
        prometheus_listener,
        "TestPlan.comments",
        "",
    )

    ET.SubElement(thread_tree, "hashTree")

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")

    return tree


def write_jmx_atomically(
    tree: ET.ElementTree,
    output_path: Path,
    overwrite: bool,
) -> None:
    if output_path.exists() and not overwrite:
        raise JmxGenerationError(
            f"El archivo ya existe: {output_path}. "
            "Usa --force para reemplazarlo."
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{output_path.stem}-",
            suffix=".tmp",
            dir=output_path.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

            temporary_file.write(
                b'<?xml version="1.0" encoding="UTF-8"?>\n'
            )

            tree.write(
                temporary_file,
                encoding="utf-8",
                xml_declaration=False,
            )

        ET.parse(temporary_path)

        temporary_path.replace(output_path)

    except ET.ParseError as exc:
        raise JmxGenerationError(
            "El XML generado no es válido."
        ) from exc

    except OSError as exc:
        raise JmxGenerationError(
            f"No se pudo escribir el archivo JMX: {exc}"
        ) from exc

    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def parse_arguments(
    config: ConfigLoader,
) -> argparse.Namespace:
    default_expected_status = int(
        config.get(
            "execution.defaults.expected_http_status",
            default=200,
        )
    )

    default_prometheus_port = int(
        config.get(
            "observability.jmeter_metrics.port",
            default=9270,
        )
    )

    parser = argparse.ArgumentParser(
        description=(
            "Genera un plan JMeter HTTP parametrizable "
            "utilizando la configuración central del proyecto."
        ),
    )

    parser.add_argument(
        "--config",
        help="Ruta alternativa a project-config.yaml.",
    )
    parser.add_argument(
        "--scenario",
        default="performance-test",
        help="Nombre lógico del escenario.",
    )
    parser.add_argument(
        "--host",
        required=True,
        help="Host sin protocolo ni endpoint.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=(
            "Puerto HTTP. Si se omite, se usa 443 para https "
            "y 80 para http."
        ),
    )
    parser.add_argument(
        "--protocol",
        choices=("http", "https"),
        default="https",
    )
    parser.add_argument(
        "--path",
        default="/",
        help="Endpoint que será evaluado.",
    )
    parser.add_argument(
        "--method",
        default="GET",
        help="Método HTTP.",
    )
    parser.add_argument(
        "--expected-status",
        type=int,
        default=default_expected_status,
    )
    parser.add_argument(
        "--connect-timeout-ms",
        type=int,
        default=5000,
    )
    parser.add_argument(
        "--response-timeout-ms",
        type=int,
        default=10000,
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=10,
        help="Usuarios virtuales por defecto del JMX.",
    )
    parser.add_argument(
        "--ramp-time",
        type=int,
        default=10,
        help="Ramp-up por defecto en segundos.",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duración por defecto en segundos.",
    )
    parser.add_argument(
        "--prometheus-port",
        type=int,
        default=default_prometheus_port,
    )
    parser.add_argument(
        "--output",
        help=(
            "Ruta del JMX. Debe estar dentro del directorio "
            "generated_jmx configurado."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Permite reemplazar un JMX existente.",
    )

    return parser.parse_args()


def main() -> int:
    preliminary_parser = argparse.ArgumentParser(add_help=False)
    preliminary_parser.add_argument("--config")
    preliminary_args, _ = preliminary_parser.parse_known_args()

    try:
        config = load_config(
            config_path=preliminary_args.config,
        )

        args = parse_arguments(config)

        scenario_name = args.scenario.strip()

        if not scenario_name:
            raise JmxGenerationError(
                "--scenario no puede estar vacío."
            )

        normalized_scenario = normalize_scenario_name(
            scenario_name
        )

        host = validate_host(args.host)
        endpoint_path = validate_path(args.path)

        protocol = args.protocol.lower()
        method = args.method.upper()

        if method not in SUPPORTED_HTTP_METHODS:
            raise JmxGenerationError(
                "Método HTTP no soportado. Valores permitidos: "
                + ", ".join(sorted(SUPPORTED_HTTP_METHODS))
            )

        port = args.port

        if port is None:
            port = 443 if protocol == "https" else 80

        validate_positive_integer(
            "port",
            port,
            minimum=1,
            maximum=65535,
        )
        validate_positive_integer(
            "connect-timeout-ms",
            args.connect_timeout_ms,
        )
        validate_positive_integer(
            "response-timeout-ms",
            args.response_timeout_ms,
        )
        validate_positive_integer(
            "threads",
            args.threads,
        )
        validate_positive_integer(
            "ramp-time",
            args.ramp_time,
        )
        validate_positive_integer(
            "duration",
            args.duration,
        )
        validate_positive_integer(
            "prometheus-port",
            args.prometheus_port,
            minimum=1,
            maximum=65535,
        )
        validate_http_status(args.expected_status)

        output_path = resolve_output_path(
            config=config,
            output_argument=args.output,
            scenario=normalized_scenario,
        )

        project_name = str(
            config.get(
                "project.name",
                default="Performance Engineering Platform",
            )
        )

        tree = build_jmx_tree(
            project_name=project_name,
            scenario_name=scenario_name,
            host=host,
            port=port,
            protocol=protocol,
            endpoint_path=endpoint_path,
            method=method,
            expected_status=args.expected_status,
            connect_timeout_ms=args.connect_timeout_ms,
            response_timeout_ms=args.response_timeout_ms,
            default_threads=args.threads,
            default_ramp_time=args.ramp_time,
            default_duration=args.duration,
            prometheus_port=args.prometheus_port,
        )

        write_jmx_atomically(
            tree=tree,
            output_path=output_path,
            overwrite=args.force,
        )

        metrics_host = config.get(
            "observability.jmeter_metrics.host",
            default="localhost",
        )
        metrics_endpoint = config.get(
            "observability.jmeter_metrics.endpoint",
            default="/metrics",
        )

        print("JMX generado correctamente")
        print(f"Scenario: {scenario_name}")
        print(f"File: {output_path}")
        print(
            f"Target: {method} "
            f"{protocol}://{host}:{port}{endpoint_path}"
        )
        print(
            "Default load: "
            f"{args.threads} users, "
            f"{args.ramp_time}s ramp-up, "
            f"{args.duration}s duration"
        )
        print(
            "Expected status: "
            f"{args.expected_status}"
        )
        print(
            "Prometheus metrics: "
            f"http://{metrics_host}:"
            f"{args.prometheus_port}{metrics_endpoint}"
        )
        print("")
        print("Runtime overrides:")
        print(
            f"  -Jthreads={args.threads} "
            f"-Jramp_time={args.ramp_time} "
            f"-Jduration={args.duration} "
            f"-Jprometheus_port={args.prometheus_port}"
        )

        return 0

    except (
        ConfigurationError,
        JmxGenerationError,
        ValueError,
    ) as exc:
        print(
            f"JMX generation error: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())