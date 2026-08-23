#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    location: str
    autofixable: bool = False


SENSITIVE_KEY_NAMES = {
    "password", "passwd", "secret", "token", "access_token", "refresh_token",
    "api_key", "apikey", "client_secret", "authorization_header",
    "proxy_authorization", "cookie", "set_cookie",
}
SENSITIVE_VALUE_PATTERNS = [
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)basic\s+[A-Za-z0-9+/=]{12,}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
]


class ReviewError(RuntimeError):
    pass


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ReviewError(f"Plan not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ReviewError("Plan root must be a YAML mapping.")
    return data


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ReviewError(f"JSON root must be an object: {path}")
    return data


def md_has_status(text: str, labels: str | tuple[str, ...], value: str) -> bool:
    # Accept canonical and common human-readable renderings produced by the designer.
    if isinstance(labels, str):
        labels = (labels,)

    for label in labels:
        patterns = [
            rf"(?im)^\s*\*\*{re.escape(label)}:\*\*\s*`?{re.escape(value)}`?\s*$",
            rf"(?im)^\s*-\s*\*\*{re.escape(label)}:\*\*\s*`?{re.escape(value)}`?\s*$",
            rf"(?im)^\s*-?\s*{re.escape(label)}\s*:\s*`?{re.escape(value)}`?\s*$",
        ]
        if any(re.search(pattern, text) for pattern in patterns):
            return True
    return False


def iter_scalars(value: Any, path: str = "root"):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            yield from iter_scalars(child, child_path)
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            yield from iter_scalars(child, f"{path}[{idx}]")
    else:
        yield path, value


def review(plan_path: Path) -> tuple[dict[str, Any], list[Finding]]:
    plan = load_yaml(plan_path)
    plan_dir = plan_path.parent
    md_path = plan_dir / "test-plan.md"
    data_path = plan_dir / "data-requirements.json"

    findings: list[Finding] = []
    status = str(plan.get("status", "")).upper()
    workload_status = str(plan.get("workload", {}).get("status", "")).upper()
    authorization_status = str(plan.get("authorization", {}).get("status", "")).upper()

    if status not in {"DRAFT", "APPROVED"}:
        findings.append(Finding("ERROR", "PLAN-STATUS", "Plan status must be DRAFT or APPROVED.", "status"))
    if workload_status not in {"PROPOSED", "APPROVED"}:
        findings.append(Finding("ERROR", "WORKLOAD-STATUS", "Workload status must be PROPOSED or APPROVED.", "workload.status"))
    if authorization_status not in {"PENDING", "AUTHORIZED", "REJECTED"}:
        findings.append(Finding("ERROR", "AUTH-STATUS", "Authorization status is invalid.", "authorization.status"))

    # Security review: inspect only scalar leaf fields. Section names such as
    # 'authorization' are not secrets by themselves.
    for location, raw_value in iter_scalars(plan, ""):
        leaf = location.rsplit(".", 1)[-1].lower().replace("-", "_")
        if leaf in SENSITIVE_KEY_NAMES:
            value = "" if raw_value is None else str(raw_value).strip()
            allowed_placeholder = (
                not value
                or value.lower() in {"null", "none", "pending", "not_set", "placeholder", "${env}"}
                or "${" in value
            )
            if not allowed_placeholder:
                findings.append(Finding(
                    "ERROR", "SECURITY-SENSITIVE-VALUE",
                    f"Potential secret persisted in sensitive field '{leaf}'.",
                    location,
                ))
        if isinstance(raw_value, str):
            for pattern in SENSITIVE_VALUE_PATTERNS:
                if pattern.search(raw_value):
                    findings.append(Finding(
                        "ERROR", "SECURITY-SENSITIVE-VALUE",
                        "Potential credential-like value detected.", location,
                    ))
                    break

    # URLs in YAML should be plain URLs, not markdown links.
    for location, raw_value in iter_scalars(plan, ""):
        if isinstance(raw_value, str) and re.search(r"\[[^\]]+\]\(https?://", raw_value):
            findings.append(Finding(
                "ERROR", "FORMAT-MARKDOWN-URL",
                "Markdown URL found inside structured YAML.", location, True,
            ))

    # SLA provenance.
    sla = plan.get("sla", {})
    if isinstance(sla, dict) and not sla.get("source"):
        findings.append(Finding(
            "ERROR", "SLA-NO-SOURCE", "SLA thresholds must declare a source.", "sla.source"
        ))

    # Workload/SLA feasibility guardrail. For closed workloads with positive
    # pacing, threads / pacing is an optimistic throughput ceiling because it
    # assumes zero response time. If that ceiling cannot exceed the configured
    # minimum throughput SLA, the proposed workload is mathematically unable to
    # satisfy the SLA and must be rejected before execution.
    parameters = plan.get("workload", {}).get("parameters", {})
    threads = parameters.get("threads") if isinstance(parameters, dict) else None
    pacing = parameters.get("pacing_seconds") if isinstance(parameters, dict) else None
    min_throughput = sla.get("min_throughput_req_per_sec") if isinstance(sla, dict) else None

    numeric_values = (threads, pacing, min_throughput)
    if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in numeric_values):
        threads_f = float(threads)
        pacing_f = float(pacing)
        min_throughput_f = float(min_throughput)
        if threads_f <= 0:
            findings.append(Finding(
                "ERROR", "WORKLOAD-INVALID-THREADS",
                "threads must be greater than zero.",
                "workload.parameters.threads",
            ))
        if pacing_f < 0:
            findings.append(Finding(
                "ERROR", "WORKLOAD-INVALID-PACING",
                "pacing_seconds cannot be negative.",
                "workload.parameters.pacing_seconds",
            ))
        if pacing_f > 0 and threads_f > 0 and min_throughput_f > 0:
            theoretical_ceiling = threads_f / pacing_f
            if theoretical_ceiling <= min_throughput_f:
                findings.append(Finding(
                    "ERROR", "SLA-WORKLOAD-INFEASIBLE",
                    (
                        "Proposed workload cannot satisfy the minimum throughput SLA even "
                        "with zero response time: theoretical ceiling "
                        f"{theoretical_ceiling:.3f} req/s <= SLA "
                        f"{min_throughput_f:.3f} req/s. Increase approved concurrency, "
                        "reduce pacing, or revise the SLA only if its source changes."
                    ),
                    "workload.parameters",
                ))
            elif theoretical_ceiling < min_throughput_f * 1.5:
                findings.append(Finding(
                    "INFO", "SLA-WORKLOAD-LOW-HEADROOM",
                    (
                        "The optimistic throughput ceiling has less than 50% headroom over "
                        f"the SLA ({theoretical_ceiling:.3f} vs {min_throughput_f:.3f} req/s). "
                        "Response time and client overhead may reduce observed throughput."
                    ),
                    "workload.parameters",
                ))

    # Duration quality signal.
    duration = parameters.get("duration_seconds") if isinstance(parameters, dict) else None
    if isinstance(duration, (int, float)) and duration < 300:
        findings.append(Finding(
            "INFO", "QUALITY-SHORT-DURATION",
            "Duration below 300s is suitable for demo/short baseline, not sustained-capacity conclusions.",
            "workload.parameters.duration_seconds",
        ))

    # Cross-artifact consistency.
    data = load_json(data_path)
    if data is None:
        findings.append(Finding("ERROR", "CONSISTENCY-DATA-MISSING", "data-requirements.json is missing.", str(data_path)))
    else:
        data_status = str(data.get("status", "")).upper()
        if data_status != status:
            findings.append(Finding(
                "ERROR", "CONSISTENCY-STATUS",
                f"Plan status differs between YAML ({status}) and data requirements ({data_status or 'MISSING'}).",
                "data-requirements.json:status",
            ))
        scenario = str(plan.get("metadata", {}).get("name", ""))
        if str(data.get("scenario", "")) != scenario:
            findings.append(Finding(
                "ERROR", "CONSISTENCY-SCENARIO",
                "Scenario differs between YAML and data requirements.",
                "data-requirements.json:scenario",
            ))

    if not md_path.is_file():
        findings.append(Finding("ERROR", "CONSISTENCY-MD-MISSING", "test-plan.md is missing.", str(md_path)))
    else:
        md = md_path.read_text(encoding="utf-8")
        if not md_has_status(md, ("Estado", "Status", "Plan Status", "Test Plan", "Test Plan Status"), status):
            findings.append(Finding(
                "ERROR", "CONSISTENCY-MD-PLAN",
                f"Markdown does not reflect plan status {status}.", "test-plan.md",
            ))
        if not md_has_status(md, ("Workload", "Workload Status"), workload_status):
            # For DRAFT plans, older markdown often says "estado PROPOSED" in prose.
            if not re.search(rf"(?i)workload[^\n]{{0,80}}{re.escape(workload_status)}|{re.escape(workload_status)}[^\n]{{0,80}}workload", md):
                findings.append(Finding(
                    "ERROR", "CONSISTENCY-MD-WORKLOAD",
                    f"Markdown does not reflect workload status {workload_status}.", "test-plan.md",
                ))
        if not md_has_status(md, ("Execution Authorization", "Authorization", "Authorization Status", "Autorización", "Estado de Autorización"), authorization_status) and not re.search(
            rf"(?i)autorizaci[oó]n[^\n]{{0,80}}{re.escape(authorization_status)}", md
        ):
            findings.append(Finding(
                "WARNING", "CONSISTENCY-MD-AUTH",
                f"Markdown does not clearly reflect execution authorization {authorization_status}.",
                "test-plan.md",
            ))

    result = {
        "plan": str(plan_path),
        "plan_status": status,
        "workload_status": workload_status,
        "authorization_status": authorization_status,
    }
    return result, findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Review a structured Performance Test Plan and its companion artifacts.")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when warnings exist as well as errors.")
    args = parser.parse_args()

    try:
        result, findings = review(args.plan.expanduser().resolve())
    except (ReviewError, OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"REVIEW ERROR: {exc}", file=sys.stderr)
        return 2

    errors = sum(f.severity == "ERROR" for f in findings)
    warnings = sum(f.severity == "WARNING" for f in findings)
    info = sum(f.severity == "INFO" for f in findings)
    overall = "PASS" if errors == 0 and (not args.strict or warnings == 0) else "FAIL"

    payload = {
        "status": overall,
        "errors": errors,
        "warnings": warnings,
        "info": info,
        "findings": [asdict(f) for f in findings],
        **result,
    }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("=" * 66)
        print("AI PERFORMANCE TEST PLAN REVIEW")
        print("=" * 66)
        print(f"Plan       : {result['plan']}")
        print(f"Status     : {overall}")
        print(f"Errors     : {errors}")
        print(f"Warnings   : {warnings}")
        print(f"Info       : {info}")
        print()
        for finding in findings:
            print(f"[{finding.severity}] {finding.code} | {finding.location}")
            print(f"  {finding.message}")
        print("=" * 66)
        print("READY FOR HUMAN REVIEW" if overall == "PASS" else "AUTOMATIC CORRECTION/REVIEW REQUIRED")

    if errors:
        return 2
    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
