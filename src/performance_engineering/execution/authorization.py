#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


GENERIC_IDENTITIES = {
    "user",
    "admin",
    "administrator",
    "qa",
    "tester",
    "operator",
    "unknown",
    "n/a",
    "na",
}


class AuthorizationError(RuntimeError):
    pass


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AuthorizationError(f"Plan not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise AuthorizationError(f"Invalid YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise AuthorizationError("Plan root must be an object.")

    return data


def require_explicit_human(value: str) -> str:
    normalized = value.strip()

    if not normalized:
        raise AuthorizationError("--authorized-by is required.")

    if normalized.lower() in GENERIC_IDENTITIES:
        raise AuthorizationError(
            "Generic authorization identities are not allowed. "
            "Provide the explicit human approver name."
        )

    return normalized


def validate_preconditions(plan: dict[str, Any]) -> None:
    if str(plan.get("status", "")).strip().upper() != "APPROVED":
        raise AuthorizationError(
            "Plan must be APPROVED before execution authorization."
        )

    workload = plan.get("workload")
    if not isinstance(workload, dict):
        raise AuthorizationError("Plan workload section is missing.")

    if str(workload.get("status", "")).strip().upper() != "APPROVED":
        raise AuthorizationError(
            "Workload must be APPROVED before execution authorization."
        )

    approval = plan.get("approval")
    if not isinstance(approval, dict):
        raise AuthorizationError("Plan approval section is missing.")

    if not approval.get("approved_by"):
        raise AuthorizationError(
            "Plan approval.approved_by is required before execution authorization."
        )

    if not approval.get("approved_at"):
        raise AuthorizationError(
            "Plan approval.approved_at is required before execution authorization."
        )


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())

        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    content = yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        width=1000,
    )
    atomic_write_text(path, content)


def sync_markdown(
    md_path: Path,
    *,
    plan_status: str,
    workload_status: str,
    authorization_status: str,
    authorized_by: str,
    authorized_at: str,
) -> None:
    if not md_path.is_file():
        raise AuthorizationError(
            f"Missing companion markdown: {md_path}"
        )

    md = md_path.read_text(encoding="utf-8")
    lines = md.splitlines()

    status_pattern = re.compile(
        r"(?i)^\s*(?:-\s*)?(?:\*\*)?"
        r"(?:status|estado|plan status|test plan|test plan status|"
        r"workload|workload status|execution authorization|authorization|"
        r"authorization status|autorizaci[oó]n|estado de autorizaci[oó]n|"
        r"authorized by|authorized at)"
        r"(?:\*\*)?\s*:\s*.*$"
    )

    filtered = [
        line
        for line in lines
        if not status_pattern.match(line)
    ]

    block = [
        f"**Status:** `{plan_status}`",
        f"**Workload Status:** `{workload_status}`",
        f"**Authorization Status:** `{authorization_status}`",
        f"**Authorized By:** `{authorized_by}`",
        f"**Authorized At:** `{authorized_at}`",
    ]

    insert_at = 0

    for index, line in enumerate(filtered):
        if line.lstrip().startswith("# "):
            insert_at = index + 1
            break

    canonical = (
        filtered[:insert_at]
        + [""]
        + block
        + [""]
        + filtered[insert_at:]
    )

    output: list[str] = []
    previous_blank = False

    for line in canonical:
        if line.strip():
            output.append(line)
            previous_blank = False
        elif not previous_blank:
            output.append("")
            previous_blank = True

    atomic_write_text(
        md_path,
        "\n".join(output).rstrip() + "\n",
    )


def backup_once(path: Path, suffix: str) -> Path:
    backup = path.with_suffix(
        path.suffix + suffix
    )

    if not backup.exists():
        shutil.copy2(path, backup)

    return backup


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Grant explicit execution authorization to an already-approved "
            "performance test plan and synchronize its companion Markdown. "
            "This command never executes JMeter."
        )
    )

    parser.add_argument("--plan", required=True)
    parser.add_argument("--authorized-by", required=True)
    parser.add_argument("--notes")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing AUTHORIZED execution state intentionally.",
    )

    args = parser.parse_args()

    plan_path = Path(args.plan).expanduser().resolve()
    md_path = plan_path.parent / "test-plan.md"

    try:
        authorized_by = require_explicit_human(
            args.authorized_by
        )
        plan = load_yaml(plan_path)
        validate_preconditions(plan)

        if not md_path.is_file():
            raise AuthorizationError(
                f"Missing companion markdown: {md_path}"
            )

        authorization = plan.get("authorization")

        if not isinstance(authorization, dict):
            authorization = {}
            plan["authorization"] = authorization

        approval = plan.get("approval")

        if not isinstance(approval, dict):
            raise AuthorizationError(
                "Plan approval section is missing."
            )

        current_status = str(
            authorization.get("status", "")
        ).strip().upper()

        if (
            current_status == "AUTHORIZED"
            and not args.force
        ):
            raise AuthorizationError(
                "Execution is already AUTHORIZED. "
                "Use --force only to intentionally resynchronize "
                "authorization metadata and companion Markdown."
            )

        timestamp = (
            datetime.now()
            .astimezone()
            .isoformat()
        )

        plan_backup = backup_once(
            plan_path,
            ".pre-authorization",
        )
        md_backup = backup_once(
            md_path,
            ".pre-authorization",
        )

        authorization["required"] = True
        authorization["status"] = "AUTHORIZED"
        authorization["authorized_by"] = authorized_by
        authorization["authorized_at"] = timestamp

        if args.notes is not None:
            authorization["notes"] = (
                args.notes.strip()
            )
        else:
            authorization["notes"] = (
                "Execution explicitly authorized after design/workload "
                "approval. Final execution still requires controlled-runner "
                "preflight, artifact hash verification, and human RUN "
                "confirmation."
            )

        approval[
            "execution_authorized"
        ] = True

        atomic_write_yaml(
            plan_path,
            plan,
        )

        sync_markdown(
            md_path,
            plan_status="APPROVED",
            workload_status="APPROVED",
            authorization_status="AUTHORIZED",
            authorized_by=authorized_by,
            authorized_at=timestamp,
        )

    except (
        AuthorizationError,
        OSError,
    ) as exc:
        print(
            f"AUTHORIZATION ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print("=" * 72)
    print(
        "PERFORMANCE EXECUTION AUTHORIZATION v1.1"
    )
    print("=" * 72)
    print(f"Plan          : {plan_path}")
    print(f"Markdown      : {md_path}")
    print("Plan status   : APPROVED")
    print("Workload      : APPROVED")
    print("Authorization : AUTHORIZED")
    print(f"Authorized by : {authorized_by}")
    print(f"Authorized at : {timestamp}")
    print("Exec flag     : True")
    print(f"Plan backup   : {plan_backup}")
    print(f"MD backup     : {md_backup}")
    print("Companions    : synchronized")
    print("JMeter run    : NOT EXECUTED")
    print("=" * 72)
    print("AUTHORIZATION RECORDED")
    print()
    print(
        "IMPORTANT: the plan hash changed. Regenerate the JMX artifact and "
        "its metadata before the next controlled preflight."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
