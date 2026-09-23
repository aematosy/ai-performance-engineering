#!/usr/bin/env python3

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

import yaml


ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

SRC = (
    ROOT
    / "src"
)

if str(SRC) not in sys.path:
    sys.path.insert(
        0,
        str(SRC),
    )

from performance_engineering.execution.runtime_properties import (
    data_requirements_path,
    required_jmeter_properties,
)


def parse_existing(
    path: Path,
) -> dict[str, str]:
    if not path.is_file():
        return {}

    values: dict[str, str] = {}

    for raw in path.read_text(
        encoding="utf-8"
    ).splitlines():
        line = raw.strip()

        if (
            not line
            or line.startswith("#")
            or line.startswith("!")
            or "=" not in line
        ):
            continue

        key, value = line.split(
            "=",
            1,
        )

        values[
            key.strip()
        ] = value.strip()

    return values


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Securely materialize generic JMeter "
            "runtime properties declared by a "
            "performance data contract."
        )
    )

    parser.add_argument(
        "--plan",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    plan_path = (
        args.plan
        .expanduser()
        .resolve()
    )

    plan = yaml.safe_load(
        plan_path.read_text(
            encoding="utf-8"
        )
    )

    requirements = data_requirements_path(
        project_root=ROOT,
        plan_path=plan_path,
        plan=plan,
    )

    if requirements is None:
        print(
            "Runtime properties : NOT REQUIRED"
        )
        return 0

    contract = json.loads(
        requirements.read_text(
            encoding="utf-8"
        )
    )

    required = required_jmeter_properties(
        contract
    )

    if not required:
        print(
            "Runtime properties : NOT REQUIRED"
        )
        return 0

    scenario = str(
        contract.get(
            "scenario",
            "",
        )
        or ""
    ).strip()

    if not scenario:
        raise SystemExit(
            "ERROR: canonical scenario is missing "
            "from data-requirements.json"
        )

    target = (
        ROOT
        / "data"
        / scenario
        / "secrets.properties"
    )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    values = parse_existing(
        target
    )

    print()
    print("=" * 70)
    print("JMETER RUNTIME PROPERTIES")
    print("=" * 70)
    print(
        f"Scenario : {scenario}"
    )
    print(
        f"File     : {target}"
    )
    print(
        f"Required : {len(required)}"
    )
    print()
    print(
        "Secret values will not be displayed."
    )

    changed = False

    for name in required:
        current = values.get(
            name,
            "",
        ).strip()

        if current:
            print(
                f"[OK] {name}: already configured"
            )
            continue

        value = getpass.getpass(
            f"Enter value for {name}: "
        )

        if not value:
            raise SystemExit(
                f"ERROR: {name} cannot be empty."
            )

        values[
            name
        ] = value

        changed = True

    lines = [
        "# Generated locally for governed JMeter execution.",
        "# Secret values must not be committed.",
        "",
    ]

    for name in required:
        lines.append(
            f"{name}={values[name]}"
        )

    target.write_text(
        "\n".join(
            lines
        )
        + "\n",
        encoding="utf-8",
    )

    os.chmod(
        target,
        0o600,
    )

    print()
    print(
        "[OK] Runtime properties configured."
    )
    print(
        "[OK] Secret values were not printed."
    )
    print(
        "[OK] File permissions: 600"
    )
    print(
        "[INFO] Changed:",
        changed,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
