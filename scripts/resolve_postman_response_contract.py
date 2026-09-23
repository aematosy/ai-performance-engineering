#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROPERTY_RE = re.compile(r"\$\{__P\(([^,}]+),?([^}]*)\)\}")
RUNTIME_RE = re.compile(r"\$\{([^{}]+)\}")


class ContractDiscoveryError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractDiscoveryError(f"JSON root must be an object: {path}")
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractDiscoveryError(f"YAML root must be a mapping: {path}")
    return value


def absolute_path(value: str, *, base: Path = ROOT) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def read_properties(path: Path | None) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value
    return values


def read_first_csv_row(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        row = next(reader, None)
    if row is None:
        raise ContractDiscoveryError(f"CSV has no data rows: {path}")
    return {str(k): "" if v is None else str(v) for k, v in row.items()}


def typed_value(raw: str, json_type: str) -> Any:
    kind = json_type.upper()
    if kind == "BOOLEAN":
        return raw.strip().lower() == "true"
    if kind == "INTEGER":
        return int(raw)
    if kind == "NUMBER":
        return float(raw)
    if kind == "NULL":
        return None
    return raw


def materialize_body(value: Any, csv_row: dict[str, str], properties: dict[str, str], runtime: dict[str, str]) -> Any:
    if isinstance(value, dict):
        if "__runtime_parameter__" in value:
            name = str(value["__runtime_parameter__"])
            if name not in csv_row:
                raise ContractDiscoveryError(f"CSV parameter is missing: {name}")
            return typed_value(csv_row[name], str(value.get("__json_type__", "STRING")))
        return {k: materialize_body(v, csv_row, properties, runtime) for k, v in value.items()}
    if isinstance(value, list):
        return [materialize_body(v, csv_row, properties, runtime) for v in value]
    if isinstance(value, str):
        return substitute(value, properties, runtime)
    return value


def substitute(value: str, properties: dict[str, str], runtime: dict[str, str]) -> str:
    def property_repl(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        default = match.group(2)
        resolved = properties.get(name, default)
        if resolved == "":
            raise ContractDiscoveryError(f"Runtime property is unresolved: {name}")
        return resolved

    result = PROPERTY_RE.sub(property_repl, value)

    def runtime_repl(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        if name not in runtime:
            raise ContractDiscoveryError(f"Runtime correlation is unresolved: {name}")
        return runtime[name]

    return RUNTIME_RE.sub(runtime_repl, result)


def json_path_value(payload: Any, expression: str) -> Any:
    if expression == "$":
        return payload
    if not expression.startswith("$."):
        raise ContractDiscoveryError(f"Unsupported JSONPath for functional contract discovery: {expression}")
    current = payload
    for piece in expression[2:].split("."):
        if not isinstance(current, dict) or piece not in current:
            raise ContractDiscoveryError(f"JSONPath did not resolve: {expression}")
        current = current[piece]
    return current


def execute_request(request: dict[str, Any], csv_row: dict[str, str], properties: dict[str, str], runtime: dict[str, str], timeout: float) -> tuple[int, bytes]:
    protocol = str(request.get("protocol", "https"))
    host = str(request.get("host", "")).strip()
    port = request.get("port")
    path = substitute(str(request.get("path", "/")), properties, runtime)
    query = substitute(str(request.get("query", "")), properties, runtime)
    if not host:
        raise ContractDiscoveryError(f"Request has no host: {request.get('id')}")
    authority = host
    if port and not ((protocol == "https" and int(port) == 443) or (protocol == "http" and int(port) == 80)):
        authority = f"{host}:{port}"
    url = f"{protocol}://{authority}{path}"
    if query:
        url += "?" + query

    headers: dict[str, str] = {}
    for item in request.get("headers", []) or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        headers[name] = substitute(str(item.get("value", "")), properties, runtime)

    data = None
    body = request.get("json_body")
    if body is not None:
        materialized = materialize_body(body, csv_row, properties, runtime)
        data = json.dumps(materialized, separators=(",", ":")).encode("utf-8")
        if not any(name.lower() == "content-type" for name in headers):
            headers["Content-Type"] = "application/json"

    # Postman and requests-based clients send a permissive Accept header by
    # default. urllib does not. Preserve any explicit source header, otherwise
    # use the same neutral HTTP default so contract discovery does not change
    # server-side content negotiation compared with generated engines.
    if not any(name.lower() == "accept" for name in headers):
        headers["Accept"] = "*/*"

    http_request = Request(
        url,
        data=data,
        headers=headers,
        method=str(request.get("method", "GET")).upper(),
    )

    try:
        with urlopen(http_request, timeout=timeout) as response:
            return int(response.status), response.read()
    except HTTPError as exc:
        return int(exc.code), exc.read()
    except (URLError, OSError) as exc:
        raise ContractDiscoveryError(
            f"Functional request failed for {request.get('id')}: {exc}"
        ) from exc


def runtime_dependencies(value: Any) -> set[str]:
    dependencies: set[str] = set()
    if isinstance(value, dict):
        for child in value.values():
            dependencies.update(runtime_dependencies(child))
    elif isinstance(value, list):
        for child in value:
            dependencies.update(runtime_dependencies(child))
    elif isinstance(value, str):
        for match in RUNTIME_RE.finditer(value):
            name = match.group(1).strip()
            if not name.startswith("__P("):
                dependencies.add(name)
    return dependencies


def request_runtime_dependencies(request: dict[str, Any]) -> set[str]:
    values: list[Any] = [
        request.get("path", ""),
        request.get("query", ""),
        request.get("headers", []),
        request.get("json_body"),
    ]
    dependencies: set[str] = set()
    for value in values:
        dependencies.update(runtime_dependencies(value))
    return dependencies


def update_plan(plan: dict[str, Any], model: dict[str, Any]) -> None:
    by_key = {
        (str(req.get("method", "")).upper(), str(req.get("path", ""))): req.get("expected_status")
        for req in model.get("requests", []) or []
        if isinstance(req, dict)
    }
    assertions: list[dict[str, Any]] = []
    for tx in plan.get("transactions", []) or []:
        if not isinstance(tx, dict):
            continue
        key = (str(tx.get("method", "")).upper(), str(tx.get("path", "")))
        status = by_key.get(key)
        if status in (None, "", "UNRESOLVED"):
            raise ContractDiscoveryError(
                f"HTTP contract remains unresolved for {key[0]} {key[1]}"
            )
        tx["expected_status"] = int(status)
        assertions.append({
            "type": "RESPONSE_CODE",
            "transaction": str(tx.get("name", "")),
            "expected_value": str(int(status)),
            "description": f"Validate expected HTTP response for {tx.get('name', '')}.",
        })
    plan["assertions"] = assertions


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve and validate Postman HTTP response contracts with one "
            "engine-neutral functional E2E traversal. This is not load testing."
        )
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    args = parser.parse_args()

    manifest_path = args.manifest.expanduser().resolve()
    manifest = load_json(manifest_path)
    artifacts = manifest.get("artifacts") or {}
    scenario = str(manifest.get("scenario", "")).strip()
    if not scenario:
        raise ContractDiscoveryError("Design manifest has no canonical scenario.")

    model_path = absolute_path(str(artifacts.get("executable_model", "")))
    csv_path = absolute_path(str(artifacts.get("csv", "")))
    plan_dir = absolute_path(str(artifacts.get("plan_directory", "")))
    plan_path = (plan_dir / "test-plan.yaml").resolve()
    properties_path = (ROOT / "data" / scenario / "secrets.properties").resolve()

    for required in (model_path, csv_path, plan_path):
        if not required.is_file():
            raise ContractDiscoveryError(f"Required design artifact is missing: {required}")

    model = load_json(model_path)
    plan = load_yaml(plan_path)
    csv_row = read_first_csv_row(csv_path)
    properties = read_properties(properties_path)
    runtime: dict[str, str] = {}

    print("=" * 70)
    print("FUNCTIONAL HTTP CONTRACT DISCOVERY")
    print("=" * 70)
    print(f"Scenario : {scenario}")
    print("Mode     : SINGLE FUNCTIONAL E2E TRAVERSAL")
    print("Load     : NOT EXECUTED")

    requests = [
        request
        for request in (model.get("requests", []) or [])
        if isinstance(request, dict)
    ]
    executed_ids: set[str] = set()

    try:
        for request in requests:
            status, body = execute_request(
                request,
                csv_row,
                properties,
                runtime,
                args.timeout_seconds,
            )
            executed_ids.add(str(request.get("id", "")))
            declared = request.get("expected_status")
            if declared not in (None, "", "UNRESOLVED"):
                if int(declared) != status:
                    raise ContractDiscoveryError(
                        "Observed HTTP status does not match the explicit Postman contract for "
                        f"{request.get('id')}: expected {declared}, observed {status}."
                    )
            elif status >= 400:
                preview = body.decode("utf-8", errors="replace").strip()[:240]
                detail = f" Response: {preview}" if preview else ""
                raise ContractDiscoveryError(
                    "Cannot infer a successful HTTP contract from an error response for "
                    f"{request.get('id')}: observed HTTP {status}.{detail}"
                )

            request["expected_status"] = status
            print(f"{request.get('method')} {request.get('path')} -> HTTP {status}")

            extractors = request.get("extractors", []) or []
            if extractors:
                try:
                    payload = json.loads(body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ContractDiscoveryError(
                        f"Response is not JSON but correlations are required for {request.get('id')}"
                    ) from exc
                for extractor in extractors:
                    if not isinstance(extractor, dict):
                        continue
                    variable = str(extractor.get("variable", "")).strip()
                    expression = str(extractor.get("json_path", "")).strip()
                    if not variable or not expression:
                        continue
                    value = json_path_value(payload, expression)
                    runtime[variable] = str(value)
    except Exception:
        # Best-effort functional cleanup. Do not hide the original failure.
        for cleanup in requests:
            cleanup_id = str(cleanup.get("id", ""))
            if cleanup_id in executed_ids:
                continue
            if str(cleanup.get("method", "")).upper() != "DELETE":
                continue

            missing_runtime = sorted(
                request_runtime_dependencies(cleanup) - set(runtime)
            )
            if missing_runtime:
                print(
                    "FUNCTIONAL CLEANUP SKIPPED: "
                    f"{cleanup_id} requires unresolved runtime values: "
                    + ", ".join(missing_runtime),
                    file=sys.stderr,
                )
                continue

            try:
                cleanup_status, _ = execute_request(
                    cleanup,
                    csv_row,
                    properties,
                    runtime,
                    args.timeout_seconds,
                )
                print(
                    f"FUNCTIONAL CLEANUP {cleanup.get('path')} -> HTTP {cleanup_status}"
                )
            except Exception as cleanup_exc:
                print(
                    "FUNCTIONAL CLEANUP WARNING: "
                    f"{cleanup.get('id')}: {cleanup_exc}",
                    file=sys.stderr,
                )
        raise

    update_plan(plan, model)
    model_path.write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    plan_path.write_text(yaml.safe_dump(plan, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")

    manifest["response_contract"] = {
        "status": "RESOLVED_AND_FUNCTIONALLY_VALIDATED",
        "mode": "SINGLE_FUNCTIONAL_E2E_TRAVERSAL",
        "performance_load_executed": False,
        "transaction_count": len(model.get("requests", []) or []),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("=" * 70)
    print("HTTP CONTRACTS : RESOLVED AND VALIDATED")
    print("PERFORMANCE LOAD: NOT EXECUTED")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractDiscoveryError as exc:
        print(f"CONTRACT DISCOVERY ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
