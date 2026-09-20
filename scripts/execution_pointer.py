#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[1]

STATE_DIR = (
    ROOT
    / "results"
    / ".state"
)

POINTER = (
    STATE_DIR
    / "last-execution.json"
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()

    sub = result.add_subparsers(
        dest="operation",
        required=True,
    )

    write = sub.add_parser(
        "write"
    )

    write.add_argument(
        "--scenario",
        required=True,
    )

    write.add_argument(
        "--engine",
        required=True,
    )

    write.add_argument(
        "--results",
        required=True,
    )

    sub.add_parser(
        "read"
    )

    return result


def main() -> int:
    args = parser().parse_args()

    if args.operation == "write":
        STATE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {
            "scenario": args.scenario,
            "engine": args.engine,
            "results": str(
                Path(
                    args.results
                ).resolve()
            ),
            "completed_at": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
        }

        POINTER.write_text(
            json.dumps(
                payload,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        print(
            POINTER
        )

        return 0

    if not POINTER.is_file():
        raise SystemExit(
            "No completed execution pointer exists."
        )

    print(
        POINTER.read_text(
            encoding="utf-8"
        ).strip()
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
