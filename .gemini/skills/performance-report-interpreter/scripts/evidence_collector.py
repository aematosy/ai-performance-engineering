#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any

from report_models import EvidenceBundle, EvidenceSample


SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "proxy-authorization",
    "x-api-key",
    "api-key",
}
SENSITIVE_JSON_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "secret",
    "sessionid",
    "session_id",
}


def parse_headers(raw: str | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in (raw or "").splitlines():
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        key = name.strip()
        if not key:
            continue
        if key.lower() in SENSITIVE_HEADERS:
            headers[key] = "<REDACTED>"
        else:
            headers[key] = redact_text(value.strip())
    return headers


def _redact_obj(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("<REDACTED>" if key.lower() in SENSITIVE_JSON_KEYS else _redact_obj(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_obj(item) for item in value]
    return value


def redact_text(value: str | None, limit: int = 4000) -> str | None:
    if value is None:
        return None
    text = str(value)
    try:
        parsed = json.loads(text)
        text = json.dumps(_redact_obj(parsed), ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        patterns = [
            (r'(?i)(password\s*[=:]\s*)[^\s,;&]+', r'\1<REDACTED>'),
            (r'(?i)(token\s*[=:]\s*)[^\s,;&]+', r'\1<REDACTED>'),
            (r'(?i)(authorization\s*:\s*)[^\r\n]+', r'\1<REDACTED>'),
            (r'(?i)(cookie\s*:\s*)[^\r\n]+', r'\1<REDACTED>'),
        ]
        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text)
    return text[:limit]


def child_text(node: ET.Element, tag: str) -> str | None:
    child = node.find(tag)
    return child.text if child is not None else None


def runtime_samples_from_xml(path: Path) -> list[EvidenceSample]:
    root = ET.parse(path).getroot()
    samples: list[EvidenceSample] = []
    for node in root.iter():
        if node.tag not in {"httpSample", "sample"}:
            continue
        label = node.attrib.get("lb") or node.attrib.get("label") or "UNKNOWN"
        request_headers = parse_headers(child_text(node, "requestHeader"))
        response_headers = parse_headers(child_text(node, "responseHeader"))
        request_body = redact_text(child_text(node, "queryString"))
        response_body = redact_text(child_text(node, "responseData"))
        method = child_text(node, "method")
        url = child_text(node, "java.net.URL")
        assertions = list(node.findall("assertionResult"))
        assertions_passed = None
        if assertions:
            assertions_passed = all(
                (child_text(item, "failure") or "false").lower() != "true"
                and (child_text(item, "error") or "false").lower() != "true"
                for item in assertions
            )
        samples.append(EvidenceSample(
            label=label,
            kind="runtime",
            method=method,
            url=url,
            status_code=node.attrib.get("rc"),
            success=node.attrib.get("s", "false").lower() == "true",
            elapsed_ms=float(node.attrib.get("t", "0") or 0),
            assertions_passed=assertions_passed,
            request_headers=request_headers,
            request_body=request_body,
            response_headers=response_headers,
            response_body=response_body,
            source=str(path),
        ))
    return samples


def runtime_samples_from_csv(path: Path) -> list[EvidenceSample]:
    samples: list[EvidenceSample] = []
    with path.open(encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh):
            label = row.get("label") or "UNKNOWN"
            samples.append(EvidenceSample(
                label=label,
                kind="runtime_status",
                url=row.get("URL") or row.get("url"),
                status_code=row.get("responseCode"),
                success=str(row.get("success", "")).lower() == "true",
                elapsed_ms=float(row.get("elapsed") or 0),
                request_headers=parse_headers(row.get("requestHeaders")),
                request_body=redact_text(row.get("samplerData") or row.get("requestData")),
                response_headers=parse_headers(row.get("responseHeaders")),
                response_body=redact_text(row.get("responseData")),
                source=str(path),
            ))
    return samples


def jmx_templates(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.is_file():
        return {}
    root = ET.parse(path).getroot()
    result: dict[str, dict[str, Any]] = {}
    for tree in root.iter("hashTree"):
        children = list(tree)
        for i, child in enumerate(children):
            if child.tag != "HTTPSamplerProxy":
                continue
            label = child.attrib.get("testname", "UNKNOWN")
            method = child.find("./stringProp[@name='HTTPSampler.method']")
            path_prop = child.find("./stringProp[@name='HTTPSampler.path']")
            body = child.find(".//stringProp[@name='Argument.value']")
            headers: dict[str, str] = {}
            if i + 1 < len(children) and children[i + 1].tag == "hashTree":
                sampler_tree = children[i + 1]
                for manager in sampler_tree.findall("./HeaderManager"):
                    for item in manager.findall(".//elementProp"):
                        name = item.find("./stringProp[@name='Header.name']")
                        value = item.find("./stringProp[@name='Header.value']")
                        if name is None or not name.text:
                            continue
                        headers[name.text] = (
                            "<REDACTED>" if name.text.lower() in SENSITIVE_HEADERS
                            else redact_text(value.text if value is not None else "") or ""
                        )
            result[label] = {
                "method": method.text if method is not None else None,
                "path": path_prop.text if path_prop is not None else None,
                "request_body": redact_text(body.text if body is not None else None),
                "request_headers": headers,
            }
    return result


def select_representative(samples: list[EvidenceSample]) -> list[EvidenceSample]:
    grouped: dict[str, list[EvidenceSample]] = defaultdict(list)
    for sample in samples:
        grouped[sample.label].append(sample)

    selected: list[EvidenceSample] = []
    for label, items in grouped.items():
        successes = [item for item in items if item.success]
        failures = [item for item in items if item.success is False]
        if successes:
            ordered_successes = sorted(successes, key=lambda item: item.elapsed_ms or 0)
            best = ordered_successes[len(ordered_successes) // 2]
            best.kind = "representative_success"
            selected.append(best)
        if failures:
            first_failure = failures[0]
            first_failure.kind = "representative_failure"
            selected.append(first_failure)
        if items:
            elapsed_values = sorted(float(item.elapsed_ms or 0) for item in items)
            median = elapsed_values[len(elapsed_values) // 2] if elapsed_values else 0.0
            slowest = max(items, key=lambda item: item.elapsed_ms or 0)
            already = any(
                item.label == slowest.label
                and item.status_code == slowest.status_code
                and item.elapsed_ms == slowest.elapsed_ms
                for item in selected
            )
            # Solo agregar un outlier cuando realmente sea anómalo; evita inflar
            # reportes normales con una segunda muestra por cada transacción.
            if not already and median > 0 and float(slowest.elapsed_ms or 0) >= median * 2.0:
                slowest.kind = "slow_outlier"
                selected.append(slowest)
    return selected


def merge_templates(samples: list[EvidenceSample], templates: dict[str, dict[str, Any]]) -> None:
    for sample in samples:
        template = templates.get(sample.label, {})
        if sample.method is None:
            sample.method = template.get("method")
        if not sample.request_headers:
            sample.request_headers = template.get("request_headers", {})
        if not sample.request_body:
            sample.request_body = template.get("request_body")
        if not sample.url and template.get("path"):
            sample.url = template.get("path")


def coverage_for(samples: list[EvidenceSample]) -> str:
    if not samples:
        return "NOT_AVAILABLE"
    if any(item.request_body and item.response_body for item in samples):
        return "RUNTIME_REQUEST_RESPONSE_VERIFIED"
    if any(item.request_body for item in samples):
        return "REQUEST_TEMPLATE_PLUS_RUNTIME_STATUS"
    return "STATUS_ONLY"


def collect(jtl: Path, jmx: Path | None = None) -> EvidenceBundle:
    head = jtl.read_bytes()[:200].lstrip()
    if head.startswith(b"<?xml") or head.startswith(b"<testResults"):
        runtime = runtime_samples_from_xml(jtl)
    else:
        runtime = runtime_samples_from_csv(jtl)
    selected = select_representative(runtime)
    merge_templates(selected, jmx_templates(jmx))
    coverage = coverage_for(selected)
    notes = [
        "Evidencia representativa: como máximo un éxito, un fallo y un outlier lento por transacción cuando estén disponibles.",
        "Headers sensibles y campos de secretos comunes se redactan automáticamente.",
    ]
    if coverage != "RUNTIME_REQUEST_RESPONSE_VERIFIED":
        notes.append(
            "Los payloads exactos de runtime no estuvieron disponibles en su totalidad; un HTTP exitoso no debe tratarse como prueba funcional completa."
        )
    return EvidenceBundle(coverage=coverage, transactions=selected, notes=notes)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect representative sanitized execution evidence.")
    parser.add_argument("--jtl", required=True, type=Path)
    parser.add_argument("--jmx", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    bundle = collect(args.jtl, args.jmx)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
