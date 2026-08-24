#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


JMETER_PROPERTY_PATTERN = re.compile(
    r"\$\{__P\((?P<name>[^,\)]+)(?:,(?P<default>[^\)]+))?\)\}"
)


class JmxParseError(RuntimeError):
    pass


def load_xml(path: Path) -> ET.ElementTree:
    try:
        return ET.parse(path)
    except FileNotFoundError as exc:
        raise JmxParseError(f"JMX not found: {path}") from exc
    except ET.ParseError as exc:
        raise JmxParseError(
            f"Invalid JMX/XML: {exc}"
        ) from exc


def prop_text(
    node: ET.Element,
    name: str,
    default: str | None = None,
) -> str | None:
    for child in node:
        if child.tag in {"stringProp", "boolProp"}:
            if child.attrib.get("name") == name:
                return child.text if child.text is not None else ""
    return default


def collection_children(
    node: ET.Element,
    name: str,
) -> list[ET.Element]:
    for child in node:
        if (
            child.tag == "collectionProp"
            and child.attrib.get("name") == name
        ):
            return list(child)
    return []


def parse_property_reference(
    value: str | None,
) -> dict[str, Any]:
    if value is None:
        return {
            "raw": None,
            "source": "MISSING",
            "property": None,
            "default": None,
        }

    match = JMETER_PROPERTY_PATTERN.fullmatch(
        value.strip()
    )
    if not match:
        return {
            "raw": value,
            "source": "HARDCODED",
            "property": None,
            "default": None,
        }

    return {
        "raw": value,
        "source": "JMETER_PROPERTY",
        "property": match.group("name"),
        "default": match.group("default"),
    }


