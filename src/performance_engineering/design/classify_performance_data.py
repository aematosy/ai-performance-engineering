#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


SENSITIVE_PATTERN = re.compile(
    r"(password|passwd|pwd|secret|token|api[_-]?key|authorization|cookie|"
    r"client[_-]?secret|private[_-]?key|access[_-]?token|refresh[_-]?token)",
    re.IGNORECASE,
)

CONFIG_EXACT_HINTS = {
    "baseurl",
    "base_url",
    "url",
    "host",
    "hostname",
    "protocol",
    "port",
    "environment",
    "env",
    "tenant",
    "region",
    "namespace",
    "domain",
}

CONFIG_SUFFIX_HINTS = (
    "url",
    "_url",
    "baseurl",
    "base_url",
    "host",
    "hostname",
    "endpoint",
    "service",
    "microservice",
    "domain",
)

NON_DATA_KEYS = {
    "id",
    "uuid",
    "timestamp",
    "createdat",
    "updatedat",
}

VAR_PATTERN = re.compile(r"\{\{([^{}]+)\}\}")


class DataClassificationError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DataClassificationError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DataClassificationError(
            f"Invalid JSON in {path}: line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(data, dict):
        raise DataClassificationError("JSON root must be an object.")
    return data


def slug(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_").lower()
    return result or "value"


def normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "", value.strip().lower())


def is_sensitive(name: str) -> bool:
    return bool(SENSITIVE_PATTERN.search(name or ""))


def looks_like_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    v = value.strip().lower()
    return v.startswith(("http://", "https://"))


def is_configuration(name: str, value: Any = None) -> bool:
    n = normalized_name(name)

    if n in CONFIG_EXACT_HINTS:
        return True

    if any(n.endswith(suffix) for suffix in CONFIG_SUFFIX_HINTS):
        return True

    if looks_like_url(value):
        return True

    return False


def scalar_type(value: Any) -> str:
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int) and not isinstance(value, bool):
        return "INTEGER"
    if isinstance(value, float):
        return "NUMBER"
    if value is None:
        return "NULL"
    return "STRING"


def flatten_json_scalars(
    value: Any,
    *,
    prefix: list[str] | None = None,
) -> list[dict[str, Any]]:
    prefix = prefix or []
    result: list[dict[str, Any]] = []

    if isinstance(value, dict):
        for key, child in value.items():
            result.extend(
                flatten_json_scalars(
                    child,
                    prefix=[*prefix, str(key)],
                )
            )
        return result

    if isinstance(value, list):
        return result

    if not prefix:
        return result

    result.append(
        {
            "json_path": "$." + ".".join(prefix),
            "leaf_name": prefix[-1],
            "value": value,
            "type": scalar_type(value),
        }
    )
    return result


def parse_raw_json(body: dict[str, Any]) -> Any | None:
    if body.get("mode") != "raw":
        return None

    content = body.get("content")
    if not isinstance(content, dict):
        return None

    raw = content.get("raw")
    if not isinstance(raw, str):
        return None

    if raw == "<REDACTED>":
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def postman_runtime_names(data: dict[str, Any]) -> set[str]:
    variables = data.get("variables", {})
    if not isinstance(variables, dict):
        return set()

    runtime = variables.get("dynamic_runtime", [])
    if not isinstance(runtime, list):
        return set()

    return {str(item) for item in runtime if str(item).strip()}


def postman_declared_variables(
    data: dict[str, Any],
) -> list[dict[str, Any]]:
    variables = data.get("variables", {})
    if not isinstance(variables, dict):
        return []

    result: list[dict[str, Any]] = []

    for scope in ("collection", "environment"):
        values = variables.get(scope, [])
        if not isinstance(values, list):
            continue

        for item in values:
            if not isinstance(item, dict):
                continue

            name = str(item.get("name", "")).strip()
            if not name:
                continue

            result.append(
                {
                    "name": name,
                    "scope": scope.upper(),
                    "value": item.get("value"),
                    "sensitive": bool(item.get("sensitive", False))
                    or is_sensitive(name),
                }
            )

    return result


def unique_column_name(
    base_name: str,
    request_id: str | None,
    counts: Counter,
) -> str:
    if counts[base_name] == 1:
        return base_name

    prefix = slug((request_id or "request").replace("/", "_"))
    return f"{prefix}_{base_name}"


