#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


class PlanValidationError(RuntimeError):
    pass


REQUIRED_ROOT_KEYS = {
    "metadata",
    "status",
    "objective",
    "system",
    "environment",
    "target",
    "authentication",
    "workload",
    "sla",
    "data",
    "transactions",
    "observability",
    "risks",
    "authorization",
}


def load_plan(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PlanValidationError(f"Plan not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PlanValidationError(f"Invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise PlanValidationError("Plan root must be a YAML mapping.")
    return data


def require(mapping: dict[str, Any], key: str, context: str) -> Any:
    if key not in mapping:
        raise PlanValidationError(f"Missing required field: {context}.{key}")
    return mapping[key]


def validate_plan(plan: dict[str, Any], plan_path: Path) -> dict[str, Any]:
    missing = sorted(REQUIRED_ROOT_KEYS - set(plan))
    if missing:
        raise PlanValidationError(
            "Missing required root fields: " + ", ".join(missing)
        )

    metadata = require(plan, "metadata", "root")
    if not isinstance(metadata, dict):
        raise PlanValidationError("metadata must be a mapping.")
    scenario = str(require(metadata, "name", "metadata")).strip()
    if not scenario:
        raise PlanValidationError("metadata.name cannot be empty.")

    status = str(require(plan, "status", "root")).upper()
    if status not in {"DRAFT", "APPROVED"}:
        raise PlanValidationError("status must be DRAFT or APPROVED.")

    system = require(plan, "system", "root")
    if not isinstance(system, dict):
        raise PlanValidationError("system must be a mapping.")
    if str(require(system, "type", "system")).upper() not in {
        "API", "WEB", "MIXED", "EXISTING_JMX"
    }:
        raise PlanValidationError("Unsupported system.type.")

    target = require(plan, "target", "root")
    if not isinstance(target, dict):
        raise PlanValidationError("target must be a mapping.")
    protocol = str(require(target, "protocol", "target")).lower()
    if protocol not in {"http", "https"}:
        raise PlanValidationError("target.protocol must be http or https.")
    host = str(require(target, "host", "target")).strip()
    if not host or "://" in host or "/" in host:
        raise PlanValidationError("target.host must contain only the host.")
    port = int(require(target, "port", "target"))
    if not 1 <= port <= 65535:
        raise PlanValidationError("target.port must be between 1 and 65535.")

    workload = require(plan, "workload", "root")
    if not isinstance(workload, dict):
        raise PlanValidationError("workload must be a mapping.")
    workload_status = str(require(workload, "status", "workload")).upper()
    if workload_status not in {"PROPOSED", "APPROVED"}:
        raise PlanValidationError(
            "workload.status must be PROPOSED or APPROVED."
        )
    params = require(workload, "parameters", "workload")
    if not isinstance(params, dict):
        raise PlanValidationError("workload.parameters must be a mapping.")
    for key in ("threads", "ramp_time_seconds", "duration_seconds"):
        value = int(require(params, key, "workload.parameters"))
        if value < 1:
            raise PlanValidationError(f"{key} must be >= 1.")
    pacing = float(params.get("pacing_seconds", 0))
    if pacing < 0:
        raise PlanValidationError("pacing_seconds cannot be negative.")

    transactions = require(plan, "transactions", "root")
    if not isinstance(transactions, list) or not transactions:
        raise PlanValidationError("transactions must contain at least one item.")

    supported_methods = {
        "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"
    }
    for index, transaction in enumerate(transactions):
        if not isinstance(transaction, dict):
            raise PlanValidationError(
                f"transactions[{index}] must be a mapping."
            )
        method = str(
            require(transaction, "method", f"transactions[{index}]")
        ).upper()
        if method not in supported_methods:
            raise PlanValidationError(
                f"Unsupported HTTP method in transaction {index}: {method}"
            )
        path = str(
            require(transaction, "path", f"transactions[{index}]")
        )
        if not path.startswith("/"):
            raise PlanValidationError(
                f"transactions[{index}].path must start with '/'."
            )
        expected = int(
            require(transaction, "expected_status", f"transactions[{index}]")
        )
        if not 100 <= expected <= 599:
            raise PlanValidationError(
                f"transactions[{index}].expected_status is invalid."
            )

    authorization = require(plan, "authorization", "root")
    if not isinstance(authorization, dict):
        raise PlanValidationError("authorization must be a mapping.")
    auth_status = str(
        require(authorization, "status", "authorization")
    ).upper()
    if auth_status not in {"PENDING", "AUTHORIZED", "REJECTED"}:
        raise PlanValidationError(
            "authorization.status must be PENDING, AUTHORIZED or REJECTED."
        )

    data = require(plan, "data", "root")
    requirements_file = data.get("requirements_file")
    if requirements_file:
        req_path = Path(requirements_file)
        if not req_path.is_absolute():
            project_root = plan_path.resolve().parents[3]
            req_path = project_root / req_path
        if not req_path.is_file():
            raise PlanValidationError(
                f"Data requirements file not found: {req_path}"
            )
        try:
            json.loads(req_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PlanValidationError(
                f"Invalid data requirements JSON: {exc}"
            ) from exc

    warnings: list[str] = []
    if status == "APPROVED" and workload_status != "APPROVED":
        warnings.append(
            "Plan is APPROVED but workload is not APPROVED."
        )
    if auth_status == "AUTHORIZED" and status != "APPROVED":
        warnings.append(
            "Execution is AUTHORIZED while plan is not APPROVED."
        )
    if int(params["duration_seconds"]) < 300:
        warnings.append(
            "Duration is below 300 seconds; suitable for a short baseline/demo, "
            "not for sustained-capacity conclusions."
        )

    return {
        "scenario": scenario,
        "status": status,
        "workload_status": workload_status,
        "authorization_status": auth_status,
        "transaction_count": len(transactions),
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a structured Performance Test Plan."
    )
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        plan_path = args.plan.expanduser().resolve()
        plan = load_plan(plan_path)
        result = validate_plan(plan, plan_path)
    except (PlanValidationError, ValueError, TypeError) as exc:
        if args.json:
            print(json.dumps({"status": "INVALID", "error": str(exc)}, indent=2))
        else:
            print(f"PLAN INVALID: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"status": "VALID", **result}, indent=2))
    else:
        print("=" * 62)
        print("PERFORMANCE TEST PLAN VALIDATION")
        print("=" * 62)
        print(f"Scenario       : {result['scenario']}")
        print(f"Plan status    : {result['status']}")
        print(f"Workload       : {result['workload_status']}")
        print(f"Authorization  : {result['authorization_status']}")
        print(f"Transactions   : {result['transaction_count']}")
        if result["warnings"]:
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        else:
            print("Warnings       : none")
        print("=" * 62)
        print("PLAN VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
