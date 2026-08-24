#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any

class ValidationError(RuntimeError):
    pass

def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON: line {exc.lineno}, column {exc.colno}") from exc
    if not isinstance(data, dict):
        raise ValidationError("Root must be a JSON object")
    return data

def require(obj: dict[str, Any], key: str, typ: type) -> Any:
    if key not in obj:
        raise ValidationError(f"Missing required field: {key}")
    value = obj[key]
    if not isinstance(value, typ):
        raise ValidationError(f"Field '{key}' must be {typ.__name__}")
    return value

def main() -> int:
    ap = argparse.ArgumentParser(description="Validate normalized Postman v2 model")
    ap.add_argument("--input", required=True)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    path = Path(args.input).expanduser().resolve()
    try:
        data = load(path)
        if data.get("schema_version") != "2.0":
            raise ValidationError(f"Unsupported schema_version: {data.get('schema_version')}")
        require(data, "collection", dict)
        require(data, "environment", dict)
        variables = require(data, "variables", dict)
        requests = require(data, "requests", list)
        deps = require(data, "dependencies", list)
        unsupported = require(data, "unsupported_features", list)
        summary = require(data, "summary", dict)
        if summary.get("request_count") != len(requests):
            raise ValidationError("summary.request_count mismatch")
        if summary.get("dependency_count") != len(deps):
            raise ValidationError("summary.dependency_count mismatch")
        ids: set[str] = set()
        for i, request in enumerate(requests):
            if not isinstance(request, dict):
                raise ValidationError(f"requests[{i}] must be object")
            rid = require(request, "id", str)
            if rid in ids:
                raise ValidationError(f"Duplicate request id: {rid}")
            ids.add(rid)
            require(request, "name", str)
            require(request, "method", str)
            require(request, "url", dict)
            require(request, "headers", list)
            require(request, "auth", dict)
            require(request, "body", dict)
            require(request, "variable_references", list)
            require(request, "variables_created", list)
            require(request, "unsupported_features", list)
        for edge in deps:
            if not isinstance(edge, dict):
                raise ValidationError("dependency edge must be object")
            producer = require(edge, "producer", str)
            consumer = require(edge, "consumer", str)
            require(edge, "variable", str)
            if producer not in ids:
                raise ValidationError(f"Unknown producer: {producer}")
            if consumer not in ids:
                raise ValidationError(f"Unknown consumer: {consumer}")
        unresolved = variables.get("unresolved", [])
        if not isinstance(unresolved, list):
            raise ValidationError("variables.unresolved must be list")
        status = "FAIL" if args.strict and (unresolved or unsupported) else "PASS"
    except ValidationError as exc:
        print("=" * 70)
        print("NORMALIZED POSTMAN VALIDATION")
        print("=" * 70)
        print("Status : FAIL")
        print(f"Error  : {exc}")
        print("=" * 70)
        return 2
    print("=" * 70)
    print("NORMALIZED POSTMAN VALIDATION")
    print("=" * 70)
    print(f"Status      : {status}")
    print(f"Collection  : {data.get('collection', {}).get('name')}")
    print(f"Requests    : {len(requests)}")
    print(f"Dependencies: {len(deps)}")
    print(f"Unresolved  : {len(unresolved)}")
    print(f"Unsupported : {len(unsupported)}")
    if unresolved:
        print(f"[WARNING] UNRESOLVED_VARIABLES | {', '.join(unresolved)}")
    if unsupported:
        print(f"[WARNING] UNSUPPORTED_FEATURES | {len(unsupported)} occurrence(s)")
    print("=" * 70)
    return 0 if status == "PASS" else 2

if __name__ == "__main__":
    raise SystemExit(main())