def classify_postman(
    data: dict[str, Any],
) -> dict[str, Any]:
    runtime_names = postman_runtime_names(data)
    declared = postman_declared_variables(data)

    configuration: list[dict[str, Any]] = []
    secrets: list[dict[str, Any]] = []
    runtime: list[dict[str, Any]] = []
    test_candidates: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    seen_runtime: set[str] = set()

    for variable in declared:
        name = variable["name"]
        value = variable.get("value")

        if name in runtime_names:
            if name not in seen_runtime:
                runtime.append(
                    {
                        "name": name,
                        "classification": "RUNTIME_CORRELATED",
                        "source": variable["scope"],
                        "parameterizable": False,
                    }
                )
                seen_runtime.add(name)
            continue

        if variable["sensitive"]:
            secrets.append(
                {
                    "name": name,
                    "classification": "SECRET",
                    "source": variable["scope"],
                    "parameterizable": False,
                    "value": "<REDACTED>",
                }
            )
            continue

        if is_configuration(name, value):
            configuration.append(
                {
                    "name": name,
                    "classification": "CONFIGURATION",
                    "source": variable["scope"],
                    "parameterizable": False,
                    "value": value,
                }
            )
            continue

        test_candidates.append(
            {
                "name": slug(name),
                "original_name": name,
                "classification": "TEST_DATA_CANDIDATE",
                "source": variable["scope"],
                "parameterizable": True,
                "type": scalar_type(value),
                "example_value": value,
            }
        )

    for name in sorted(runtime_names - seen_runtime):
        runtime.append(
            {
                "name": name,
                "classification": "RUNTIME_CORRELATED",
                "source": "POSTMAN_SCRIPT",
                "parameterizable": False,
            }
        )

    requests = data.get("requests", [])
    if not isinstance(requests, list):
        requests = []

    raw_candidates: list[dict[str, Any]] = []

    for request in requests:
        if not isinstance(request, dict):
            continue

        request_id = str(request.get("id", ""))
        body = request.get("body", {})
        if not isinstance(body, dict):
            body = {}

        parsed = parse_raw_json(body)
        if parsed is not None:
            for item in flatten_json_scalars(parsed):
                leaf = str(item["leaf_name"])
                base_name = slug(leaf)

                if is_sensitive(leaf):
                    findings.append(
                        {
                            "severity": "WARNING",
                            "code": "SENSITIVE_BODY_LITERAL",
                            "request_id": request_id,
                            "location": item["json_path"],
                            "message": (
                                "Sensitive-looking request-body value "
                                "was not proposed as CSV test data."
                            ),
                        }
                    )
                    continue

                if base_name in NON_DATA_KEYS:
                    continue

                raw_candidates.append(
                    {
                        "base_name": base_name,
                        "original_name": leaf,
                        "classification": "TEST_DATA_CANDIDATE",
                        "source": "REQUEST_BODY",
                        "request_id": request_id,
                        "location": item["json_path"],
                        "parameterizable": True,
                        "type": item["type"],
                        "example_value": item["value"],
                    }
                )

        for query_item in request.get("query", []):
            if not isinstance(query_item, dict):
                continue
            if query_item.get("disabled"):
                continue

            key = str(query_item.get("key", "")).strip()
            if not key or is_sensitive(key):
                continue

            value = query_item.get("value")

            if isinstance(value, str) and VAR_PATTERN.search(value):
                continue

            raw_candidates.append(
                {
                    "base_name": slug(key),
                    "original_name": key,
                    "classification": "TEST_DATA_CANDIDATE",
                    "source": "QUERY",
                    "request_id": request_id,
                    "location": f"query:{key}",
                    "parameterizable": True,
                    "type": scalar_type(value),
                    "example_value": value,
                }
            )

    counts = Counter(
        item["base_name"]
        for item in raw_candidates
    )

    for item in raw_candidates:
        base_name = item.pop("base_name")
        item["name"] = unique_column_name(
            base_name,
            item.get("request_id"),
            counts,
        )
        test_candidates.append(item)

    deduped_test: list[dict[str, Any]] = []
    seen_test: set[tuple[Any, ...]] = set()

    for item in test_candidates:
        key = (
            item.get("name"),
            item.get("request_id"),
            item.get("location"),
            item.get("source"),
        )
        if key in seen_test:
            continue
        seen_test.add(key)
        deduped_test.append(item)

    return {
        "schema_version": "1.1",
        "source_type": "POSTMAN",
        "classification": {
            "configuration": configuration,
            "test_data": deduped_test,
            "runtime_correlated": runtime,
            "secrets": secrets,
        },
        "findings": findings,
        "summary": {
            "configuration_count": len(configuration),
            "test_data_count": len(deduped_test),
            "runtime_correlated_count": len(runtime),
            "secret_count": len(secrets),
            "finding_count": len(findings),
        },
    }


