#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SUPPORTED_SOURCE_TYPES = {
    "POSTMAN",
    "JMX",
    "CLI",
}


class ModelValidationError(RuntimeError):
    pass


def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8",
            )
        )
    except FileNotFoundError as exc:
        raise ModelValidationError(
            f"File not found: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ModelValidationError(
            f"Invalid JSON: line {exc.lineno}, "
            f"column {exc.colno}"
        ) from exc

    if not isinstance(data, dict):
        raise ModelValidationError(
            "Root must be a JSON object."
        )

    return data


def require(
    obj: dict[str, Any],
    key: str,
    expected: type,
) -> Any:
    if key not in obj:
        raise ModelValidationError(
            f"Missing field: {key}"
        )

    value = obj[key]

    if not isinstance(
        value,
        expected,
    ):
        raise ModelValidationError(
            f"{key} must be "
            f"{expected.__name__}, "
            f"got {type(value).__name__}"
        )

    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate normalized performance model."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
    )
    parser.add_argument(
        "--strict",
        action="store_true",
    )
    args = parser.parse_args()

    path = (
        Path(args.input)
        .expanduser()
        .resolve()
    )

    try:
        data = load(path)

        if data.get(
            "schema_version"
        ) != "1.0":
            raise ModelValidationError(
                "Unsupported schema_version: "
                f"{data.get('schema_version')}"
            )

        source = require(
            data,
            "source",
            dict,
        )

        source_type = require(
            source,
            "type",
            str,
        )

        if (
            source_type
            not in SUPPORTED_SOURCE_TYPES
        ):
            raise ModelValidationError(
                "Unsupported source type: "
                f"{source_type}"
            )

        require(
            data,
            "system",
            dict,
        )

        scenarios = require(
            data,
            "scenarios",
            list,
        )

        if not scenarios:
            raise ModelValidationError(
                "At least one scenario is required."
            )

        for index, scenario in enumerate(
            scenarios
        ):
            if not isinstance(
                scenario,
                dict,
            ):
                raise ModelValidationError(
                    f"scenarios[{index}] "
                    "must be an object."
                )

            require(
                scenario,
                "name",
                str,
            )
            transactions = require(
                scenario,
                "transactions",
                list,
            )

            if not transactions:
                raise ModelValidationError(
                    f"Scenario "
                    f"'{scenario['name']}' "
                    "has no transactions."
                )

            for transaction_index, transaction in enumerate(
                transactions
            ):
                if not isinstance(
                    transaction,
                    dict,
                ):
                    raise ModelValidationError(
                        f"scenarios[{index}].transactions"
                        f"[{transaction_index}] must be an object."
                    )

                transaction_name = require(
                    transaction,
                    "name",
                    str,
                )

                if not transaction_name.strip():
                    raise ModelValidationError(
                        f"scenarios[{index}].transactions"
                        f"[{transaction_index}].name "
                        "must not be empty."
                    )

                if "method" in transaction:
                    method = require(
                        transaction,
                        "method",
                        str,
                    ).upper()

                    allowed_methods = {
                        "GET",
                        "POST",
                        "PUT",
                        "PATCH",
                        "DELETE",
                        "HEAD",
                        "OPTIONS",
                    }

                    if method not in allowed_methods:
                        raise ModelValidationError(
                            f"Unsupported HTTP method in "
                            f"scenarios[{index}].transactions"
                            f"[{transaction_index}]: {method}"
                        )

                cli_format = (
                    str(
                        source.get(
                            "format",
                            "",
                        )
                    )
                    .strip()
                    .upper()
                )

                strict_cli_formats = {
                    "STRUCTURED",
                    "LEGACY_SINGLE_TARGET",
                }

                if (
                    source_type == "CLI"
                    and cli_format in strict_cli_formats
                    and "method" not in transaction
                ):
                    raise ModelValidationError(
                        f"CLI transaction "
                        f"'{transaction_name}' "
                        "requires an explicit HTTP method."
                    )

                if (
                    source_type == "CLI"
                    and cli_format in strict_cli_formats
                    and not transaction.get("target")
                ):
                    raise ModelValidationError(
                        f"CLI transaction "
                        f"'{transaction_name}' "
                        "requires a target."
                    )

        require(data, "data", dict)
        require(data, "runtime", dict)
        require(data, "workload", dict)
        require(data, "assertions", list)
        require(data, "observability", list)
        require(data, "risks", list)

        findings = require(
            data,
            "findings",
            list,
        )

        error_findings = [
            item
            for item in findings
            if isinstance(item, dict)
            and str(
                item.get("severity", "")
            ).upper()
            == "ERROR"
        ]

        warning_findings = [
            item
            for item in findings
            if isinstance(item, dict)
            and str(
                item.get("severity", "")
            ).upper()
            == "WARNING"
        ]

        if error_findings:
            status = "FAIL"
        elif (
            args.strict
            and warning_findings
        ):
            status = "FAIL"
        else:
            status = "PASS"

    except ModelValidationError as exc:
        print("=" * 70)
        print(
            "NORMALIZED PERFORMANCE MODEL VALIDATION"
        )
        print("=" * 70)
        print("Status : FAIL")
        print(f"Error  : {exc}")
        print("=" * 70)
        return 2

    print("=" * 70)
    print(
        "NORMALIZED PERFORMANCE MODEL VALIDATION"
    )
    print("=" * 70)
    print(f"Status   : {status}")
    print(f"Source   : {source_type}")
    print(
        f"Scenarios: {len(scenarios)}"
    )
    print(
        f"Errors   : {len(error_findings)}"
    )
    print(
        f"Warnings : {len(warning_findings)}"
    )
    print("=" * 70)

    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
