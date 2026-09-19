#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SUPPORTED_TYPES = {
    "POSTMAN",
    "JMX",
    "CLI",
}


class InputDetectionError(RuntimeError):
    pass


def detect_input_type(path: Path | None, forced: str | None) -> str:
    if forced:
        forced_upper = forced.strip().upper()
        if forced_upper not in SUPPORTED_TYPES:
            raise InputDetectionError(
                f"Unsupported input type: {forced}"
            )
        return forced_upper

    if path is None:
        return "CLI"

    name = path.name.lower()

    if name.endswith(".postman_collection.json"):
        return "POSTMAN"

    if name.endswith(".jmx"):
        return "JMX"

    raise InputDetectionError(
        "Unable to detect input type from file name. "
        "Use --input-type postman|jmx|cli."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect supported performance input type."
    )
    parser.add_argument("--input")
    parser.add_argument(
        "--input-type",
        choices=["postman", "jmx", "cli"],
    )
    parser.add_argument(
        "--json",
        action="store_true",
    )
    args = parser.parse_args()

    path = (
        Path(args.input).expanduser().resolve()
        if args.input
        else None
    )

    try:
        detected = detect_input_type(
            path,
            args.input_type,
        )
    except InputDetectionError as exc:
        print(
            f"INPUT DETECTION ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "input": str(path) if path else None,
                    "input_type": detected,
                },
                indent=2,
            )
        )
    else:
        print(detected)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
