#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from config_loader import ConfigLoader, load_config
from generate_jmx import build_jmx_tree, normalize_scenario_name
from validate_test_plan import PlanValidationError, load_plan, validate_plan


GENERATOR_VERSION = "2.0"


class PlanGenerationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PlanGenerationError(f"Invalid JSON metadata: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PlanGenerationError(f"Metadata root must be an object: {path}")
    return payload


def metadata_path_for(jmx_path: Path) -> Path:
    return jmx_path.with_suffix(jmx_path.suffix + ".meta.json")


def load_data_defaults(plan: dict[str, Any], project_root: Path) -> dict[str, Any]:
    data = plan.get("data", {})
    requirements_file = data.get("requirements_file")
    if not requirements_file:
        return {}

    path = Path(str(requirements_file)).expanduser()
    if not path.is_absolute():
        path = project_root / path
    if not path.is_file():
        raise PlanGenerationError(f"Data requirements file not found: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PlanGenerationError(
            f"Invalid data requirements JSON: {exc}"
        ) from exc

    defaults: dict[str, Any] = {}
    parameters = payload.get("requirements", {}).get("parameters", [])
    for parameter in parameters:
        if not isinstance(parameter, dict):
            continue
        name = parameter.get("name")
        if name and "example" in parameter:
            defaults[str(name)] = parameter["example"]
    return defaults


def add_user_variable(collection: ET.Element, name: str, value: Any) -> None:
    argument = ET.SubElement(
        collection,
        "elementProp",
        {"name": name, "elementType": "Argument"},
    )
    child = ET.SubElement(argument, "stringProp", {"name": "Argument.name"})
    child.text = name
    child = ET.SubElement(argument, "stringProp", {"name": "Argument.value"})
    child.text = str(value)
    child = ET.SubElement(argument, "stringProp", {"name": "Argument.metadata"})
    child.text = "="


def configure_user_variables(tree: ET.ElementTree, defaults: dict[str, Any]) -> None:
    if not defaults:
        return
    collection = tree.find(
        ".//elementProp[@name='TestPlan.user_defined_variables']/"
        "collectionProp[@name='Arguments.arguments']"
    )
    if collection is None:
        raise PlanGenerationError("Generated JMX does not contain TestPlan user variables.")
    for name, value in defaults.items():
        add_user_variable(collection, name, value)


def configure_headers(tree: ET.ElementTree, headers: dict[str, Any]) -> None:
    collection = tree.find(
        ".//HeaderManager/collectionProp[@name='HeaderManager.headers']"
    )
    if collection is None:
        raise PlanGenerationError("Generated JMX has no HeaderManager.")

    existing: dict[str, ET.Element] = {}
    for element in collection.findall("elementProp"):
        name_prop = element.find("stringProp[@name='Header.name']")
        if name_prop is not None and name_prop.text:
            existing[name_prop.text.lower()] = element

    for name, value in headers.items():
        key = str(name).lower()
        if key in existing:
            value_prop = existing[key].find("stringProp[@name='Header.value']")
            if value_prop is not None:
                value_prop.text = str(value)
            continue
        element = ET.SubElement(
            collection,
            "elementProp",
            {"name": str(name), "elementType": "Header"},
        )
        name_prop = ET.SubElement(element, "stringProp", {"name": "Header.name"})
        name_prop.text = str(name)
        value_prop = ET.SubElement(element, "stringProp", {"name": "Header.value"})
        value_prop.text = str(value)


def configure_raw_body(tree: ET.ElementTree, body: str) -> None:
    sampler = tree.find(".//HTTPSamplerProxy")
    if sampler is None:
        raise PlanGenerationError("Generated JMX has no HTTP sampler.")

    arguments = ET.Element(
        "elementProp",
        {"name": "HTTPsampler.Arguments", "elementType": "Arguments"},
    )
    collection = ET.SubElement(
        arguments,
        "collectionProp",
        {"name": "Arguments.arguments"},
    )
    argument = ET.SubElement(
        collection,
        "elementProp",
        {"name": "", "elementType": "HTTPArgument"},
    )
    prop = ET.SubElement(argument, "boolProp", {"name": "HTTPArgument.always_encode"})
    prop.text = "false"
    prop = ET.SubElement(argument, "stringProp", {"name": "Argument.value"})
    prop.text = body.strip()
    prop = ET.SubElement(argument, "stringProp", {"name": "Argument.metadata"})
    prop.text = "="
    prop = ET.SubElement(argument, "boolProp", {"name": "HTTPArgument.use_equals"})
    prop.text = "true"
    sampler.insert(0, arguments)

    post_body = sampler.find("boolProp[@name='HTTPSampler.postBodyRaw']")
    if post_body is None:
        post_body = ET.SubElement(
            sampler,
            "boolProp",
            {"name": "HTTPSampler.postBodyRaw"},
        )
    post_body.text = "true"


def find_sampler_tree(tree: ET.ElementTree) -> ET.Element:
    root = tree.getroot()
    for parent in root.iter():
        children = list(parent)
        for index, child in enumerate(children):
            if child.tag == "HTTPSamplerProxy":
                if index + 1 < len(children) and children[index + 1].tag == "hashTree":
                    return children[index + 1]
    raise PlanGenerationError("Could not locate sampler hashTree.")


def add_json_extractor(
    sampler_tree: ET.Element,
    *,
    variable: str,
    expression: str,
    fallback: str,
) -> None:
    extractor = ET.SubElement(
        sampler_tree,
        "JSONPostProcessor",
        {
            "guiclass": "JSONPostProcessorGui",
            "testclass": "JSONPostProcessor",
            "testname": f"Extract {variable}",
            "enabled": "true",
        },
    )
    props = {
        "JSONPostProcessor.referenceNames": variable,
        "JSONPostProcessor.jsonPathExprs": expression,
        "JSONPostProcessor.match_numbers": "1",
        "JSONPostProcessor.defaultValues": fallback,
    }
    for name, value in props.items():
        prop = ET.SubElement(extractor, "stringProp", {"name": name})
        prop.text = value
    ET.SubElement(sampler_tree, "hashTree")


def add_response_body_regex_assertion(
    sampler_tree: ET.Element,
    *,
    name: str,
    regex: str,
) -> None:
    assertion = ET.SubElement(
        sampler_tree,
        "ResponseAssertion",
        {
            "guiclass": "AssertionGui",
            "testclass": "ResponseAssertion",
            "testname": name,
            "enabled": "true",
        },
    )
    patterns = ET.SubElement(
        assertion,
        "collectionProp",
        {"name": "Asserion.test_strings"},
    )
    prop = ET.SubElement(patterns, "stringProp", {"name": "0"})
    prop.text = regex
    prop = ET.SubElement(assertion, "stringProp", {"name": "Assertion.custom_message"})
    prop.text = name
    prop = ET.SubElement(assertion, "boolProp", {"name": "Assertion.assume_success"})
    prop.text = "false"
    prop = ET.SubElement(assertion, "stringProp", {"name": "Assertion.test_field"})
    prop.text = "Assertion.response_data"
    prop = ET.SubElement(assertion, "intProp", {"name": "Assertion.test_type"})
    prop.text = "2"
    ET.SubElement(sampler_tree, "hashTree")


def add_pacing_timer(tree: ET.ElementTree, pacing_seconds: float) -> None:
    if pacing_seconds <= 0:
        return
    root = tree.getroot()
    for parent in root.iter():
        children = list(parent)
        for index, child in enumerate(children):
            if child.tag == "HTTPSamplerProxy":
                timer = ET.Element(
                    "ConstantTimer",
                    {
                        "guiclass": "ConstantTimerGui",
                        "testclass": "ConstantTimer",
                        "testname": "Pacing",
                        "enabled": "true",
                    },
                )
                prop = ET.SubElement(timer, "stringProp", {"name": "ConstantTimer.delay"})
                default_ms = int(pacing_seconds * 1000)
                prop.text = f"${{__P(pacing_ms,{default_ms})}}"
                parent.insert(index, timer)
                parent.insert(index + 1, ET.Element("hashTree"))
                return
    raise PlanGenerationError("Could not place pacing timer.")


def enforce_supported_plan(plan: dict[str, Any]) -> None:
    transactions = plan.get("transactions", [])
    if len(transactions) != 1:
        raise PlanGenerationError(
            "This bridge currently supports exactly one HTTP transaction. "
            "Extend the generator before approving a multi-transaction plan."
        )
    auth_type = str(plan.get("authentication", {}).get("type", "NONE")).upper()
    if auth_type != "NONE":
        raise PlanGenerationError(
            f"Authentication type {auth_type} is not supported by the current plan-to-JMX bridge."
        )
    for assertion in plan.get("assertions", []):
        if str(assertion.get("type", "")).upper() == "JSON_PATH":
            expression = str(assertion.get("expression", ""))
            if expression != "$.id":
                raise PlanGenerationError(
                    "Current bridge supports JSON_PATH assertion only for $.id."
                )
    for extractor in plan.get("correlations", {}).get("extractors", []):
        if str(extractor.get("type", "")).upper() != "JSON_PATH":
            raise PlanGenerationError("Current bridge supports only JSON_PATH extractors.")


def resolve_output(config: ConfigLoader, scenario: str, output_arg: Path | None) -> Path:
    generated = config.get_path(
        "paths.generated_jmx_directory",
        required=True,
        create=True,
        directory=True,
    )
    assert generated is not None
    if output_arg is None:
        output = generated / f"{normalize_scenario_name(scenario)}.jmx"
    else:
        output = output_arg.expanduser()
        if not output.is_absolute():
            output = config.project_root / output
    output = output.resolve()
    output.relative_to(generated.resolve())
    if output.suffix.lower() != ".jmx":
        raise PlanGenerationError("Output file must use .jmx extension.")
    return output


def artifact_state(plan_path: Path, jmx_path: Path) -> tuple[str, dict[str, Any] | None]:
    meta_path = metadata_path_for(jmx_path)
    if not jmx_path.exists() and not meta_path.exists():
        return "MISSING", None
    if jmx_path.exists() != meta_path.exists():
        return "INCOMPLETE", None
    if not jmx_path.exists():
        return "MISSING", None

    metadata = load_json(meta_path)
    current_plan_sha = sha256_file(plan_path)
    stored_plan_sha = str(metadata.get("plan_sha256", ""))
    stored_jmx_sha = str(metadata.get("jmx_sha256", ""))
    actual_jmx_sha = sha256_file(jmx_path)

    if stored_plan_sha == current_plan_sha and stored_jmx_sha == actual_jmx_sha:
        try:
            ET.parse(jmx_path)
        except ET.ParseError:
            return "STALE", metadata
        return "CURRENT", metadata
    return "STALE", metadata


def archive_existing_artifact(
    *,
    config: ConfigLoader,
    scenario: str,
    jmx_path: Path,
) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_dir = (
        config.project_root
        / "archive"
        / "generated-jmx"
        / normalize_scenario_name(scenario)
        / timestamp
    )
    archive_dir.mkdir(parents=True, exist_ok=False)

    meta_path = metadata_path_for(jmx_path)
    if jmx_path.exists():
        shutil.move(str(jmx_path), str(archive_dir / jmx_path.name))
    if meta_path.exists():
        shutil.move(str(meta_path), str(archive_dir / meta_path.name))
    return archive_dir


def build_metadata(
    *,
    plan_path: Path,
    jmx_path: Path,
    plan: dict[str, Any],
) -> dict[str, Any]:
    transaction = plan["transactions"][0]
    workload = plan["workload"]["parameters"]
    target = plan["target"]
    return {
        "schema_version": "1.0",
        "generator_version": GENERATOR_VERSION,
        "generated_at": utc_now(),
        "scenario": str(plan["metadata"]["name"]),
        "plan_path": str(plan_path),
        "jmx_path": str(jmx_path),
        "plan_sha256": sha256_file(plan_path),
        "jmx_sha256": sha256_file(jmx_path),
        "plan_status": str(plan["status"]).upper(),
        "workload_status": str(plan["workload"]["status"]).upper(),
        "execution_authorization_status": str(plan["authorization"]["status"]).upper(),
        "target": {
            "method": str(transaction["method"]).upper(),
            "protocol": str(target["protocol"]),
            "host": str(target["host"]),
            "port": int(target["port"]),
            "path": str(transaction["path"]),
        },
        "workload": {
            "threads": int(workload["threads"]),
            "ramp_time_seconds": int(workload["ramp_time_seconds"]),
            "duration_seconds": int(workload["duration_seconds"]),
            "pacing_seconds": float(workload.get("pacing_seconds", 0)),
        },
    }


def write_metadata(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate or refresh a JMX from an APPROVED structured Performance "
            "Test Plan. Existing stale artifacts are archived before regeneration. "
            "JMeter is never executed."
        )
    )
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--config")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    archive_dir: Path | None = None
    action = "GENERATED"

    try:
        config = load_config(args.config)
        plan_path = args.plan.expanduser().resolve()
        plan = load_plan(plan_path)
        validate_plan(plan, plan_path)
        enforce_supported_plan(plan)

        if str(plan["status"]).upper() != "APPROVED":
            raise PlanGenerationError("Plan must be APPROVED before JMX generation.")
        if str(plan["workload"]["status"]).upper() != "APPROVED":
            raise PlanGenerationError("Workload must be APPROVED before JMX generation.")

        scenario = str(plan["metadata"]["name"])
        output = resolve_output(config, scenario, args.output)
        state, _ = artifact_state(plan_path, output)

        if state == "CURRENT":
            print("=" * 62)
            print("JMX ARTIFACT ALREADY UP TO DATE")
            print("=" * 62)
            print(f"Plan          : {plan_path}")
            print(f"JMX           : {output}")
            print(f"Metadata      : {metadata_path_for(output)}")
            print("Action        : REUSED")
            print("JMeter run    : NOT EXECUTED")
            print("=" * 62)
            return 0

        if state in {"STALE", "INCOMPLETE"}:
            archive_dir = archive_existing_artifact(
                config=config,
                scenario=scenario,
                jmx_path=output,
            )
            action = "REGENERATED_STALE_ARCHIVED"
        elif output.exists():
            # Legacy JMX without sidecar metadata.
            archive_dir = archive_existing_artifact(
                config=config,
                scenario=scenario,
                jmx_path=output,
            )
            action = "REGENERATED_LEGACY_ARCHIVED"

        transaction = plan["transactions"][0]
        target = plan["target"]
        workload = plan["workload"]["parameters"]
        prometheus_port = int(
            config.get("observability.jmeter_metrics.port", default=9270)
        )

        tree = build_jmx_tree(
            project_name=str(config.get("project.name", default="Performance Engineering")),
            scenario_name=scenario,
            host=str(target["host"]),
            port=int(target["port"]),
            protocol=str(target["protocol"]),
            endpoint_path=str(transaction["path"]),
            method=str(transaction["method"]).upper(),
            expected_status=int(transaction["expected_status"]),
            connect_timeout_ms=5000,
            response_timeout_ms=10000,
            default_threads=int(workload["threads"]),
            default_ramp_time=int(workload["ramp_time_seconds"]),
            default_duration=int(workload["duration_seconds"]),
            prometheus_port=prometheus_port,
        )

        defaults = load_data_defaults(plan, config.project_root)
        configure_user_variables(tree, defaults)
        configure_headers(tree, transaction.get("headers", {}))
        body = transaction.get("body")
        if body:
            configure_raw_body(tree, str(body))
        add_pacing_timer(tree, float(workload.get("pacing_seconds", 0)))
        sampler_tree = find_sampler_tree(tree)

        for extractor in plan.get("correlations", {}).get("extractors", []):
            add_json_extractor(
                sampler_tree,
                variable=str(extractor["name"]),
                expression=str(extractor["expression"]),
                fallback=str(extractor.get("fallback", "NOT_FOUND")),
            )
        for assertion in plan.get("assertions", []):
            if str(assertion.get("type", "")).upper() == "JSON_PATH":
                add_response_body_regex_assertion(
                    sampler_tree,
                    name="Validate response contains id",
                    regex=r'"id"\s*:\s*[^,}\s]+',
                )

        ET.indent(tree, space="  ")
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".jmx",
            dir=output.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            tree.write(handle, encoding="utf-8", xml_declaration=True)

        ET.parse(temporary)
        temporary.replace(output)
        metadata = build_metadata(plan_path=plan_path, jmx_path=output, plan=plan)
        write_metadata(metadata_path_for(output), metadata)

    except (
        PlanGenerationError,
        PlanValidationError,
        KeyError,
        TypeError,
        ValueError,
        OSError,
        yaml.YAMLError,
        ET.ParseError,
    ) as exc:
        print(f"JMX GENERATION ERROR: {exc}", file=sys.stderr)
        return 2

    print("=" * 62)
    print("JMX ARTIFACT READY")
    print("=" * 62)
    print(f"Plan          : {plan_path}")
    print(f"JMX           : {output}")
    print(f"Metadata      : {metadata_path_for(output)}")
    print(f"Scenario      : {scenario}")
    print(
        "Target        : "
        f"{transaction['method']} "
        f"{target['protocol']}://{target['host']}:{target['port']}"
        f"{transaction['path']}"
    )
    print(
        "Default load  : "
        f"{workload['threads']} users, "
        f"{workload['ramp_time_seconds']}s ramp-up, "
        f"{workload['duration_seconds']}s duration, "
        f"{workload.get('pacing_seconds', 0)}s pacing"
    )
    print(f"Action        : {action}")
    if archive_dir is not None:
        print(f"Archived      : {archive_dir}")
    print("XML validation: OK")
    print("JMeter run    : NOT EXECUTED")
    print("Authorization : unchanged")
    print("=" * 62)
    print("JMX READY FOR CONTROLLED EXECUTION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
