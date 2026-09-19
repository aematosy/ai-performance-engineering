#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


class ValidationError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except FileNotFoundError as exc:
        raise ValidationError(
            f"File not found: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(
            f"Invalid JSON: {path}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ValidationError(
            f"JSON root must be object: {path}"
        )

    return data


def text_of(
    element: ET.Element,
    name: str,
) -> str | None:
    for child in element:
        if (
            child.tag == "stringProp"
            and child.attrib.get("name")
            == name
        ):
            return child.text or ""

    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate multi-request Postman JMX structure, "
            "correlations, data and secret safety."
        )
    )

    parser.add_argument(
        "--model",
        required=True,
    )
    parser.add_argument(
        "--jmx",
        required=True,
    )
    parser.add_argument(
        "--csv",
        required=True,
    )

    args = parser.parse_args()

    errors: list[str] = []

    try:
        model = load_json(
            Path(args.model).expanduser().resolve()
        )
        jmx_path = Path(
            args.jmx
        ).expanduser().resolve()
        csv_path = Path(
            args.csv
        ).expanduser().resolve()

        if not jmx_path.is_file():
            raise ValidationError(
                f"JMX not found: {jmx_path}"
            )

        if not csv_path.is_file():
            raise ValidationError(
                f"CSV not found: {csv_path}"
            )

        tree = ET.parse(
            jmx_path
        )
        root = tree.getroot()

        samplers = root.findall(
            ".//HTTPSamplerProxy"
        )

        expected_requests = model.get(
            "requests",
            [],
        )

        if len(samplers) != len(
            expected_requests
        ):
            errors.append(
                "Request count mismatch: "
                f"expected {len(expected_requests)}, "
                f"found {len(samplers)}."
            )

        sampler_map = {
            sampler.attrib.get(
                "testname"
            ): sampler
            for sampler in samplers
        }

        for request in expected_requests:
            request_id = request["id"]

            if request_id not in sampler_map:
                errors.append(
                    f"Missing sampler: {request_id}"
                )
                continue

            sampler = sampler_map[
                request_id
            ]

            path = text_of(
                sampler,
                "HTTPSampler.path",
            ) or ""

            expected_path = (
                request.get(
                    "path",
                    "",
                )
            )

            if request.get("query"):
                expected_path += (
                    "?"
                    + request[
                        "query"
                    ]
                )

            if path != expected_path:
                errors.append(
                    f"Path mismatch for {request_id}: "
                    f"{path} != {expected_path}"
                )

        jmx_text = jmx_path.read_text(
            encoding="utf-8"
        )

        for correlation in model.get(
            "correlations",
            [],
        ) or []:
            variable = correlation.get(
                "runtime_variable"
            )
            json_path = correlation.get(
                "json_path"
            )

            if not variable:
                continue

            if (
                f"JSONPostProcessor.referenceNames"
                not in jmx_text
                or variable not in jmx_text
            ):
                errors.append(
                    f"Missing extractor variable: {variable}"
                )

            if (
                json_path
                and json_path
                not in jmx_text
            ):
                errors.append(
                    f"Missing extractor JSONPath: "
                    f"{variable} -> {json_path}"
                )

            for consumer in correlation.get(
                "consumers",
                [],
            ) or []:
                request = next(
                    (
                        item
                        for item
                        in expected_requests
                        if item.get("id")
                        == consumer
                    ),
                    None,
                )

                if not request:
                    continue

                serialized = json.dumps(
                    request,
                    ensure_ascii=False,
                )

                if (
                    "${" + variable + "}"
                    not in serialized
                    and correlation.get("source")
                    == "INFERRED_RESOURCE_LIFECYCLE"
                ):
                    errors.append(
                        f"Consumer does not use "
                        f"${{{variable}}}: {consumer}"
                    )

        # No static resource-id tail should remain for inferred resource consumers.
        inferred = [
            item
            for item in model.get(
                "correlations",
                [],
            ) or []
            if item.get("source")
            == "INFERRED_RESOURCE_LIFECYCLE"
        ]

        for item in inferred:
            for consumer in item.get(
                "consumers",
                [],
            ) or []:
                request = next(
                    (
                        req
                        for req in expected_requests
                        if req.get("id")
                        == consumer
                    ),
                    None,
                )

                if not request:
                    continue

                path = str(
                    request.get(
                        "path",
                        "",
                    )
                )

                if re.search(
                    r"/\d+$",
                    path,
                ):
                    errors.append(
                        f"Static numeric resource id remains: "
                        f"{consumer} -> {path}"
                    )

        # Secret values must never be persisted in the executable model.
        model_text = json.dumps(
            model,
            ensure_ascii=False,
        )

        for secret_prop in model.get(
            "secrets",
            {},
        ).get(
            "jmeter_properties",
            [],
        ):
            marker = (
                "${__P("
                + secret_prop
                + ",)}"
            )

            if marker not in model_text:
                errors.append(
                    f"Secret property is declared but "
                    f"not referenced: {secret_prop}"
                )

        csv_header = (
            csv_path.read_text(
                encoding="utf-8"
            )
            .splitlines()[0]
            if csv_path.stat().st_size
            else ""
        )

        for forbidden in (
            "access_token",
            "booking_id",
            "password",
        ):
            if forbidden in (
                csv_header.lower()
            ):
                errors.append(
                    f"Forbidden runtime/secret field "
                    f"in CSV: {forbidden}"
                )

    except (
        ValidationError,
        ET.ParseError,
        OSError,
    ) as exc:
        print(
            f"POSTMAN JMX VALIDATION ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    status = (
        "PASS"
        if not errors
        else "FAIL"
    )

    print("=" * 72)
    print("POSTMAN MULTI-REQUEST JMX VALIDATION")
    print("=" * 72)
    print(
        f"Status       : {status}"
    )
    print(
        f"Requests     : {len(samplers)}"
    )
    print(
        f"Correlations : "
        f"{len(model.get('correlations', []))}"
    )
    print(
        f"Errors       : {len(errors)}"
    )

    for error in errors:
        print()
        print(
            f"[ERROR] {error}"
        )

    print("=" * 72)

    if errors:
        print(
            "JMX NOT READY FOR EXECUTION"
        )
        return 2

    print(
        "JMX STRUCTURE AND CORRELATIONS VALID"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
