#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import yaml


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()

    result.add_argument(
        "--plan",
        required=True,
    )

    result.add_argument(
        "--curl",
        required=True,
    )

    return result


def run_probe(
    curl_file: Path,
) -> int:
    raw = curl_file.read_text(
        encoding="utf-8"
    ).strip()

    if not raw.startswith("curl "):
        raise RuntimeError(
            "Functional probe requires a cURL input."
        )

    command = (
        raw
        + " --silent"
        + " --show-error"
        + " --output /dev/null"
        + " --write-out '%{http_code}'"
    )

    completed = subprocess.run(
        [
            "/bin/bash",
            "-lc",
            command,
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "Functional probe failed: "
            + completed.stderr.strip()
        )

    value = completed.stdout.strip()

    if not value.isdigit():
        raise RuntimeError(
            f"Invalid HTTP probe response: {value!r}"
        )

    return int(value)


def main() -> int:
    args = parser().parse_args()

    plan_path = Path(
        args.plan
    ).resolve()

    curl_path = Path(
        args.curl
    ).resolve()

    payload = yaml.safe_load(
        plan_path.read_text(
            encoding="utf-8"
        )
    )

    transactions = payload.get(
        "transactions",
        [],
    )

    if not transactions:
        raise RuntimeError(
            "Plan contains no transactions."
        )

    unresolved = [
        transaction
        for transaction in transactions
        if str(
            transaction.get(
                "expected_status",
                "",
            )
        ).upper()
        in {
            "",
            "NONE",
            "UNRESOLVED",
        }
    ]

    if not unresolved:
        print(
            "[OK] HTTP response contract already resolved."
        )
        return 0

    status = run_probe(
        curl_path
    )

    print(
        "Functional probe observed HTTP:",
        status,
    )

    if not 200 <= status <= 299:
        print(
            "HTTP contract remains unresolved."
        )
        print(
            "Human confirmation is required."
        )
        return 2

    for transaction in unresolved:
        transaction[
            "expected_status"
        ] = status

    assertions = payload.get(
        "assertions"
    ) or []

    assertions = [
        item
        for item in assertions
        if item.get("type")
        != "RESPONSE_CODE"
    ]

    for transaction in unresolved:
        assertions.append(
            {
                "type": "RESPONSE_CODE",
                "expected_value": str(status),
                "description": (
                    "Validate expected HTTP response for "
                    f"{transaction.get('name', '')}."
                ),
            }
        )

    payload[
        "assertions"
    ] = assertions

    open_questions = payload.get(
        "open_questions"
    ) or []

    payload[
        "open_questions"
    ] = [
        question
        for question in open_questions
        if "[RESPONSE_CONTRACT]"
        not in str(question)
    ]

    plan_path.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    print(
        "[OK] Expected HTTP contract:",
        status,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
