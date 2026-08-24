#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse


SCHEMA_VERSION = "1.0"

SUPPORTED_SOURCE_TYPES = {
    "CLI",
}

SUPPORTED_SYSTEM_TYPES = {
    "API",
}

SUPPORTED_METHODS = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
}

SUPPORTED_EXTRACTOR_TYPES = {
    "JSON_PATH",
}

DEFAULT_EXPECTED_STATUS = 200

RUNTIME_REFERENCE_RE = re.compile(
    r"\$\{([A-Za-z_][A-Za-z0-9_.-]*)\}"
)


class NormalizedCompilationError(RuntimeError):
    """Raised when a normalized model cannot be compiled safely."""


def load_json(
    path: Path,
) -> dict[str, Any]:
    """Load and validate a JSON object from disk."""

    if not path.is_file():
        raise NormalizedCompilationError(
            f"Normalized model not found: {path}"
        )

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except OSError as exc:
        raise NormalizedCompilationError(
            f"Unable to read normalized model: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise NormalizedCompilationError(
            "Invalid normalized model JSON: "
            f"line {exc.lineno}, "
            f"column {exc.colno}: "
            f"{exc.msg}"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise NormalizedCompilationError(
            "Normalized model root must be an object."
        )

    return payload


def write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    """Atomically persist deterministic JSON."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    try:
        temporary.write_text(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        # Validate the exact serialized artifact before replacing.
        json.loads(
            temporary.read_text(
                encoding="utf-8"
            )
        )

        temporary.replace(
            path
        )

    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass

        raise NormalizedCompilationError(
            f"Unable to persist executable model: {exc}"
        ) from exc


def require_mapping(
    value: Any,
    context: str,
) -> dict[str, Any]:
    if not isinstance(
        value,
        dict,
    ):
        raise NormalizedCompilationError(
            f"{context} must be an object."
        )

    return value


def require_list(
    value: Any,
    context: str,
) -> list[Any]:
    if not isinstance(
        value,
        list,
    ):
        raise NormalizedCompilationError(
            f"{context} must be a list."
        )

    return value


def require_text(
    mapping: dict[str, Any],
    key: str,
    context: str,
) -> str:
    value = mapping.get(
        key
    )

    if not isinstance(
        value,
        str,
    ):
        raise NormalizedCompilationError(
            f"{context}.{key} must be a string."
        )

    value = value.strip()

    if not value:
        raise NormalizedCompilationError(
            f"{context}.{key} must not be empty."
        )

    return value


def normalize_schema_version(
    normalized: dict[str, Any],
) -> str:
    version = str(
        normalized.get(
            "schema_version",
            "",
        )
    ).strip()

    if version != SCHEMA_VERSION:
        raise NormalizedCompilationError(
            "Unsupported normalized model schema_version: "
            f"{version or '<EMPTY>'}. "
            f"Expected {SCHEMA_VERSION}."
        )

    return version


def normalize_source(
    normalized: dict[str, Any],
) -> dict[str, Any]:
    source = require_mapping(
        normalized.get(
            "source"
        ),
        "source",
    )

    source_type = str(
        source.get(
            "type",
            "",
        )
    ).strip().upper()

    if source_type not in SUPPORTED_SOURCE_TYPES:
        raise NormalizedCompilationError(
            "This compiler handles normalized CLI/API models only. "
            "Postman collections and existing JMX files must remain "
            "on their dedicated workflow paths. "
            f"Received source.type={source_type or '<EMPTY>'}."
        )

    return source


def normalize_system(
    normalized: dict[str, Any],
) -> dict[str, Any]:
    system = require_mapping(
        normalized.get(
            "system"
        ),
        "system",
    )

    system_type = str(
        system.get(
            "type",
            "",
        )
    ).strip().upper()

    if system_type not in SUPPORTED_SYSTEM_TYPES:
        raise NormalizedCompilationError(
            "Normalized CLI compilation currently supports "
            "API models only. Existing Web/JMX recordings must "
            "preserve the original JMX. "
            f"Received system.type={system_type or '<EMPTY>'}."
        )

    return system


def parse_target(
    target: str,
    context: str,
) -> dict[str, Any]:
    """Split a literal HTTP target into JMeter request components."""

    value = target.strip()

    if not value:
        raise NormalizedCompilationError(
            f"{context}.target must not be empty."
        )

    if any(
        token in value
        for token in (
            "[",
            "]",
            "\n",
            "\r",
            "\t",
        )
    ):
        raise NormalizedCompilationError(
            f"{context}.target must be a literal HTTP/HTTPS URL."
        )

    parsed = urlparse(
        value
    )

    protocol = (
        parsed.scheme
        .strip()
        .lower()
    )

    if protocol not in {
        "http",
        "https",
    }:
        raise NormalizedCompilationError(
            f"{context}.target must use http or https."
        )

    if not parsed.hostname:
        raise NormalizedCompilationError(
            f"{context}.target has no valid host."
        )

    if (
        parsed.username
        or parsed.password
    ):
        raise NormalizedCompilationError(
            f"{context}.target must not embed credentials."
        )

    try:
        explicit_port = parsed.port
    except ValueError as exc:
        raise NormalizedCompilationError(
            f"{context}.target contains an invalid port."
        ) from exc

    port = (
        explicit_port
        if explicit_port is not None
        else (
            443
            if protocol == "https"
            else 80
        )
    )

    if not 1 <= port <= 65535:
        raise NormalizedCompilationError(
            f"{context}.target port must be between 1 and 65535."
        )

    path = (
        parsed.path
        or "/"
    )

    # Keep query separated because generate_postman_jmx.py already
    # appends request["query"] to HTTPSampler.path.
    query = (
        parsed.query
        if parsed.query
        else None
    )

    return {
        "protocol": protocol,
        "host": parsed.hostname,
        "port": port,
        "path": path,
        "query": query,
    }


def normalize_headers(
    value: Any,
    context: str,
) -> list[dict[str, str]]:
    """Convert normalized header mapping to generator contract."""

    if value is None:
        return []

    if not isinstance(
        value,
        dict,
    ):
        raise NormalizedCompilationError(
            f"{context}.headers must be an object."
        )

    result: list[dict[str, str]] = []

    for name, header_value in value.items():
        clean_name = str(
            name
        ).strip()

        if not clean_name:
            raise NormalizedCompilationError(
                f"{context}.headers contains an empty header name."
            )

        if (
            "\n" in clean_name
            or "\r" in clean_name
        ):
            raise NormalizedCompilationError(
                f"{context}.headers contains an invalid header name."
            )

        clean_value = str(
            header_value
        )

        if (
            "\n" in clean_value
            or "\r" in clean_value
        ):
            raise NormalizedCompilationError(
                f"{context}.headers['{clean_name}'] "
                "contains an invalid newline."
            )

        result.append(
            {
                "name": clean_name,
                "value": clean_value,
            }
        )

    return result


def normalize_json_body(
    value: Any,
    context: str,
) -> Any | None:
    """Normalize an API body for the existing JMX generator.

    generate_postman_jmx.py expects request["json_body"].

    Supported input:
    - dict
    - list
    - string containing valid JSON

    Arbitrary text/XML/form bodies are intentionally not guessed.
    """

    if value is None:
        return None

    if isinstance(
        value,
        (
            dict,
            list,
        ),
    ):
        return value

    if isinstance(
        value,
        str,
    ):
        raw = value.strip()

        if not raw:
            raise NormalizedCompilationError(
                f"{context}.body must not be an empty string."
            )

        try:
            parsed = json.loads(
                raw
            )
        except json.JSONDecodeError as exc:
            raise NormalizedCompilationError(
                f"{context}.body string must contain valid JSON. "
                "Raw text, form and XML bodies are not inferred "
                "by the generic JSON API compiler."
            ) from exc

        if not isinstance(
            parsed,
            (
                dict,
                list,
            ),
        ):
            raise NormalizedCompilationError(
                f"{context}.body JSON must be an object or array."
            )

        return parsed

    raise NormalizedCompilationError(
        f"{context}.body must be an object, array "
        "or a string containing valid JSON."
    )


def normalize_expected_status(
    value: Any,
    context: str,
) -> list[int]:
    """Normalize accepted HTTP status codes."""

    if value is None:
        raw_values = [
            DEFAULT_EXPECTED_STATUS
        ]
    elif isinstance(
        value,
        list,
    ):
        raw_values = value
    else:
        raw_values = [
            value
        ]

    if not raw_values:
        raise NormalizedCompilationError(
            f"{context}.expected_status must not be empty."
        )

    result: list[int] = []

    for raw in raw_values:
        try:
            status = int(
                raw
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise NormalizedCompilationError(
                f"{context}.expected_status contains "
                f"an invalid status: {raw}"
            ) from exc

        if not 100 <= status <= 599:
            raise NormalizedCompilationError(
                f"{context}.expected_status contains "
                f"an out-of-range status: {status}"
            )

        if status not in result:
            result.append(
                status
            )

    return result


def normalize_correlations(
    normalized: dict[str, Any],
) -> list[dict[str, Any]]:
    runtime = normalized.get(
        "runtime",
        {},
    )

    if runtime is None:
        return []

    runtime = require_mapping(
        runtime,
        "runtime",
    )

    correlations = runtime.get(
        "correlations",
        [],
    )

    correlations = require_list(
        correlations,
        "runtime.correlations",
    )

    result = []

    for index, item in enumerate(
        correlations
    ):
        context = (
            f"runtime.correlations[{index}]"
        )

        if not isinstance(
            item,
            dict,
        ):
            raise NormalizedCompilationError(
                f"{context} must be an object."
            )

        extractor_type = str(
            item.get(
                "type",
                "",
            )
        ).strip().upper()

        if extractor_type not in SUPPORTED_EXTRACTOR_TYPES:
            raise NormalizedCompilationError(
                f"{context}.type={extractor_type or '<EMPTY>'} "
                "is not supported by the current generic "
                "multi-request JMX contract."
            )

        variable = str(
            item.get(
                "variable",
                item.get(
                    "name",
                    "",
                ),
            )
        ).strip()

        expression = str(
            item.get(
                "expression",
                "",
            )
        ).strip()

        source_transaction = str(
            item.get(
                "transaction",
                item.get(
                    "source_transaction",
                    "",
                ),
            )
        ).strip()

        if not variable:
            raise NormalizedCompilationError(
                f"{context} requires variable/name."
            )

        if not expression:
            raise NormalizedCompilationError(
                f"{context} requires expression."
            )

        if not source_transaction:
            raise NormalizedCompilationError(
                f"{context} requires source transaction."
            )

        result.append(
            {
                "type": extractor_type,
                "variable": variable,
                "expression": expression,
                "transaction": source_transaction,
            }
        )

    return result


def extractors_for_transaction(
    correlations: list[dict[str, Any]],
    transaction_name: str,
) -> list[dict[str, Any]]:
    """Build the exact extractor contract consumed by JMX generator."""

    result = []

    for correlation in correlations:
        if (
            correlation["transaction"]
            != transaction_name
        ):
            continue

        result.append(
            {
                "variable": correlation[
                    "variable"
                ],
                "json_path": correlation[
                    "expression"
                ],
            }
        )

    return result


def normalize_parameters(
    normalized: dict[str, Any],
) -> tuple[
    list[str],
    list[str],
    dict[str, dict[str, Any]],
]:
    """Resolve runtime and sensitive parameters."""

    data = normalized.get(
        "data",
        {},
    )

    if data is None:
        data = {}

    data = require_mapping(
        data,
        "data",
    )

    parameters = data.get(
        "parameters",
        [],
    )

    parameters = require_list(
        parameters,
        "data.parameters",
    )

    runtime_names: list[str] = []
    sensitive_names: list[str] = []
    catalog: dict[str, dict[str, Any]] = {}

    for index, item in enumerate(
        parameters
    ):
        context = (
            f"data.parameters[{index}]"
        )

        if not isinstance(
            item,
            dict,
        ):
            raise NormalizedCompilationError(
                f"{context} must be an object."
            )

        name = str(
            item.get(
                "name",
                "",
            )
        ).strip()

        if not name:
            raise NormalizedCompilationError(
                f"{context}.name must not be empty."
            )

        if name in catalog:
            raise NormalizedCompilationError(
                f"Duplicate runtime parameter: {name}"
            )

        source = str(
            item.get(
                "source",
                "RUNTIME",
            )
        ).strip().upper()

        sensitive = bool(
            item.get(
                "sensitive",
                False,
            )
        )

        catalog[
            name
        ] = {
            "name": name,
            "source": source,
            "sensitive": sensitive,
        }

        runtime_names.append(
            name
        )

        if sensitive:
            sensitive_names.append(
                name
            )

    return (
        runtime_names,
        sensitive_names,
        catalog,
    )


def collect_runtime_references(
    value: Any,
) -> set[str]:
    """Collect ${name} references recursively without resolving values."""

    references: set[str] = set()

    if isinstance(
        value,
        dict,
    ):
        for child in value.values():
            references.update(
                collect_runtime_references(
                    child
                )
            )

    elif isinstance(
        value,
        list,
    ):
        for child in value:
            references.update(
                collect_runtime_references(
                    child
                )
            )

    elif isinstance(
        value,
        str,
    ):
        references.update(
            RUNTIME_REFERENCE_RE.findall(
                value
            )
        )

    return references


def validate_runtime_references(
    requests: list[dict[str, Any]],
    parameter_catalog: dict[str, dict[str, Any]],
    correlations: list[dict[str, Any]],
) -> None:
    """Fail closed when a request references an undeclared variable."""

    declared = set(
        parameter_catalog
    )

    declared.update(
        item["variable"]
        for item in correlations
    )

    for index, request in enumerate(
        requests
    ):
        references = set()

        references.update(
            collect_runtime_references(
                request.get(
                    "headers",
                    []
                )
            )
        )

        references.update(
            collect_runtime_references(
                request.get(
                    "json_body"
                )
            )
        )

        references.update(
            collect_runtime_references(
                request.get(
                    "query"
                )
            )
        )

        unknown = sorted(
            references
            - declared
        )

        if unknown:
            raise NormalizedCompilationError(
                f"requests[{index}] references undeclared "
                "runtime variables: "
                + ", ".join(
                    unknown
                )
            )


def validate_correlation_sources(
    requests: list[dict[str, Any]],
    correlations: list[dict[str, Any]],
) -> None:
    transaction_names = {
        str(
            request.get(
                "id",
                "",
            )
        )
        for request in requests
    }

    for correlation in correlations:
        source = correlation[
            "transaction"
        ]

        if source not in transaction_names:
            raise NormalizedCompilationError(
                "Correlation source transaction does not exist: "
                f"{source}"
            )


def compile_model(
    normalized: dict[str, Any],
) -> dict[str, Any]:
    """Compile normalized CLI/API model into executable JMX model."""

    normalize_schema_version(
        normalized
    )

    source = normalize_source(
        normalized
    )

    normalize_system(
        normalized
    )

    scenarios = require_list(
        normalized.get(
            "scenarios",
            [],
        ),
        "scenarios",
    )

    if len(
        scenarios
    ) != 1:
        raise NormalizedCompilationError(
            "Exactly one normalized scenario is required "
            "per executable model."
        )

    scenario = require_mapping(
        scenarios[0],
        "scenarios[0]",
    )

    scenario_name = require_text(
        scenario,
        "name",
        "scenarios[0]",
    )

    transactions = require_list(
        scenario.get(
            "transactions",
            [],
        ),
        "scenarios[0].transactions",
    )

    if not transactions:
        raise NormalizedCompilationError(
            "Scenario must contain at least one transaction."
        )

    correlations = normalize_correlations(
        normalized
    )

    (
        runtime_parameters,
        sensitive_parameters,
        parameter_catalog,
    ) = normalize_parameters(
        normalized
    )

    requests: list[dict[str, Any]] = []

    seen_names: set[str] = set()

    for index, raw_transaction in enumerate(
        transactions
    ):
        context = (
            f"scenarios[0].transactions[{index}]"
        )

        transaction = require_mapping(
            raw_transaction,
            context,
        )

        name = require_text(
            transaction,
            "name",
            context,
        )

        if name in seen_names:
            raise NormalizedCompilationError(
                f"Duplicate transaction name: {name}"
            )

        seen_names.add(
            name
        )

        method = require_text(
            transaction,
            "method",
            context,
        ).upper()

        if method not in SUPPORTED_METHODS:
            raise NormalizedCompilationError(
                f"{context}.method is unsupported: {method}"
            )

        target = require_text(
            transaction,
            "target",
            context,
        )

        target_parts = parse_target(
            target,
            context,
        )

        request: dict[str, Any] = {
            "id": name,
            "name": name,
            "method": method,
            "protocol": target_parts[
                "protocol"
            ],
            "host": target_parts[
                "host"
            ],
            "port": target_parts[
                "port"
            ],
            "path": target_parts[
                "path"
            ],
            "headers": normalize_headers(
                transaction.get(
                    "headers"
                ),
                context,
            ),
            "extractors": (
                extractors_for_transaction(
                    correlations,
                    name,
                )
            ),
            "expected_status": (
                normalize_expected_status(
                    transaction.get(
                        "expected_status"
                    ),
                    context,
                )
            ),
        }

        query = target_parts.get(
            "query"
        )

        if query:
            request[
                "query"
            ] = query

        body = normalize_json_body(
            transaction.get(
                "body"
            ),
            context,
        )

        if body is not None:
            request[
                "json_body"
            ] = body

        requests.append(
            request
        )

    validate_correlation_sources(
        requests,
        correlations,
    )

    validate_runtime_references(
        requests,
        parameter_catalog,
        correlations,
    )

    hosts = sorted(
        {
            (
                request["protocol"],
                request["host"],
                request["port"],
            )
            for request in requests
        }
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "type": "NORMALIZED_CLI",
            "original_type": str(
                source.get(
                    "type",
                    ""
                )
            ).upper(),
            "artifact": source.get(
                "artifact"
            ),
        },
        "scenario_candidate": {
            "id": scenario_name,
            "type": (
                "MULTI_REQUEST"
                if len(
                    requests
                )
                > 1
                else "SINGLE_REQUEST"
            ),
        },
        "requests": requests,
        "parameters": {
            "runtime": runtime_parameters,
            "sensitive": sensitive_parameters,
        },
        "secrets": {
            "jmeter_properties": sensitive_parameters,
        },
        "correlations": correlations,
        "target_summary": {
            "host_count": len(
                hosts
            ),
            "hosts": [
                {
                    "protocol": protocol,
                    "host": host,
                    "port": port,
                }
                for (
                    protocol,
                    host,
                    port,
                ) in hosts
            ],
        },
        "summary": {
            "request_count": len(
                requests
            ),
            "correlation_count": len(
                correlations
            ),
            "runtime_parameter_count": len(
                runtime_parameters
            ),
            "secret_count": len(
                sensitive_parameters
            ),
            "host_count": len(
                hosts
            ),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compile a normalized CLI/API performance model "
            "into the deterministic multi-request executable "
            "model consumed by the JMeter generator."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help=(
            "normalized-performance-model.json generated "
            "by the governed performance intake."
        ),
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help=(
            "Destination executable-model.json."
        ),
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    input_path = (
        args.input
        .expanduser()
        .resolve()
    )

    output_path = (
        args.output
        .expanduser()
        .resolve()
    )

    try:
        normalized = load_json(
            input_path
        )

        executable = compile_model(
            normalized
        )

        write_json(
            output_path,
            executable,
        )

    except (
        NormalizedCompilationError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        print(
            "NORMALIZED COMPILATION ERROR: "
            f"{exc}",
            file=sys.stderr,
        )
        return 2

    summary = executable[
        "summary"
    ]

    print("=" * 72)
    print("NORMALIZED CLI -> EXECUTABLE MODEL")
    print("=" * 72)
    print(
        f"Input              : {input_path}"
    )
    print(
        f"Output             : {output_path}"
    )
    print(
        "Scenario           : "
        f"{executable['scenario_candidate']['id']}"
    )
    print(
        "Scenario type      : "
        f"{executable['scenario_candidate']['type']}"
    )
    print(
        "Requests           : "
        f"{summary['request_count']}"
    )
    print(
        "Hosts              : "
        f"{summary['host_count']}"
    )
    print(
        "Runtime parameters : "
        f"{summary['runtime_parameter_count']}"
    )
    print(
        "Correlations       : "
        f"{summary['correlation_count']}"
    )
    print(
        "Secrets            : "
        f"{summary['secret_count']}"
    )
    print("=" * 72)
    print("Executable model   : VALID")
    print("JMeter             : NOT EXECUTED")
    print("=" * 72)
    print("EXECUTABLE MODEL READY")

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )