#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    yaml = None


SUPPORTED_METHODS = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
}


class CliScenarioError(RuntimeError):
    pass


def load_document(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CliScenarioError(
            f"CLI scenario file does not exist: {path}"
        )

    suffix = path.suffix.lower()

    try:
        raw = path.read_text(
            encoding="utf-8"
        )
    except OSError as exc:
        raise CliScenarioError(
            f"Unable to read CLI scenario file: {exc}"
        ) from exc

    try:
        if suffix == ".json":
            data = json.loads(raw)
        elif suffix in {".yaml", ".yml"}:
            if yaml is None:
                raise CliScenarioError(
                    "PyYAML is required for YAML CLI scenarios."
                )
            data = yaml.safe_load(raw)
        else:
            raise CliScenarioError(
                "Structured CLI input must be .json, .yaml or .yml. "
                "Plain endpoint lists are ambiguous and are not accepted."
            )
    except (
        json.JSONDecodeError,
        yaml.YAMLError if yaml else Exception,
    ) as exc:
        raise CliScenarioError(
            f"Invalid structured CLI document: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise CliScenarioError(
            "CLI scenario root must be an object."
        )

    return data


def require_text(
    obj: dict[str, Any],
    key: str,
    context: str,
) -> str:
    value = obj.get(key)

    if not isinstance(value, str) or not value.strip():
        raise CliScenarioError(
            f"{context}.{key} must be a non-empty string."
        )

    return value.strip()


def normalize_expected_status(
    value: Any,
) -> list[int]:
    if value is None:
        raise CliScenarioError(
            "Expected HTTP status is not declared. "
            "An explicit response contract is required."
        )

    values = (
        value
        if isinstance(value, list)
        else [value]
    )

    result: list[int] = []

    for item in values:
        try:
            status = int(item)
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise CliScenarioError(
                f"Invalid expected HTTP status: {item}"
            ) from exc

        if not 100 <= status <= 599:
            raise CliScenarioError(
                f"HTTP status outside valid range: {status}"
            )

        result.append(status)

    return result


def validate_base_url(
    base_url: str,
) -> str:
    parsed = urlparse(base_url)

    if parsed.scheme not in {"http", "https"}:
        raise CliScenarioError(
            "scenario.base_url must use http or https."
        )

    if not parsed.netloc:
        raise CliScenarioError(
            "scenario.base_url must include a host."
        )

    return base_url.rstrip("/")


def normalize_transaction(
    raw: dict[str, Any],
    index: int,
    base_url: str,
) -> dict[str, Any]:
    context = f"transactions[{index}]"

    name = require_text(
        raw,
        "name",
        context,
    )

    method = require_text(
        raw,
        "method",
        context,
    ).upper()

    if method not in SUPPORTED_METHODS:
        raise CliScenarioError(
            f"{context}.method unsupported: {method}"
        )

    path = require_text(
        raw,
        "path",
        context,
    )

    if path.startswith(
        ("http://", "https://")
    ):
        target = path
    else:
        if not path.startswith("/"):
            path = "/" + path

        target = base_url + path

    headers = raw.get(
        "headers",
        {},
    )

    if not isinstance(headers, dict):
        raise CliScenarioError(
            f"{context}.headers must be an object."
        )

    extractors = raw.get(
        "extractors",
        [],
    )

    if not isinstance(extractors, list):
        raise CliScenarioError(
            f"{context}.extractors must be a list."
        )

    normalized_extractors = []

    for extractor_index, extractor in enumerate(
        extractors
    ):
        if not isinstance(extractor, dict):
            raise CliScenarioError(
                f"{context}.extractors[{extractor_index}] "
                "must be an object."
            )

        extractor_type = require_text(
            extractor,
            "type",
            f"{context}.extractors[{extractor_index}]",
        ).upper()

        variable = require_text(
            extractor,
            "variable",
            f"{context}.extractors[{extractor_index}]",
        )

        expression = require_text(
            extractor,
            "expression",
            f"{context}.extractors[{extractor_index}]",
        )

        if extractor_type not in {
            "JSON_PATH",
            "REGEX",
        }:
            raise CliScenarioError(
                f"Unsupported extractor type: {extractor_type}"
            )

        normalized_extractors.append(
            {
                "type": extractor_type,
                "variable": variable,
                "expression": expression,
                "transaction": name,
            }
        )

    result: dict[str, Any] = {
        "name": name,
        "method": method,
        "target": target,
        "path": path,
        "headers": headers,
        "expected_status": normalize_expected_status(
            raw.get("expected_status")
        ),
    }

    if "body" in raw:
        result["body"] = raw["body"]

    if normalized_extractors:
        result["extractors"] = normalized_extractors

    return result


def build_model(
    document: dict[str, Any],
    source_path: Path,
) -> dict[str, Any]:
    schema_version = str(
        document.get(
            "schema_version",
            "1.0",
        )
    )

    if schema_version != "1.0":
        raise CliScenarioError(
            f"Unsupported schema_version: {schema_version}"
        )

    scenario = document.get(
        "scenario"
    )

    if not isinstance(
        scenario,
        dict,
    ):
        raise CliScenarioError(
            "scenario must be an object."
        )

    scenario_name = require_text(
        scenario,
        "name",
        "scenario",
    )

    base_url = validate_base_url(
        require_text(
            scenario,
            "base_url",
            "scenario",
        )
    )

    raw_transactions = document.get(
        "transactions"
    )

    if (
        not isinstance(raw_transactions, list)
        or not raw_transactions
    ):
        raise CliScenarioError(
            "transactions must contain at least one operation."
        )

    transactions = []
    correlations = []

    for index, raw in enumerate(
        raw_transactions
    ):
        if not isinstance(raw, dict):
            raise CliScenarioError(
                f"transactions[{index}] must be an object."
            )

        transaction = normalize_transaction(
            raw,
            index,
            base_url,
        )

        correlations.extend(
            transaction.pop(
                "extractors",
                [],
            )
        )

        transactions.append(
            transaction
        )

    parameters = document.get(
        "parameters",
        [],
    )

    if not isinstance(parameters, list):
        raise CliScenarioError(
            "parameters must be a list."
        )

    findings = document.get(
        "findings",
        [],
    )

    if not isinstance(findings, list):
        raise CliScenarioError(
            "findings must be a list."
        )

    return {
        "schema_version": "1.0",
        "source": {
            "type": "CLI",
            "artifact": str(
                source_path
            ),
            "format": "STRUCTURED",
        },
        "system": {
            "type": "API",
            "base_url": base_url,
        },
        "scenarios": [
            {
                "name": scenario_name,
                "transactions": transactions,
            }
        ],
        "data": {
            "strategy": (
                "PARAMETERIZED"
                if parameters
                else "NONE_OR_PARAMETERIZED"
            ),
            "csv_data_sets": [],
            "parameters": parameters,
        },
        "runtime": {
            "correlations": correlations,
        },
        "workload": {
            "source": "EXECUTION_PROFILE",
            "thread_groups": [],
        },
        "assertions": [],
        "observability": [],
        "risks": [],
        "findings": findings,
        "summary": {
            "transaction_count": len(
                transactions
            ),
            "correlation_count": len(
                correlations
            ),
            "parameter_count": len(
                parameters
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Parse a deterministic structured CLI/API "
            "performance scenario."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
    )

    parser.add_argument(
        "--output",
        required=True,
    )

    args = parser.parse_args()

    source = (
        Path(args.input)
        .expanduser()
        .resolve()
    )

    output = (
        Path(args.output)
        .expanduser()
        .resolve()
    )

    try:
        document = load_document(
            source
        )

        model = build_model(
            document,
            source,
        )

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output.write_text(
            json.dumps(
                model,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    except CliScenarioError as exc:
        print(
            f"CLI SCENARIO ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print("=" * 72)
    print("STRUCTURED CLI SCENARIO")
    print("=" * 72)
    print(
        f"Input        : {source}"
    )
    print(
        f"Scenario     : "
        f"{model['scenarios'][0]['name']}"
    )
    print(
        f"Transactions : "
        f"{model['summary']['transaction_count']}"
    )
    print(
        f"Correlations : "
        f"{model['summary']['correlation_count']}"
    )
    print(
        f"Output       : {output}"
    )
    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
