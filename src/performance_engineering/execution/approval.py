#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml


class ApprovalError(RuntimeError):
    pass


GENERIC_APPROVER_NAMES = {
    "user", "human", "operator", "tester", "qa", "approver", "unknown",
    "anonymous", "none", "n/a", "na", "admin",
}


def validate_approver(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ApprovalError("--approved-by must contain an explicit approver identity.")
    if normalized.lower() in GENERIC_APPROVER_NAMES:
        raise ApprovalError(
            "Generic approver identities are not allowed. Provide the explicit human approver name."
        )
    if len(normalized) < 3:
        raise ApprovalError("Approver identity is too short to be auditable.")
    return normalized


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        raise ApprovalError(f"Plan not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ApprovalError("Plan root must be a mapping.")
    return data


def replace_or_append_status(md: str, label: str, value: str) -> str:
    patterns = [
        re.compile(rf"(?im)^(\*\*{re.escape(label)}:\*\*\s*)`?[^\n`]+`?(.*)$"),
        re.compile(rf"(?im)^(-\s*\*\*{re.escape(label)}:\*\*\s*)`?[^\n`]+`?(.*)$"),
        re.compile(rf"(?im)^(-\s*{re.escape(label)}\s*:\s*)`?[^\n`]+`?(.*)$"),
    ]
    for pattern in patterns:
        if pattern.search(md):
            return pattern.sub(lambda m: f"{m.group(1)}`{value}`{m.group(2)}", md, count=1)
    return md.rstrip() + f"\n- **{label}:** `{value}`\n"


def sync_markdown(md_path: Path, plan_status: str, workload_status: str, auth_status: str) -> None:
    if not md_path.is_file():
        raise ApprovalError(f"Missing companion markdown: {md_path}")

    md = md_path.read_text(encoding="utf-8")
    lines = md.splitlines()

    # Remove any previous top-level status lines to avoid accumulating aliases.
    status_pattern = re.compile(
        r"(?i)^\s*(?:-\s*)?(?:\*\*)?"
        r"(?:status|estado|plan status|test plan|test plan status|"
        r"workload|workload status|execution authorization|authorization|"
        r"authorization status|autorizaci[oó]n|estado de autorizaci[oó]n)"
        r"(?:\*\*)?\s*:\s*.*$"
    )
    filtered = [line for line in lines if not status_pattern.match(line)]

    block = [
        f"**Status:** `{plan_status}`",
        f"**Workload Status:** `{workload_status}`",
        f"**Authorization Status:** `{auth_status}`",
    ]

    insert_at = 0
    for idx, line in enumerate(filtered):
        if line.lstrip().startswith("# "):
            insert_at = idx + 1
            break

    canonical = filtered[:insert_at] + [""] + block + [""] + filtered[insert_at:]
    # Collapse excessive blank lines while preserving readable Markdown.
    output: list[str] = []
    blank = False
    for line in canonical:
        if line.strip():
            output.append(line)
            blank = False
        elif not blank:
            output.append("")
            blank = True

    md_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def sync_data_json(data_path: Path, plan_status: str) -> None:
    if not data_path.is_file():
        raise ApprovalError(f"Missing companion data requirements: {data_path}")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ApprovalError("data-requirements.json root must be an object.")
    data["status"] = plan_status
    data_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Approve design/workload and synchronize companion artifacts without authorizing execution.")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--timezone", default="America/Lima")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    path = args.plan.expanduser().resolve()
    plan_dir = path.parent
    md_path = plan_dir / "test-plan.md"
    data_path = plan_dir / "data-requirements.json"

    try:
        approved_by = validate_approver(args.approved_by)
        plan = load_yaml(path)
        current_status = str(plan.get("status", "")).upper()
        if current_status == "APPROVED" and not args.force:
            raise ApprovalError("Plan is already APPROVED. Use --force only to resynchronize companion artifacts intentionally.")

        workload = plan.get("workload")
        authorization = plan.get("authorization")
        if not isinstance(workload, dict):
            raise ApprovalError("Missing workload section.")
        if not isinstance(authorization, dict):
            raise ApprovalError("Missing authorization section.")

        # Back up all three artifacts once before approval/synchronization.
        for artifact in (path, md_path, data_path):
            if not artifact.is_file():
                raise ApprovalError(f"Missing companion artifact: {artifact}")
            backup = artifact.with_suffix(artifact.suffix + ".pre-approval")
            if not backup.exists():
                shutil.copy2(artifact, backup)

        plan["status"] = "APPROVED"
        workload["status"] = "APPROVED"
        approval = plan.setdefault("approval", {})
        approval["approved_by"] = approved_by
        approval["approved_at"] = datetime.now(ZoneInfo(args.timezone)).isoformat()
        approval["scope"] = "DESIGN_AND_WORKLOAD"
        approval["execution_authorized"] = False

        # Explicitly preserve separation from execution authorization.
        authorization["status"] = "PENDING"
        authorization["authorized_by"] = None
        authorization["authorized_at"] = None

        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(yaml.safe_dump(plan, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")
        temp.replace(path)

        sync_data_json(data_path, "APPROVED")
        sync_markdown(md_path, "APPROVED", "APPROVED", "PENDING")

    except (ApprovalError, OSError, yaml.YAMLError, json.JSONDecodeError, ValueError) as exc:
        print(f"APPROVAL ERROR: {exc}", file=sys.stderr)
        return 2

    print("=" * 62)
    print("PERFORMANCE TEST PLAN APPROVAL")
    print("=" * 62)
    print(f"Plan          : {path}")
    print("Plan status   : APPROVED")
    print("Workload      : APPROVED")
    print("Authorization : PENDING")
    print(f"Approved by   : {approved_by}")
    print("Companions    : synchronized")
    print("=" * 62)
    print("DESIGN APPROVED - EXECUTION NOT AUTHORIZED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
