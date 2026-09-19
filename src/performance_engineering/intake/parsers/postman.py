#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SUPPORTED_SCHEMAS = ("collection/v2.0.0", "collection/v2.1.0")
VAR_RE = re.compile(r"\{\{([^{}]+)\}\}")
SET_RE = re.compile(r'pm\.(globals|environment|collectionVariables|variables)\.set\(\s*["\']([^"\']+)["\']', re.I)
RT_RE = re.compile(r"responseTime\)\.to\.be\.below\((\d+)\)", re.I)
STATUS_RE = re.compile(r"pm\.response\.to\.have\.status\((\d{3})\)", re.I)
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
NUMERIC_RE = re.compile(r"^\d+$")
ALNUM_RE = re.compile(r"^[A-Za-z0-9_-]{8,}$")
SENSITIVE_RE = re.compile(r"password|passwd|secret|token|api[_-]?key|authorization|cookie|client[_-]?secret|private[_-]?key", re.I)
UNSUPPORTED_MARKERS = {
    "pm.sendRequest": "POSTMAN_DYNAMIC_REQUEST",
    "postman.setNextRequest": "POSTMAN_CONTROL_FLOW",
    "pm.execution.setNextRequest": "POSTMAN_CONTROL_FLOW",
    "eval(": "DYNAMIC_JAVASCRIPT",
}

class ParseError(RuntimeError):
    pass

def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ParseError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ParseError(f"Invalid JSON in {path}: line {exc.lineno}, column {exc.colno}") from exc
    if not isinstance(data, dict):
        raise ParseError(f"JSON root must be an object: {path}")
    return data

def schema_of(collection: dict[str, Any]) -> str:
    schema = str(collection.get("info", {}).get("schema", ""))
    if not any(x in schema for x in SUPPORTED_SCHEMAS):
        raise ParseError(f"Unsupported Postman schema: {schema or '<missing>'}")
    return schema

def sensitive(name: str) -> bool:
    return bool(SENSITIVE_RE.search(name or ""))

def scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)

