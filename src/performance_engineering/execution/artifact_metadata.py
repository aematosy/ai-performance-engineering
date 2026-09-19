#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from generate_jmx_from_plan import (
    build_metadata,
    metadata_path_for,
    write_metadata,
)


class MetadataRefreshError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh governed JMX metadata for an existing "
            "JMX without regenerating or executing it."
        )
    )

    parser.add_argument(
        "--plan",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--jmx",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    plan_path = (
        args.plan
        .expanduser()
        .resolve()
    )

    jmx_path = (
        args.jmx
        .expanduser()
        .resolve()
    )

    if not plan_path.is_file():
        raise MetadataRefreshError(
            f"Plan not found: {plan_path}"
        )

    if not jmx_path.is_file():
        raise MetadataRefreshError(
            f"JMX not found: {jmx_path}"
        )

    plan = yaml.safe_load(
        plan_path.read_text(
            encoding="utf-8"
        )
    )

    metadata = build_metadata(
        plan_path=plan_path,
        jmx_path=jmx_path,
        plan=plan,
    )

    meta_path = metadata_path_for(
        jmx_path
    )

    write_metadata(
        meta_path,
        metadata,
    )

    print("=" * 72)
    print("JMX METADATA REFRESH")
    print("=" * 72)
    print(f"Plan     : {plan_path}")
    print(f"JMX      : {jmx_path}")
    print(f"Metadata : {meta_path}")
    print(
        f"Plan     : "
        f"{metadata['plan_status']}"
    )
    print(
        f"Workload : "
        f"{metadata['workload_status']}"
    )
    print(
        f"Auth     : "
        f"{metadata['execution_authorization_status']}"
    )
    print("=" * 72)
    print("JMX METADATA REFRESHED")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
