#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml

from validate_test_plan import PlanValidationError, load_plan, validate_plan


class ArtifactValidationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metadata_path_for(jmx_path: Path) -> Path:
    return jmx_path.with_suffix(jmx_path.suffix + ".meta.json")


def load_metadata(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ArtifactValidationError(f"JMX metadata not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ArtifactValidationError(f"Invalid JMX metadata JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ArtifactValidationError("JMX metadata root must be an object.")
    return payload


def canonical_target(plan: dict[str, Any]) -> dict[str, Any]:
    tx = plan["transactions"][0]
    target = plan["target"]
    return {
        "method": str(tx["method"]).upper(),
        "protocol": str(target["protocol"]),
        "host": str(target["host"]),
        "port": int(target["port"]),
        "path": str(tx["path"]),
    }


def canonical_workload(plan: dict[str, Any]) -> dict[str, Any]:
    workload = plan["workload"]["parameters"]
    return {
        "threads": int(workload["threads"]),
        "ramp_time_seconds": int(workload["ramp_time_seconds"]),
        "duration_seconds": int(workload["duration_seconds"]),
        "pacing_seconds": float(workload.get("pacing_seconds", 0)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that a JMX artifact exactly matches its approved test plan."
    )
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--jmx", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        plan_path = args.plan.expanduser().resolve()
        jmx_path = args.jmx.expanduser().resolve()
        if not jmx_path.is_file():
            raise ArtifactValidationError(f"JMX not found: {jmx_path}")

        plan = load_plan(plan_path)
        validate_plan(plan, plan_path)
        if str(plan["status"]).upper() != "APPROVED":
            raise ArtifactValidationError("Plan must be APPROVED.")
        if str(plan["workload"]["status"]).upper() != "APPROVED":
            raise ArtifactValidationError("Workload must be APPROVED.")

        try:
            ET.parse(jmx_path)
        except ET.ParseError as exc:
            raise ArtifactValidationError(f"JMX XML is invalid: {exc}") from exc

        meta_path = metadata_path_for(jmx_path)
        metadata = load_metadata(meta_path)

        expected = {
            "scenario": str(plan["metadata"]["name"]),
            "plan_sha256": sha256_file(plan_path),
            "jmx_sha256": sha256_file(jmx_path),
            "plan_status": "APPROVED",
            "workload_status": "APPROVED",
            "target": canonical_target(plan),
            "workload": canonical_workload(plan),
        }

        mismatches: list[str] = []
        for key in ("scenario", "plan_sha256", "jmx_sha256", "plan_status", "workload_status"):
            if metadata.get(key) != expected[key]:
                mismatches.append(key)
        if metadata.get("target") != expected["target"]:
            mismatches.append("target")
        if metadata.get("workload") != expected["workload"]:
            mismatches.append("workload")
        if mismatches:
            raise ArtifactValidationError(
                "JMX artifact is stale or inconsistent with the approved plan: "
                + ", ".join(mismatches)
            )

        result = {
            "status": "VALID",
            "scenario": expected["scenario"],
            "plan": str(plan_path),
            "jmx": str(jmx_path),
            "metadata": str(meta_path),
            "target": expected["target"],
            "workload": expected["workload"],
        }

    except (
        ArtifactValidationError,
        PlanValidationError,
        KeyError,
        TypeError,
        ValueError,
        OSError,
        yaml.YAMLError,
    ) as exc:
        if args.json:
            print(json.dumps({"status": "INVALID", "error": str(exc)}, indent=2))
        else:
            print(f"JMX ARTIFACT INVALID: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("=" * 62)
        print("JMX ARTIFACT VALIDATION")
        print("=" * 62)
        print(f"Scenario : {result['scenario']}")
        print(f"Plan     : {result['plan']}")
        print(f"JMX      : {result['jmx']}")
        print(f"Metadata : {result['metadata']}")
        print("Plan hash: MATCH")
        print("JMX hash : MATCH")
        print("Target   : MATCH")
        print("Workload : MATCH")
        print("XML      : VALID")
        print("=" * 62)
        print("JMX ARTIFACT VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