def parse_headers(
    root: ET.Element,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for manager in root.iter("HeaderManager"):
        for element in collection_children(
            manager,
            "HeaderManager.headers",
        ):
            if element.tag != "elementProp":
                continue

            key = prop_text(
                element,
                "Header.name",
                "",
            ) or ""
            value = prop_text(
                element,
                "Header.value",
                "",
            ) or ""

            sensitive = key.lower() in {
                "authorization",
                "cookie",
                "x-api-key",
                "api-key",
            }

            result.append(
                {
                    "key": key,
                    "value": (
                        "<REDACTED>"
                        if sensitive
                        else value
                    ),
                    "sensitive": sensitive,
                }
            )

    return result


def parse_csv_data_sets(
    root: ET.Element,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for node in root.iter("CSVDataSet"):
        result.append(
            {
                "name": node.attrib.get(
                    "testname",
                    "CSV Data Set Config",
                ),
                "filename": prop_text(
                    node,
                    "filename",
                ),
                "variable_names": prop_text(
                    node,
                    "variableNames",
                    "",
                ),
                "delimiter": prop_text(
                    node,
                    "delimiter",
                    ",",
                ),
                "recycle": prop_text(
                    node,
                    "recycle",
                    "true",
                ),
                "stop_thread_on_eof": prop_text(
                    node,
                    "stopThread",
                    "false",
                ),
                "sharing_mode": prop_text(
                    node,
                    "shareMode",
                ),
            }
        )

    return result


def parse_extractors(
    root: ET.Element,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for node in root.iter():
        if node.tag == "JSONPostProcessor":
            result.append(
                {
                    "type": "JSON_PATH",
                    "name": node.attrib.get(
                        "testname",
                    ),
                    "variable": prop_text(
                        node,
                        "JSONPostProcessor.referenceNames",
                    ),
                    "expression": prop_text(
                        node,
                        "JSONPostProcessor.jsonPathExprs",
                    ),
                }
            )

        elif node.tag == "RegexExtractor":
            result.append(
                {
                    "type": "REGEX",
                    "name": node.attrib.get(
                        "testname",
                    ),
                    "variable": prop_text(
                        node,
                        "RegexExtractor.refname",
                    ),
                    "expression": prop_text(
                        node,
                        "RegexExtractor.regex",
                    ),
                }
            )

    return result


def parse_assertions(
    root: ET.Element,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for node in root.iter("ResponseAssertion"):
        patterns = []
        for child in collection_children(
            node,
            "Asserion.test_strings",
        ):
            if child.tag == "stringProp":
                patterns.append(
                    child.text or ""
                )

        result.append(
            {
                "type": "RESPONSE_ASSERTION",
                "name": node.attrib.get(
                    "testname",
                ),
                "field": prop_text(
                    node,
                    "Assertion.test_field",
                ),
                "patterns": patterns,
            }
        )

    return result


def parse_thread_groups(
    root: ET.Element,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for node in root.iter("ThreadGroup"):
        result.append(
            {
                "name": node.attrib.get(
                    "testname",
                    "Thread Group",
                ),
                "threads": parse_property_reference(
                    prop_text(
                        node,
                        "ThreadGroup.num_threads",
                    )
                ),
                "ramp_time_seconds": parse_property_reference(
                    prop_text(
                        node,
                        "ThreadGroup.ramp_time",
                    )
                ),
                "duration_seconds": parse_property_reference(
                    prop_text(
                        node,
                        "ThreadGroup.duration",
                    )
                ),
                "scheduler": prop_text(
                    node,
                    "ThreadGroup.scheduler",
                    "false",
                ),
            }
        )

    return result


def parse_samplers(
    root: ET.Element,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for node in root.iter("HTTPSamplerProxy"):
        result.append(
            {
                "name": node.attrib.get(
                    "testname",
                    "HTTP Request",
                ),
                "method": (
                    prop_text(
                        node,
                        "HTTPSampler.method",
                        "GET",
                    )
                    or "GET"
                ).upper(),
                "protocol": prop_text(
                    node,
                    "HTTPSampler.protocol",
                ),
                "host": prop_text(
                    node,
                    "HTTPSampler.domain",
                ),
                "port": prop_text(
                    node,
                    "HTTPSampler.port",
                ),
                "path": prop_text(
                    node,
                    "HTTPSampler.path",
                ),
                "connect_timeout_ms": prop_text(
                    node,
                    "HTTPSampler.connect_timeout",
                ),
                "response_timeout_ms": prop_text(
                    node,
                    "HTTPSampler.response_timeout",
                ),
            }
        )

    return result


def parse_timers(
    root: ET.Element,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for node in root.iter("ConstantTimer"):
        result.append(
            {
                "type": "CONSTANT",
                "name": node.attrib.get(
                    "testname",
                    "Constant Timer",
                ),
                "delay_ms": prop_text(
                    node,
                    "ConstantTimer.delay",
                ),
            }
        )

    return result


def build_normalized_model(
    path: Path,
    tree: ET.ElementTree,
) -> dict[str, Any]:
    root = tree.getroot()

    thread_groups = parse_thread_groups(
        root
    )
    samplers = parse_samplers(root)
    csv_data = parse_csv_data_sets(root)
    extractors = parse_extractors(root)
    assertions = parse_assertions(root)
    timers = parse_timers(root)
    headers = parse_headers(root)

    findings: list[dict[str, Any]] = []

    for group in thread_groups:
        for field in (
            "threads",
            "ramp_time_seconds",
            "duration_seconds",
        ):
            meta = group.get(field, {})
            if (
                isinstance(meta, dict)
                and meta.get("source")
                == "HARDCODED"
            ):
                findings.append(
                    {
                        "severity": "WARNING",
                        "code": (
                            "HARDCODED_EXECUTION_PARAMETER"
                        ),
                        "location": (
                            f"thread_group:{group['name']}:{field}"
                        ),
                        "message": (
                            f"{field} is hardcoded in the JMX."
                        ),
                    }
                )

    model = {
        "schema_version": "1.0",
        "source": {
            "type": "JMX",
            "artifact": str(path),
        },
        "system": {
            "type": "API",
        },
        "scenarios": [
            {
                "name": path.stem,
                "transactions": samplers,
            }
        ],
        "data": {
            "strategy": (
                "CSV"
                if csv_data
                else "NONE_OR_EMBEDDED"
            ),
            "csv_data_sets": csv_data,
            "parameters": [],
        },
        "runtime": {
            "correlations": extractors,
        },
        "workload": {
            "source": "JMX",
            "thread_groups": thread_groups,
        },
        "assertions": assertions,
        "timers": timers,
        "headers": headers,
        "observability": [],
        "risks": [],
        "findings": findings,
        "summary": {
            "thread_group_count": len(
                thread_groups
            ),
            "transaction_count": len(
                samplers
            ),
            "csv_data_set_count": len(
                csv_data
            ),
            "correlation_count": len(
                extractors
            ),
            "assertion_count": len(
                assertions
            ),
            "timer_count": len(timers),
            "finding_count": len(findings),
        },
    }

    return model


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Parse an existing Apache JMeter JMX "
            "into the normalized performance model."
        )
    )
    parser.add_argument(
        "--jmx",
        required=True,
    )
    parser.add_argument(
        "--output",
        required=True,
    )
    args = parser.parse_args()

    jmx_path = (
        Path(args.jmx)
        .expanduser()
        .resolve()
    )
    output_path = (
        Path(args.output)
        .expanduser()
        .resolve()
    )

    try:
        tree = load_xml(jmx_path)
        model = build_normalized_model(
            jmx_path,
            tree,
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        output_path.write_text(
            json.dumps(
                model,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    except JmxParseError as exc:
        print(
            f"JMX PARSE ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print("=" * 70)
    print("JMX NORMALIZATION")
    print("=" * 70)
    print(f"JMX           : {jmx_path}")
    print(
        "Thread groups :",
        model["summary"][
            "thread_group_count"
        ],
    )
    print(
        "Transactions  :",
        model["summary"][
            "transaction_count"
        ],
    )
    print(
        "CSV datasets  :",
        model["summary"][
            "csv_data_set_count"
        ],
    )
    print(
        "Correlations  :",
        model["summary"][
            "correlation_count"
        ],
    )
    print(
        "Assertions    :",
        model["summary"][
            "assertion_count"
        ],
    )
    print(
        "Findings      :",
        model["summary"][
            "finding_count"
        ],
    )
    print(f"Output        : {output_path}")
    print("=" * 70)
    print("JMX NORMALIZATION COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
