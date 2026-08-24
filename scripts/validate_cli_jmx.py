#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


class CliJmxValidationError(RuntimeError):
    pass


def load_model(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except FileNotFoundError as exc:
        raise CliJmxValidationError(
            f"Executable model not found: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise CliJmxValidationError(
            f"Invalid executable model JSON: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise CliJmxValidationError(
            "Executable model root must be an object."
        )

    return payload


def string_prop(
    node: ET.Element,
    name: str,
) -> str:
    child = node.find(
        f"./stringProp[@name='{name}']"
    )

    if child is None:
        return ""

    return (
        child.text
        or ""
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a NORMALIZED_CLI executable "
            "model against its generated JMX."
        )
    )

    parser.add_argument(
        "--model",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--jmx",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    model_path = (
        args.model.expanduser().resolve()
    )
    jmx_path = (
        args.jmx.expanduser().resolve()
    )

    try:
        model = load_model(
            model_path
        )

        source = model.get("source")

        if not isinstance(source, dict):
            raise CliJmxValidationError(
                "Executable model source is missing."
            )

        if (
            str(
                source.get("type", "")
            ).strip().upper()
            != "NORMALIZED_CLI"
        ):
            raise CliJmxValidationError(
                "CLI JMX validator only accepts "
                "source.type NORMALIZED_CLI."
            )

        candidate = model.get(
            "scenario_candidate"
        )

        if not isinstance(candidate, dict):
            raise CliJmxValidationError(
                "scenario_candidate is missing."
            )

        scenario = str(
            candidate.get("id", "")
        ).strip()

        if not scenario:
            raise CliJmxValidationError(
                "scenario_candidate.id is missing."
            )

        requests = model.get("requests")

        if (
            not isinstance(requests, list)
            or not requests
        ):
            raise CliJmxValidationError(
                "Executable model has no requests."
            )

        if not jmx_path.is_file():
            raise CliJmxValidationError(
                f"JMX not found: {jmx_path}"
            )

        try:
            root = ET.parse(
                jmx_path
            ).getroot()
        except ET.ParseError as exc:
            raise CliJmxValidationError(
                f"Invalid JMX XML: {exc}"
            ) from exc

        samplers = list(
            root.iter(
                "HTTPSamplerProxy"
            )
        )

        if len(samplers) != len(requests):
            raise CliJmxValidationError(
                "Request/sampler count mismatch: "
                f"model={len(requests)}, "
                f"jmx={len(samplers)}"
            )

        for index, (
            request,
            sampler,
        ) in enumerate(
            zip(
                requests,
                samplers,
                strict=True,
            ),
            start=1,
        ):
            if not isinstance(
                request,
                dict,
            ):
                raise CliJmxValidationError(
                    f"Request {index} is invalid."
                )

            expected_method = str(
                request.get(
                    "method",
                    "",
                )
            ).strip().upper()

            expected_path = str(
                request.get(
                    "path",
                    "",
                )
            ).strip()

            actual_method = string_prop(
                sampler,
                "HTTPSampler.method",
            ).upper()

            actual_path = string_prop(
                sampler,
                "HTTPSampler.path",
            )

            if (
                expected_method
                != actual_method
            ):
                raise CliJmxValidationError(
                    f"Request {index} method mismatch: "
                    f"{expected_method} != "
                    f"{actual_method}"
                )

            if (
                expected_path
                != actual_path
            ):
                raise CliJmxValidationError(
                    f"Request {index} path mismatch: "
                    f"{expected_path} != "
                    f"{actual_path}"
                )

        print("=" * 70)
        print("CLI EXECUTABLE MODEL VS JMX")
        print("=" * 70)
        print(f"Scenario : {scenario}")
        print(
            f"Requests : {len(requests)}"
        )
        print(
            f"Samplers : {len(samplers)}"
        )
        print("Status   : PASS")
        print("=" * 70)

        return 0

    except (
        CliJmxValidationError,
        OSError,
    ) as exc:
        print(
            "CLI JMX VALIDATION ERROR: "
            f"{exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