def classify_common_model(
    data: dict[str, Any],
) -> dict[str, Any]:
    source = data.get("source", {})
    source_type = (
        str(source.get("type", "UNKNOWN"))
        if isinstance(source, dict)
        else "UNKNOWN"
    )

    test_data: list[dict[str, Any]] = []
    runtime: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    data_section = data.get("data", {})
    if isinstance(data_section, dict):
        for param in data_section.get("parameters", []):
            if not isinstance(param, dict):
                continue

            name = str(param.get("name", "")).strip()
            if not name:
                continue

            test_data.append(
                {
                    "name": slug(name),
                    "original_name": name,
                    "classification": "TEST_DATA_CANDIDATE",
                    "source": "NORMALIZED_MODEL",
                    "parameterizable": True,
                    "type": str(param.get("type", "STRING")),
                    "example_value": param.get("example_value"),
                }
            )

    runtime_section = data.get("runtime", {})
    if isinstance(runtime_section, dict):
        for corr in runtime_section.get("correlations", []):
            if not isinstance(corr, dict):
                continue

            variable = str(corr.get("variable", "")).strip()
            if variable:
                runtime.append(
                    {
                        "name": variable,
                        "classification": "RUNTIME_CORRELATED",
                        "source": source_type,
                        "parameterizable": False,
                    }
                )

    if (
        source_type == "JMX"
        and not test_data
        and isinstance(data_section, dict)
        and data_section.get("strategy") == "NONE_OR_EMBEDDED"
    ):
        findings.append(
            {
                "severity": "INFO",
                "code": "JMX_BODY_DATA_NOT_CLASSIFIED",
                "message": (
                    "No explicit normalized data parameters were available. "
                    "JMX request-body parameter discovery requires the "
                    "enhanced JMX body adapter planned for the next phase."
                ),
            }
        )

    return {
        "schema_version": "1.1",
        "source_type": source_type,
        "classification": {
            "configuration": [],
            "test_data": test_data,
            "runtime_correlated": runtime,
            "secrets": [],
        },
        "findings": findings,
        "summary": {
            "configuration_count": 0,
            "test_data_count": len(test_data),
            "runtime_correlated_count": len(runtime),
            "secret_count": 0,
            "finding_count": len(findings),
        },
    }


def classify(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("schema_version") == "2.0" and "requests" in data:
        return classify_postman(data)

    if data.get("schema_version") == "1.0" and "source" in data:
        return classify_common_model(data)

    raise DataClassificationError(
        "Unsupported input model. Expected normalized Postman v2 "
        "or normalized performance model v1."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Classify performance input data as CONFIGURATION, "
            "TEST_DATA_CANDIDATE, RUNTIME_CORRELATED, or SECRET."
        )
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()

    try:
        data = load_json(input_path)
        result = classify(data)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except DataClassificationError as exc:
        print(
            f"DATA CLASSIFICATION ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print("=" * 72)
    print("PERFORMANCE DATA CLASSIFICATION v1.1")
    print("=" * 72)
    print(f"Source type        : {result['source_type']}")
    print(
        "Configuration     :",
        result["summary"]["configuration_count"],
    )
    print(
        "Test data         :",
        result["summary"]["test_data_count"],
    )
    print(
        "Runtime correlated:",
        result["summary"]["runtime_correlated_count"],
    )
    print(
        "Secrets           :",
        result["summary"]["secret_count"],
    )
    print(
        "Findings          :",
        result["summary"]["finding_count"],
    )
    print(f"Output            : {output_path}")
    print("=" * 72)
    print("CLASSIFICATION COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