def variables_from(values: Any, scope: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(values, list):
        return out
    for item in values:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if not isinstance(key, str) or not key.strip():
            continue
        value = scalar(item.get("value"))
        is_sensitive = sensitive(key)
        out[key] = {
            "name": key,
            "scope": scope,
            "enabled": bool(item.get("enabled", True)),
            "sensitive": is_sensitive,
            "value": "<REDACTED>" if is_sensitive else value,
            "_raw": value,
        }
    return out

def merged_vars(collection_vars: dict[str, dict[str, Any]], env_vars: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = dict(collection_vars)
    result.update({k: v for k, v in env_vars.items() if v.get("enabled", True)})
    return result

def resolve_template(text: str, values: dict[str, dict[str, Any]]) -> tuple[str, list[str]]:
    unresolved: list[str] = []
    def repl(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        var = values.get(name)
        if not var or not var.get("enabled", True):
            unresolved.append(name)
            return match.group(0)
        if var.get("sensitive"):
            return f"{{{{{name}}}}}"
        return str(var.get("_raw", ""))
    return VAR_RE.sub(repl, text), sorted(set(unresolved))

def refs(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, str):
        found.update(x.strip() for x in VAR_RE.findall(value))
    elif isinstance(value, list):
        for x in value:
            found.update(refs(x))
    elif isinstance(value, dict):
        for x in value.values():
            found.update(refs(x))
    return found

def normalize_kv(items: Any, *, sensitive_by_key: bool = True) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", ""))
        value = scalar(item.get("value"))
        is_sensitive = sensitive(key) if sensitive_by_key else False
        out.append({
            "key": key,
            "value": "<REDACTED>" if is_sensitive else value,
            "disabled": bool(item.get("disabled", False)),
            "sensitive": is_sensitive,
            "variable_references": sorted(VAR_RE.findall(value)),
        })
    return out

def normalize_auth(auth: Any) -> dict[str, Any]:
    if auth is None:
        return {"type": "INHERIT", "details": [], "unsupported": False}
    if not isinstance(auth, dict):
        return {"type": "UNKNOWN", "details": [], "unsupported": True}
    raw_type = str(auth.get("type", "none"))
    auth_type = raw_type.upper()
    details = normalize_kv(auth.get(raw_type, []))
    supported = auth_type in {"NOAUTH", "BASIC", "BEARER", "APIKEY", "OAUTH2", "INHERIT", "NONE"}
    return {"type": auth_type, "details": details, "unsupported": not supported}

def normalize_body(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {"mode": "none", "content": None, "unsupported": False}
    mode = str(body.get("mode", "none"))
    if mode == "raw":
        raw = str(body.get("raw", ""))
        return {
            "mode": mode,
            "content": {
                "raw": "<REDACTED>" if SENSITIVE_RE.search(raw) else raw,
                "language": body.get("options", {}).get("raw", {}).get("language") if isinstance(body.get("options"), dict) else None,
                "variable_references": sorted(VAR_RE.findall(raw)),
            },
            "unsupported": False,
        }
    if mode in {"urlencoded", "formdata"}:
        return {"mode": mode, "content": normalize_kv(body.get(mode, [])), "unsupported": False}
    if mode == "graphql":
        value = body.get("graphql") if isinstance(body.get("graphql"), dict) else {}
        return {"mode": mode, "content": {"query": value.get("query"), "variables": value.get("variables")}, "unsupported": False}
    if mode == "file":
        return {"mode": mode, "content": {"file_reference": body.get("file")}, "unsupported": True}
    return {"mode": mode, "content": body.get(mode), "unsupported": mode not in {"none", ""}}

def analyze_events(events: Any) -> dict[str, Any]:
    created: list[dict[str, Any]] = []
    assertions: list[dict[str, Any]] = []
    unsupported: set[str] = set()
    scripts: list[dict[str, Any]] = []
    if not isinstance(events, list):
        return {"variables_created": created, "candidate_assertions": assertions, "unsupported_features": [], "scripts": scripts}
    seen_created: set[tuple[str, str]] = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        listen = str(event.get("listen", ""))
        script = event.get("script", {})
        exec_lines = script.get("exec", []) if isinstance(script, dict) else []
        lines = [exec_lines] if isinstance(exec_lines, str) else [str(x) for x in exec_lines] if isinstance(exec_lines, list) else []
        content = "\n".join(lines)
        for scope, name in SET_RE.findall(content):
            seen_created.add((scope, name))
        for value in RT_RE.findall(content):
            assertions.append({"type": "RESPONSE_TIME_BELOW_MS", "value": int(value), "source": "postman_test_script", "classification": "CANDIDATE_SLA"})
        for value in STATUS_RE.findall(content):
            assertions.append({"type": "HTTP_STATUS", "value": int(value), "source": "postman_test_script", "classification": "ASSERTION"})
        for marker, code in UNSUPPORTED_MARKERS.items():
            if marker in content:
                unsupported.add(code)
        scripts.append({"type": listen, "present": bool(content.strip()), "sha256": hashlib.sha256(content.encode()).hexdigest() if content else None})
    for scope, name in sorted(seen_created):
        created.append({"scope": scope, "name": name, "sensitive": sensitive(name)})
    return {"variables_created": created, "candidate_assertions": assertions, "unsupported_features": sorted(unsupported), "scripts": scripts}

def static_candidates(url: str) -> list[dict[str, str]]:
    if not url or "{{" in url:
        return []
    try:
        path = urlsplit(url).path
    except ValueError:
        return []
    out: list[dict[str, str]] = []
    for segment in [s for s in path.split("/") if s]:
        if NUMERIC_RE.fullmatch(segment):
            out.append({"value": segment, "kind": "NUMERIC", "confidence": "HIGH"})
        elif UUID_RE.fullmatch(segment):
            out.append({"value": segment, "kind": "UUID", "confidence": "HIGH"})
        elif ALNUM_RE.fullmatch(segment) and any(c.isdigit() for c in segment):
            out.append({"value": segment, "kind": "ALPHANUMERIC", "confidence": "MEDIUM"})
    return out

def normalize_url(url_obj: Any, values: dict[str, dict[str, Any]]) -> dict[str, Any]:
    raw = url_obj if isinstance(url_obj, str) else str(url_obj.get("raw", "")) if isinstance(url_obj, dict) else ""
    resolved, unresolved = resolve_template(raw, values)
    parsed = None
    if resolved and "{{" not in resolved:
        try:
            parsed = urlsplit(resolved)
        except ValueError:
            parsed = None
    query = normalize_kv(url_obj.get("query", [])) if isinstance(url_obj, dict) else []
    path_variables = normalize_kv(url_obj.get("variable", [])) if isinstance(url_obj, dict) else []
    return {
        "raw": raw,
        "resolved": resolved,
        "unresolved_variables": unresolved,
        "protocol": parsed.scheme if parsed else None,
        "host": parsed.hostname if parsed else None,
        "port": parsed.port if parsed else None,
        "path": parsed.path if parsed else None,
        "query": query,
        "path_variables": path_variables,
    }

def walk(items: Any, values: dict[str, dict[str, Any]], inherited_auth: Any, folder_path: list[str], out: list[dict[str, Any]]) -> None:
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "<unnamed>"))
        item_auth = item.get("auth", inherited_auth)
        if isinstance(item.get("item"), list):
            walk(item["item"], values, item_auth, [*folder_path, name], out)
            continue
        request = item.get("request")
        if not isinstance(request, dict):
            continue
        request_auth = request.get("auth", item_auth)
        url = normalize_url(request.get("url"), values)
        body = normalize_body(request.get("body"))
        event_info = analyze_events(item.get("event", []))
        unsupported = set(event_info["unsupported_features"])
        auth = normalize_auth(request_auth)
        if auth.get("unsupported"):
            unsupported.add("AUTH_TYPE_UNSUPPORTED")
        if body.get("unsupported"):
            unsupported.add(f"BODY_MODE_{str(body.get('mode')).upper()}")
        out.append({
            "id": "/".join(folder_path + [name]),
            "name": name,
            "folder_path": folder_path,
            "method": str(request.get("method", "GET")).upper(),
            "url": url,
            "headers": normalize_kv(request.get("header", [])),
            "query": url["query"],
            "path_variables": url["path_variables"],
            "auth": auth,
            "body": body,
            "variable_references": sorted(refs(request)),
            "variables_created": event_info["variables_created"],
            "candidate_assertions": event_info["candidate_assertions"],
            "scripts": event_info["scripts"],
            "static_resource_candidates": static_candidates(url["resolved"]),
            "unsupported_features": sorted(unsupported),
        })

def dependencies(requests: list[dict[str, Any]]) -> list[dict[str, str]]:
    producers: dict[str, list[str]] = {}
    for request in requests:
        for item in request["variables_created"]:
            producers.setdefault(item["name"], []).append(request["id"])
    out: list[dict[str, str]] = []
    for request in requests:
        for ref in request["variable_references"]:
            for producer in producers.get(ref, []):
                if producer != request["id"]:
                    out.append({"variable": ref, "producer": producer, "consumer": request["id"]})
    return out

def public_vars(values: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for name in sorted(values):
        item = dict(values[name])
        item.pop("_raw", None)
        out.append(item)
    return out

def main() -> int:
    ap = argparse.ArgumentParser(description="Generic Postman Collection v2.0/v2.1 normalizer.")
    ap.add_argument("--collection", required=True)
    ap.add_argument("--environment")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    collection_path = Path(args.collection).expanduser().resolve()
    env_path = Path(args.environment).expanduser().resolve() if args.environment else None
    output_path = Path(args.output).expanduser().resolve()

    try:
        collection = load_json(collection_path)
        schema = schema_of(collection)
        environment = load_json(env_path) if env_path else {}
        collection_vars = variables_from(collection.get("variable", []), "collection")
        env_vars = variables_from(environment.get("values", []), "environment")
        merged = merged_vars(collection_vars, env_vars)
        reqs: list[dict[str, Any]] = []
        walk(collection.get("item", []), merged, collection.get("auth"), [], reqs)
        deps = dependencies(reqs)
        unresolved = sorted({v for r in reqs for v in r["url"]["unresolved_variables"]})
        unsupported = [{"request_id": r["id"], "feature": f} for r in reqs for f in r["unsupported_features"]]
        static = [{"request_id": r["id"], **c} for r in reqs for c in r["static_resource_candidates"]]
        assertions = [{"request_id": r["id"], **a} for r in reqs for a in r["candidate_assertions"]]
        dynamic = sorted({v["name"] for r in reqs for v in r["variables_created"]})
        normalized = {
            "schema_version": "2.0",
            "source": {"collection_path": str(collection_path), "environment_path": str(env_path) if env_path else None},
            "collection": {"name": collection.get("info", {}).get("name"), "schema": schema},
            "environment": {"name": environment.get("name") if environment else None, "provided": bool(env_path)},
            "variables": {"collection": public_vars(collection_vars), "environment": public_vars(env_vars), "unresolved": unresolved, "dynamic_runtime": dynamic},
            "requests": reqs,
            "dependencies": deps,
            "static_resource_candidates": static,
            "candidate_assertions": assertions,
            "unsupported_features": unsupported,
            "summary": {
                "request_count": len(reqs),
                "dependency_count": len(deps),
                "dynamic_variable_count": len(dynamic),
                "unresolved_variable_count": len(unresolved),
                "static_resource_candidate_count": len(static),
                "candidate_assertion_count": len(assertions),
                "unsupported_feature_count": len(unsupported),
            },
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except ParseError as exc:
        print(f"POSTMAN PARSE ERROR: {exc}", file=sys.stderr)
        return 2

    print("=" * 70)
    print("POSTMAN NORMALIZATION v2")
    print("=" * 70)
    print(f"Collection : {normalized['collection']['name']}")
    print(f"Environment: {normalized['environment']['name']}")
    for key, value in normalized["summary"].items():
        print(f"{key:34}: {value}")
    print(f"Output                            : {output_path}")
    print("=" * 70)
    print("NORMALIZATION COMPLETE")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
