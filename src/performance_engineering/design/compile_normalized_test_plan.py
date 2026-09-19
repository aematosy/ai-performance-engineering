#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


SCHEMA_VERSION = "1.0"

SUPPORTED_HTTP_METHODS = {
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


class TestPlanCompilationError(RuntimeError):
    pass


def load_json(
    path: Path,
    description: str,
) -> dict[str, Any]:
    if not path.is_file():
        raise TestPlanCompilationError(
            f"{description} not found: {path}"
        )

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except OSError as exc:
        raise TestPlanCompilationError(
            f"Unable to read {description}: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise TestPlanCompilationError(
            f"Invalid JSON in {description}: "
            f"line {exc.lineno}, column {exc.colno}: "
            f"{exc.msg}"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise TestPlanCompilationError(
            f"{description} root must be an object."
        )

    return payload


def load_yaml(
    path: Path,
    description: str,
) -> dict[str, Any]:
    if not path.is_file():
        raise TestPlanCompilationError(
            f"{description} not found: {path}"
        )

    try:
        payload = yaml.safe_load(
            path.read_text(
                encoding="utf-8"
            )
        )
    except OSError as exc:
        raise TestPlanCompilationError(
            f"Unable to read {description}: {exc}"
        ) from exc
    except yaml.YAMLError as exc:
        raise TestPlanCompilationError(
            f"Invalid YAML in {description}: {exc}"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise TestPlanCompilationError(
            f"{description} root must be an object."
        )

    return payload


def require_mapping(
    value: Any,
    context: str,
) -> dict[str, Any]:
    if not isinstance(
        value,
        dict,
    ):
        raise TestPlanCompilationError(
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
        raise TestPlanCompilationError(
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
        raise TestPlanCompilationError(
            f"{context}.{key} must be a string."
        )

    value = value.strip()

    if not value:
        raise TestPlanCompilationError(
            f"{context}.{key} must not be empty."
        )

    return value


def normalize_name(
    value: str,
) -> str:
    normalized = re.sub(
        r"[^A-Za-z0-9._-]+",
        "-",
        value.strip(),
    ).strip("-._")

    if not normalized:
        raise TestPlanCompilationError(
            "Scenario name becomes empty after normalization."
        )

    return normalized


def parse_target(
    target: str,
    context: str,
) -> tuple[
    str,
    str,
    int,
    str,
]:
    parsed = urlparse(
        target
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
        raise TestPlanCompilationError(
            f"{context}.target must use http or https."
        )

    if not parsed.hostname:
        raise TestPlanCompilationError(
            f"{context}.target must contain a valid host."
        )

    if (
        parsed.username
        or parsed.password
    ):
        raise TestPlanCompilationError(
            f"{context}.target must not embed credentials."
        )

    try:
        port = (
            parsed.port
            if parsed.port is not None
            else (
                443
                if protocol == "https"
                else 80
            )
        )
    except ValueError as exc:
        raise TestPlanCompilationError(
            f"{context}.target contains an invalid port."
        ) from exc

    if not 1 <= port <= 65535:
        raise TestPlanCompilationError(
            f"{context}.target port must be between 1 and 65535."
        )

    path = (
        parsed.path
        or "/"
    )

    if parsed.query:
        path = (
            path
            + "?"
            + parsed.query
        )

    return (
        protocol,
        parsed.hostname,
        port,
        path,
    )


def normalize_expected_status(
    value: Any,
    context: str,
) -> int:
    if value is None:
        values = [
            200
        ]
    elif isinstance(
        value,
        list,
    ):
        values = value
    else:
        values = [
            value
        ]

    statuses: list[int] = []

    for item in values:
        try:
            status = int(
                item
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise TestPlanCompilationError(
                f"{context}.expected_status "
                f"contains invalid value: {item}"
            ) from exc

        if not 100 <= status <= 599:
            raise TestPlanCompilationError(
                f"{context}.expected_status "
                f"is outside HTTP range: {status}"
            )

        if status not in statuses:
            statuses.append(
                status
            )

    if len(statuses) != 1:
        raise TestPlanCompilationError(
            f"{context} declares multiple expected statuses "
            f"{statuses}. The current governed test-plan "
            "contract supports exactly one expected_status "
            "per transaction."
        )

    return statuses[0]


def serialize_body(
    value: Any,
    context: str,
) -> str | None:
    if value is None:
        return None

    if isinstance(
        value,
        (
            dict,
            list,
        ),
    ):
        return json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
        )

    if isinstance(
        value,
        str,
    ):
        if not value.strip():
            raise TestPlanCompilationError(
                f"{context}.body must not be empty."
            )

        return value

    raise TestPlanCompilationError(
        f"{context}.body must be an object, array or string."
    )


def compile_transactions(
    normalized: dict[str, Any],
) -> tuple[
    str,
    list[dict[str, Any]],
    dict[str, Any],
]:
    scenarios = require_list(
        normalized.get(
            "scenarios",
            [],
        ),
        "scenarios",
    )

    if len(scenarios) != 1:
        raise TestPlanCompilationError(
            "Exactly one scenario is required per governed test plan."
        )

    scenario = require_mapping(
        scenarios[0],
        "scenarios[0]",
    )

    scenario_name = normalize_name(
        require_text(
            scenario,
            "name",
            "scenarios[0]",
        )
    )

    raw_transactions = require_list(
        scenario.get(
            "transactions",
            [],
        ),
        "scenarios[0].transactions",
    )

    if not raw_transactions:
        raise TestPlanCompilationError(
            "At least one transaction is required."
        )

    result: list[
        dict[str, Any]
    ] = []

    names: set[str] = set()

    root_targets: set[
        tuple[str, str, int]
    ] = set()

    for index, raw in enumerate(
        raw_transactions
    ):
        context = (
            f"scenarios[0].transactions[{index}]"
        )

        transaction = require_mapping(
            raw,
            context,
        )

        name = require_text(
            transaction,
            "name",
            context,
        )

        if name in names:
            raise TestPlanCompilationError(
                f"Duplicate transaction name: {name}"
            )

        names.add(
            name
        )

        method = require_text(
            transaction,
            "method",
            context,
        ).upper()

        if method not in SUPPORTED_HTTP_METHODS:
            raise TestPlanCompilationError(
                f"{context}.method unsupported: {method}"
            )

        target = require_text(
            transaction,
            "target",
            context,
        )

        (
            protocol,
            host,
            port,
            path,
        ) = parse_target(
            target,
            context,
        )

        root_targets.add(
            (
                protocol,
                host,
                port,
            )
        )

        output: dict[
            str,
            Any
        ] = {
            "name": name,
            "method": method,
            "path": path,
            "expected_status": (
                normalize_expected_status(
                    transaction.get(
                        "expected_status"
                    ),
                    context,
                )
            ),
        }

        headers = transaction.get(
            "headers"
        )

        if headers is not None:
            if not isinstance(
                headers,
                dict,
            ):
                raise TestPlanCompilationError(
                    f"{context}.headers must be an object."
                )

            output[
                "headers"
            ] = {
                str(key): str(value)
                for key, value in headers.items()
            }

        body = serialize_body(
            transaction.get(
                "body"
            ),
            context,
        )

        if body is not None:
            output[
                "body"
            ] = body

        result.append(
            output
        )

    if len(root_targets) != 1:
        raise TestPlanCompilationError(
            "The current governed test-plan schema supports "
            "one root target only. "
            f"The normalized scenario contains "
            f"{len(root_targets)} distinct targets."
        )

    (
        protocol,
        host,
        port,
    ) = next(
        iter(
            root_targets
        )
    )

    root_target = {
        "protocol": protocol,
        "host": host,
        "port": port,
        "base_path": "",
    }

    return (
        scenario_name,
        result,
        root_target,
    )


def compile_correlations(
    normalized: dict[str, Any],
    transaction_names: set[str],
) -> dict[str, Any]:
    runtime = normalized.get(
        "runtime",
        {},
    )

    if runtime is None:
        runtime = {}

    runtime = require_mapping(
        runtime,
        "runtime",
    )

    raw_correlations = require_list(
        runtime.get(
            "correlations",
            [],
        ),
        "runtime.correlations",
    )

    extractors = []

    for index, raw in enumerate(
        raw_correlations
    ):
        context = (
            f"runtime.correlations[{index}]"
        )

        item = require_mapping(
            raw,
            context,
        )

        extractor_type = str(
            item.get(
                "type",
                "",
            )
        ).strip().upper()

        if (
            extractor_type
            not in SUPPORTED_EXTRACTOR_TYPES
        ):
            raise TestPlanCompilationError(
                f"{context}.type unsupported: "
                f"{extractor_type}"
            )

        name = str(
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

        if not name:
            raise TestPlanCompilationError(
                f"{context} requires variable/name."
            )

        if not expression:
            raise TestPlanCompilationError(
                f"{context} requires expression."
            )

        if (
            source_transaction
            not in transaction_names
        ):
            raise TestPlanCompilationError(
                f"{context} references unknown transaction: "
                f"{source_transaction}"
            )

        extractors.append(
            {
                "name": name,
                "source_transaction": (
                    source_transaction
                ),
                "type": extractor_type,
                "expression": expression,
                "fallback": "NOT_FOUND",
            }
        )

    return {
        "description": (
            "Runtime correlations derived from "
            "the normalized scenario."
            if extractors
            else (
                "No runtime correlations are declared "
                "for this scenario."
            )
        ),
        "extractors": extractors,
    }


def compile_authentication(
    transactions: list[dict[str, Any]],
    correlations: dict[str, Any],
) -> dict[str, Any]:
    authorization_values: list[str] = []

    for transaction in transactions:
        headers = transaction.get(
            "headers",
            {},
        )

        if not isinstance(
            headers,
            dict,
        ):
            continue

        for key, value in headers.items():
            if (
                str(key)
                .strip()
                .lower()
                == "authorization"
            ):
                authorization_values.append(
                    str(value)
                )

    if not authorization_values:
        return {
            "type": "NONE",
            "description": (
                "No Authorization header is declared "
                "by the normalized scenario."
            ),
        }

    correlation_names = {
        item.get(
            "name"
        )
        for item in correlations.get(
            "extractors",
            []
        )
        if isinstance(
            item,
            dict,
        )
    }

    for value in authorization_values:
        for name in correlation_names:
            if (
                name
                and f"${{{name}}}" in value
            ):
                return {
                    "type": "RUNTIME_TOKEN",
                    "description": (
                        "Authorization is populated "
                        "from a runtime correlation."
                    ),
                }

    return {
        "type": "DECLARED_HEADER",
        "description": (
            "An Authorization header is declared. "
            "The authentication protocol is not inferred."
        ),
    }


def compile_workload(
    profile: dict[str, Any],
) -> dict[str, Any]:
    execution = require_mapping(
        profile.get(
            "execution"
        ),
        "execution-profile.execution",
    )

    mode = str(
        execution.get(
            "mode",
            "",
        )
    ).strip().upper()

    if mode != "DURATION":
        raise TestPlanCompilationError(
            "Current governed plan compilation "
            "supports DURATION workload only."
        )

    try:
        threads = int(
            execution[
                "threads"
            ]
        )

        ramp = int(
            execution.get(
                "ramp_time_seconds",
                0,
            )
        )

        duration = int(
            execution[
                "duration_seconds"
            ]
        )

        pacing = float(
            execution.get(
                "pacing_seconds",
                0.0,
            )
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise TestPlanCompilationError(
            "Invalid execution profile workload."
        ) from exc

    if threads <= 0:
        raise TestPlanCompilationError(
            "execution.threads must be > 0."
        )

    if ramp < 0:
        raise TestPlanCompilationError(
            "execution.ramp_time_seconds must be >= 0."
        )

    if duration <= 0:
        raise TestPlanCompilationError(
            "execution.duration_seconds must be > 0."
        )

    if pacing < 0:
        raise TestPlanCompilationError(
            "execution.pacing_seconds must be >= 0."
        )

    return {
        "type": "DURATION",
        "status": "PROPOSED",
        "parameters": {
            "threads": threads,
            "ramp_time_seconds": ramp,
            "duration_seconds": duration,
            "pacing_seconds": pacing,
        },
        "description": (
            "Workload derived from the governed "
            "execution profile. Human approval is "
            "required before execution."
        ),
    }


def find_numeric(
    payload: Any,
    names: tuple[str, ...],
) -> float | int | None:
    if isinstance(
        payload,
        dict,
    ):
        for name in names:
            if name in payload:
                value = payload[
                    name
                ]

                if isinstance(
                    value,
                    (
                        int,
                        float,
                    ),
                ):
                    return value

        for child in payload.values():
            found = find_numeric(
                child,
                names,
            )

            if found is not None:
                return found

    elif isinstance(
        payload,
        list,
    ):
        for child in payload:
            found = find_numeric(
                child,
                names,
            )

            if found is not None:
                return found

    return None


def compile_sla(
    sla_payload: dict[str, Any],
) -> dict[str, Any]:
    error_rate = find_numeric(
        sla_payload,
        (
            "error_rate_threshold_pct",
            "max_error_rate_pct",
        ),
    )

    p95 = find_numeric(
        sla_payload,
        (
            "p95_threshold_ms",
            "max_p95_ms",
        ),
    )

    p99 = find_numeric(
        sla_payload,
        (
            "p99_threshold_ms",
            "max_p99_ms",
        ),
    )

    throughput = find_numeric(
        sla_payload,
        (
            "min_throughput_req_per_sec",
            "minimum_throughput_req_per_sec",
        ),
    )

    missing = []

    if error_rate is None:
        missing.append(
            "error_rate_threshold_pct"
        )

    if p95 is None:
        missing.append(
            "p95_threshold_ms"
        )

    if p99 is None:
        missing.append(
            "p99_threshold_ms"
        )

    if throughput is None:
        missing.append(
            "min_throughput_req_per_sec"
        )

    if missing:
        raise TestPlanCompilationError(
            "SLA configuration is missing required values: "
            + ", ".join(
                missing
            )
        )

    return {
        "error_rate_threshold_pct": error_rate,
        "p95_threshold_ms": p95,
        "p99_threshold_ms": p99,
        "min_throughput_req_per_sec": throughput,
        "source": "config/sla.json",
    }


def compile_data_requirements(
    normalized: dict[str, Any],
    *,
    scenario_name: str,
    plan_status: str,
) -> dict[str, Any]:
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

    parameters = require_list(
        data.get(
            "parameters",
            [],
        ),
        "data.parameters",
    )

    fields = []
    secrets = []

    for index, raw in enumerate(
        parameters
    ):
        context = (
            f"data.parameters[{index}]"
        )

        item = require_mapping(
            raw,
            context,
        )

        name = require_text(
            item,
            "name",
            context,
        )

        sensitive = bool(
            item.get(
                "sensitive",
                False,
            )
        )

        source = str(
            item.get(
                "source",
                "RUNTIME",
            )
        ).strip().upper()

        parameter_type = str(
            item.get(
                "type",
                "STRING",
            )
        ).strip().upper()

        if sensitive:
            secrets.append(
                {
                    "name": name,
                    "source": "JMETER_PROPERTY",
                    "required": True,
                }
            )
        else:
            fields.append(
                {
                    "name": name,
                    "type": parameter_type,
                    "source": source,
                    "required": True,
                }
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "scenario": scenario_name,
        "status": plan_status,
        "strategy": (
            "PARAMETERIZED"
            if parameters
            else "NONE"
        ),
        "fields": fields,
        "secrets": secrets,
    }


def compile_plan_data(
    requirements_path: Path,
    requirements: dict[str, Any],
) -> dict[str, Any]:
    fields = []

    for item in requirements.get(
        "fields",
        [],
    ):
        fields.append(
            {
                "name": item[
                    "name"
                ],
                "type": item.get(
                    "type",
                    "STRING",
                ),
                "description": (
                    "Runtime parameter declared "
                    "by the normalized scenario."
                ),
            }
        )

    for item in requirements.get(
        "secrets",
        [],
    ):
        fields.append(
            {
                "name": item[
                    "name"
                ],
                "type": "STRING",
                "description": (
                    "Sensitive runtime parameter "
                    "provided as external JMeter property."
                ),
            }
        )

    return {
        "requirements_file": str(
            requirements_path
        ),
        "source_type": requirements.get(
            "strategy",
            "NONE",
        ),
        "fields": fields,
    }


def compile_observability(
    profile: dict[str, Any],
) -> dict[str, Any]:
    observability = profile.get(
        "observability",
        {},
    )

    if not isinstance(
        observability,
        dict,
    ):
        observability = {}

    prometheus_port = observability.get(
        "prometheus_port",
        9270,
    )

    return {
        "metrics": [
            {
                "source": "JMeter Prometheus Listener",
                "endpoint": (
                    "http://localhost:"
                    f"{prometheus_port}/metrics"
                ),
            },
            {
                "source": "Prometheus",
                "url": "http://localhost:9090",
            },
            {
                "source": "Grafana",
                "url": "http://localhost:3000",
            },
        ],
        "gaps": [
            (
                "Application-side infrastructure metrics "
                "are not inferred automatically from the input."
            )
        ],
    }


def build_plan(
    *,
    normalized: dict[str, Any],
    profile: dict[str, Any],
    sla_payload: dict[str, Any],
    requirements_path: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
]:
    if (
        str(
            normalized.get(
                "schema_version",
                "",
            )
        ).strip()
        != SCHEMA_VERSION
    ):
        raise TestPlanCompilationError(
            "Unsupported normalized model schema_version."
        )

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

    if source_type != "CLI":
        raise TestPlanCompilationError(
            "This compiler handles normalized CLI/API "
            "models only. Postman and JMX preserve their "
            "existing workflow paths."
        )

    system = require_mapping(
        normalized.get(
            "system"
        ),
        "system",
    )

    if (
        str(
            system.get(
                "type",
                "",
            )
        ).strip().upper()
        != "API"
    ):
        raise TestPlanCompilationError(
            "Normalized CLI plan compilation "
            "currently supports API scenarios only."
        )

    (
        scenario_name,
        transactions,
        target,
    ) = compile_transactions(
        normalized
    )

    transaction_names = {
        item[
            "name"
        ]
        for item in transactions
    }

    correlations = compile_correlations(
        normalized,
        transaction_names,
    )

    authentication = compile_authentication(
        transactions,
        correlations,
    )

    workload = compile_workload(
        profile
    )

    plan_status = "DRAFT"

    requirements = compile_data_requirements(
        normalized,
        scenario_name=scenario_name,
        plan_status=plan_status,
    )

    requirements["scenario_candidate"] = {
        "id": scenario_name,
        "type": (
            "SINGLE_REQUEST"
            if len(transactions) == 1
            else "MULTI_REQUEST"
        ),
    }

    plan = {
        "metadata": {
            "name": scenario_name,
            "version": "1.0",
            "description": (
                "Governed performance test plan generated "
                "deterministically from the normalized "
                "performance model."
            ),
            "created_at": date.today().isoformat(),
            "author": "AI Performance Engineering Platform",
        },
        "status": plan_status,
        "objective": (
            "Evaluate the declared scenario under the "
            "proposed controlled workload and collect "
            "performance evidence without exceeding "
            "approved execution parameters."
        ),
        "system": {
            "type": "API",
            "name": target[
                "host"
            ],
        },
        "environment": "demo",
        "target": target,
        "authentication": authentication,
        "workload": workload,
        "sla": compile_sla(
            sla_payload
        ),
        "data": compile_plan_data(
            requirements_path,
            requirements,
        ),
        "transactions": transactions,
        "correlations": correlations,
        "assertions": [
            {
                "type": "RESPONSE_CODE",
                "expected_value": str(
                    transaction[
                        "expected_status"
                    ]
                ),
                "description": (
                    "Validate expected HTTP response "
                    f"for transaction {transaction['name']}."
                ),
            }
            for transaction in transactions
        ],
        "observability": compile_observability(
            profile
        ),
        "risks": [
            {
                "category": "TARGET_CAPACITY",
                "description": (
                    "Target capacity and throttling limits "
                    "are not inferred automatically."
                ),
                "impact": "MEDIUM",
                "mitigation": (
                    "Use only the approved workload and "
                    "monitor latency, throughput and errors."
                ),
            }
        ],
        "authorization": {
            "required": True,
            "status": "PENDING",
            "authorized_by": None,
            "authorized_at": None,
            "notes": (
                "Execution authorization is pending "
                "human approval."
            ),
        },
        "open_questions": [],
        "approval": {
            "approved_by": None,
            "approved_at": None,
            "scope": "DESIGN_AND_WORKLOAD",
            "execution_authorized": False,
        },
    }

    return (
        plan,
        requirements,
    )



def render_test_plan_markdown(
    plan: dict[str, Any],
) -> str:
    """Render a human-readable review artifact from the canonical plan.

    YAML remains the source of truth. Markdown is derived from it and
    must never introduce independent state.
    """

    metadata = plan["metadata"]
    workload = plan["workload"]
    parameters = workload["parameters"]
    target = plan["target"]
    authorization = plan["authorization"]
    authentication = plan["authentication"]

    lines: list[str] = [
        f"# Performance Test Plan - {metadata['name']}",
        "",
        "## Plan Status",
        "",
        f"- Scenario: `{metadata['name']}`",
        f"- Status: `{plan['status']}`",
        f"- Workload status: `{workload['status']}`",
        f"- Authorization status: `{authorization['status']}`",
        f"- Version: `{metadata.get('version', '1.0')}`",
        "",
        "## Objective",
        "",
        str(plan.get("objective", "")),
        "",
        "## Target",
        "",
        f"- Protocol: `{target['protocol']}`",
        f"- Host: `{target['host']}`",
        f"- Port: `{target['port']}`",
        f"- Base path: `{target.get('base_path', '')}`",
        "",
        "## Authentication",
        "",
        f"- Type: `{authentication.get('type', 'NONE')}`",
        f"- Description: {authentication.get('description', '')}",
        "",
        "## Proposed Workload",
        "",
        f"- Users / threads: `{parameters['threads']}`",
        f"- Ramp-up: `{parameters['ramp_time_seconds']} s`",
        f"- Duration: `{parameters['duration_seconds']} s`",
        f"- Pacing: `{parameters['pacing_seconds']} s`",
        "",
        "## Transactions",
        "",
    ]

    for index, transaction in enumerate(
        plan.get("transactions", []),
        start=1,
    ):
        lines.extend(
            [
                f"### {index}. {transaction['name']}",
                "",
                f"- Method: `{transaction['method']}`",
                f"- Path: `{transaction['path']}`",
                (
                    "- Expected status: "
                    f"`{transaction['expected_status']}`"
                ),
            ]
        )

        headers = transaction.get(
            "headers",
            {},
        )

        if headers:
            lines.extend(
                [
                    "- Headers:",
                ]
            )

            for name, value in headers.items():
                safe_value = str(value)

                # Do not render literal secret values.
                if (
                    str(name).strip().lower()
                    == "authorization"
                ):
                    if "${" not in safe_value:
                        safe_value = "<REDACTED>"

                lines.append(
                    f"  - `{name}: {safe_value}`"
                )

        if transaction.get("body"):
            lines.extend(
                [
                    "- Body: declared in canonical YAML plan.",
                ]
            )

        lines.append("")

    correlations = plan.get(
        "correlations",
        {},
    )

    lines.extend(
        [
            "## Correlations",
            "",
            str(
                correlations.get(
                    "description",
                    "No correlations declared.",
                )
            ),
            "",
        ]
    )

    for extractor in correlations.get(
        "extractors",
        [],
    ):
        lines.extend(
            [
                (
                    f"- `{extractor['name']}` from "
                    f"`{extractor['source_transaction']}` "
                    f"using `{extractor['type']}` "
                    f"`{extractor['expression']}`"
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## SLA",
            "",
        ]
    )

    sla = plan.get(
        "sla",
        {},
    )

    for key, value in sla.items():
        lines.append(
            f"- {key}: `{value}`"
        )

    lines.extend(
        [
            "",
            "## Observability",
            "",
        ]
    )

    for metric in (
        plan.get(
            "observability",
            {}
        ).get(
            "metrics",
            []
        )
    ):
        location = (
            metric.get("endpoint")
            or metric.get("url")
            or ""
        )

        lines.append(
            f"- {metric.get('source', 'Unknown')}: {location}"
        )

    lines.extend(
        [
            "",
            "## Governance",
            "",
            (
                "- Human design/workload approval: "
                f"`{'REQUIRED' if plan['status'] == 'DRAFT' else 'COMPLETE'}`"
            ),
            (
                "- Execution authorization: "
                f"`{authorization['status']}`"
            ),
            "",
            (
                "This Markdown document is generated from "
                "`test-plan.yaml`. The YAML plan remains the "
                "canonical governed artifact."
            ),
            "",
        ]
    )

    return "\n".join(lines)


def write_text_atomic(
    path: Path,
    content: str,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    try:
        temporary.write_text(
            content,
            encoding="utf-8",
        )

        if not temporary.read_text(
            encoding="utf-8"
        ).strip():
            raise TestPlanCompilationError(
                "Serialized Markdown test plan is empty."
            )

        temporary.replace(
            path
        )

    except Exception:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass

        raise



def write_yaml_atomic(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    try:
        temporary.write_text(
            yaml.safe_dump(
                payload,
                sort_keys=False,
                allow_unicode=True,
                width=1000,
            ),
            encoding="utf-8",
        )

        validation = yaml.safe_load(
            temporary.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(
            validation,
            dict,
        ):
            raise TestPlanCompilationError(
                "Serialized test plan is invalid."
            )

        temporary.replace(
            path
        )

    except Exception:
        if temporary.exists():
            temporary.unlink()

        raise


def write_json_atomic(
    path: Path,
    payload: dict[str, Any],
) -> None:
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

        validation = json.loads(
            temporary.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(
            validation,
            dict,
        ):
            raise TestPlanCompilationError(
                "Serialized data requirements are invalid."
            )

        temporary.replace(
            path
        )

    except Exception:
        if temporary.exists():
            temporary.unlink()

        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compile a normalized CLI/API performance model "
            "into a governed DRAFT test plan."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--profile",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--sla",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--data-requirements",
        required=True,
        type=Path,
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    input_path = (
        args.input
        .expanduser()
        .resolve()
    )

    profile_path = (
        args.profile
        .expanduser()
        .resolve()
    )

    sla_path = (
        args.sla
        .expanduser()
        .resolve()
    )

    output_path = (
        args.output
        .expanduser()
        .resolve()
    )

    requirements_path = (
        args.data_requirements
        .expanduser()
        .resolve()
    )

    markdown_path = (
        output_path
        .with_suffix(".md")
    )

    try:
        normalized = load_json(
            input_path,
            "Normalized performance model",
        )

        profile = load_yaml(
            profile_path,
            "Execution profile",
        )

        sla_payload = load_json(
            sla_path,
            "SLA configuration",
        )

        (
            plan,
            requirements,
        ) = build_plan(
            normalized=normalized,
            profile=profile,
            sla_payload=sla_payload,
            requirements_path=requirements_path,
        )

        write_json_atomic(
            requirements_path,
            requirements,
        )

        write_yaml_atomic(
            output_path,
            plan,
        )

        write_text_atomic(
            markdown_path,
            render_test_plan_markdown(
                plan
            ),
        )

    except (
        TestPlanCompilationError,
        OSError,
        TypeError,
        ValueError,
        KeyError,
    ) as exc:
        print(
            "NORMALIZED TEST PLAN COMPILATION ERROR: "
            f"{exc}",
            file=sys.stderr,
        )
        return 2

    print("=" * 72)
    print("NORMALIZED CLI -> GOVERNED TEST PLAN")
    print("=" * 72)
    print(
        f"Input             : {input_path}"
    )
    print(
        f"Profile           : {profile_path}"
    )
    print(
        f"Plan              : {output_path}"
    )
    print(
        f"Data requirements : {requirements_path}"
    )
    print(
        f"Markdown          : {markdown_path}"
    )
    print(
        "Scenario          : "
        f"{plan['metadata']['name']}"
    )
    print(
        "Transactions      : "
        f"{len(plan['transactions'])}"
    )
    print(
        "Plan status       : "
        f"{plan['status']}"
    )
    print(
        "Workload status   : "
        f"{plan['workload']['status']}"
    )
    print(
        "Authorization     : "
        f"{plan['authorization']['status']}"
    )
    print("=" * 72)
    print("Human approval    : REQUIRED")
    print("JMeter            : NOT EXECUTED")
    print("=" * 72)
    print("GOVERNED TEST PLAN READY")

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
