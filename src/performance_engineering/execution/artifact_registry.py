#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class RegistrationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(
            path.read_text(encoding="utf-8")
        )
    except FileNotFoundError as exc:
        raise RegistrationError(
            f"Plan not found: {path}"
        ) from exc

    if not isinstance(data, dict):
        raise RegistrationError(
            "Plan root must be an object."
        )

    return data


def canonical_target(
    plan: dict[str, Any],
) -> dict[str, Any]:
    tx = plan["transactions"][0]
    target = plan["target"]

    return {
        "method": str(
            tx["method"]
        ).upper(),
        "protocol": str(
            target["protocol"]
        ),
        "host": str(
            target["host"]
        ),
        "port": int(
            target["port"]
        ),
        "path": str(
            tx["path"]
        ),
    }


def canonical_workload(
    plan: dict[str, Any],
) -> dict[str, Any]:
    workload = plan[
        "workload"
    ]["parameters"]

    return {
        "threads": int(
            workload["threads"]
        ),
        "ramp_time_seconds": int(
            workload["ramp_time_seconds"]
        ),
        "duration_seconds": int(
            workload["duration_seconds"]
        ),
        "pacing_seconds": float(
            workload.get(
                "pacing_seconds",
                0,
            )
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Register provenance metadata for an existing "
            "approved JMX artifact without regenerating it."
        )
    )

    parser.add_argument(
        "--plan",
        required=True,
    )
    parser.add_argument(
        "--jmx",
        required=True,
    )
    parser.add_argument(
        "--source-type",
        default="EXTERNAL_JMX",
    )
    parser.add_argument(
        "--source-model",
    )

    args = parser.parse_args()

    try:
        plan_path = Path(
            args.plan
        ).expanduser().resolve()

        jmx_path = Path(
            args.jmx
        ).expanduser().resolve()

        if not jmx_path.is_file():
            raise RegistrationError(
                f"JMX not found: {jmx_path}"
            )

        plan = load_yaml(
            plan_path
        )

        if str(
            plan.get("status", "")
        ).upper() != "APPROVED":
            raise RegistrationError(
                "Plan must be APPROVED."
            )

        if str(
            plan.get(
                "workload",
                {},
            ).get(
                "status",
                "",
            )
        ).upper() != "APPROVED":
            raise RegistrationError(
                "Workload must be APPROVED."
            )

        authorization_status = str(
            plan.get(
                "authorization",
                {},
            ).get(
                "status",
                "PENDING",
            )
        ).upper()

        metadata = {
            "schema_version": "1.0",
            "generator_version": "POSTMAN-E2E-1.0",
            "generated_at": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            "scenario": str(
                plan[
                    "metadata"
                ]["name"]
            ),
            "plan_path": str(
                plan_path
            ),
            "jmx_path": str(
                jmx_path
            ),
            "plan_sha256": sha256_file(
                plan_path
            ),
            "jmx_sha256": sha256_file(
                jmx_path
            ),
            "plan_status": "APPROVED",
            "workload_status": "APPROVED",
            "execution_authorization_status": (
                authorization_status
            ),
            "target": canonical_target(
                plan
            ),
            "workload": canonical_workload(
                plan
            ),
            "provenance": {
                "source_type": (
                    args.source_type
                ),
                "source_model": (
                    str(
                        Path(
                            args.source_model
                        )
                        .expanduser()
                        .resolve()
                    )
                    if args.source_model
                    else None
                ),
                "registration_mode": (
                    "REGISTER_EXISTING_ARTIFACT"
                ),
            },
        }

        meta_path = jmx_path.with_suffix(
            jmx_path.suffix
            + ".meta.json"
        )

        meta_path.write_text(
            json.dumps(
                metadata,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    except (
        RegistrationError,
        KeyError,
        TypeError,
        ValueError,
        OSError,
    ) as exc:
        print(
            f"JMX REGISTRATION ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print("=" * 72)
    print("JMX ARTIFACT REGISTRATION")
    print("=" * 72)
    print(f"Scenario      : {metadata['scenario']}")
    print(f"Plan          : {plan_path}")
    print(f"JMX           : {jmx_path}")
    print(f"Metadata      : {meta_path}")
    print(f"Source type   : {args.source_type}")
    print(
        f"Authorization : "
        f"{authorization_status}"
    )
    print("Plan hash     : RECORDED")
    print("JMX hash      : RECORDED")
    print("JMeter run    : NOT EXECUTED")
    print("=" * 72)
    print("JMX ARTIFACT REGISTERED")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
