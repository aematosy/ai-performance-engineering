#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from generate_jmx import add_prometheus_collector
import xml.etree.ElementTree as ET

import yaml


class JmxGenerationError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except FileNotFoundError as exc:
        raise JmxGenerationError(
            f"File not found: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise JmxGenerationError(
            f"Invalid JSON in {path}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise JmxGenerationError(
            f"JSON root must be object: {path}"
        )

    return data


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(
            path.read_text(
                encoding="utf-8"
            )
        )
    except FileNotFoundError as exc:
        raise JmxGenerationError(
            f"File not found: {path}"
        ) from exc

    if not isinstance(data, dict):
        raise JmxGenerationError(
            f"YAML root must be object: {path}"
        )

    return data


def string_prop(
    parent: ET.Element,
    name: str,
    value: Any,
) -> ET.Element:
    element = ET.SubElement(
        parent,
        "stringProp",
        {"name": name},
    )
    element.text = str(
        "" if value is None else value
    )
    return element


def bool_prop(
    parent: ET.Element,
    name: str,
    value: bool,
) -> ET.Element:
    element = ET.SubElement(
        parent,
        "boolProp",
        {"name": name},
    )
    element.text = (
        "true"
        if value
        else "false"
    )
    return element


def add_http_defaults(
    parent_hash: ET.Element,
    model: dict[str, Any],
) -> None:
    requests = model.get(
        "requests",
        [],
    )

    if not requests:
        raise JmxGenerationError(
            "Executable model has no requests."
        )

    hosts = {
        (
            req.get("protocol"),
            req.get("host"),
            req.get("port"),
        )
        for req in requests
    }

    if len(hosts) != 1:
        return

    protocol, host, port = next(
        iter(hosts)
    )

    config = ET.SubElement(
        parent_hash,
        "ConfigTestElement",
        {
            "guiclass": "HttpDefaultsGui",
            "testclass": "ConfigTestElement",
            "testname": "HTTP Request Defaults",
            "enabled": "true",
        },
    )

    string_prop(
        config,
        "HTTPSampler.domain",
        host or "",
    )
    string_prop(
        config,
        "HTTPSampler.protocol",
        protocol or "",
    )

    if port:
        string_prop(
            config,
            "HTTPSampler.port",
            port,
        )

    bool_prop(
        config,
        "HTTPSampler.image_parser",
        False,
    )

    ET.SubElement(
        parent_hash,
        "hashTree",
    )



def add_prometheus_listener(
    parent_hash: ET.Element,
    profile: dict[str, Any],
) -> bool:
    """Add Prometheus observability to a generated Postman JMX.

    The listener is enabled when the execution profile provides
    observability.prometheus_port.

    The concrete runtime port remains overrideable through the
    standard JMeter property:
        -Jprometheus_port=<port>

    No application, host, endpoint or scenario is hardcoded here.
    """

    observability = profile.get(
        "observability",
        {},
    )

    if observability is None:
        return False

    if not isinstance(
        observability,
        dict,
    ):
        raise JmxGenerationError(
            "profile.observability must be an object."
        )

    raw_port = observability.get(
        "prometheus_port"
    )

    # Observability is optional for profiles that intentionally
    # do not configure a Prometheus endpoint.
    if raw_port is None:
        return False

    try:
        prometheus_port = int(
            raw_port
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise JmxGenerationError(
            "observability.prometheus_port "
            "must be an integer."
        ) from exc

    if not 1 <= prometheus_port <= 65535:
        raise JmxGenerationError(
            "observability.prometheus_port "
            "must be between 1 and 65535."
        )

    listener = ET.SubElement(
        parent_hash,
        (
            "com.github.johrstrom.listener."
            "PrometheusListener"
        ),
        {
            "guiclass": (
                "com.github.johrstrom.listener.gui."
                "PrometheusListenerGui"
            ),
            "testclass": (
                "com.github.johrstrom.listener."
                "PrometheusListener"
            ),
            "testname": "Prometheus Listener",
            "enabled": "true",
        },
    )

    collectors = ET.SubElement(
        listener,
        "collectionProp",
        {
            "name": (
                "prometheus.collector_definitions"
            )
        },
    )

    add_prometheus_collector(
        collectors,
        metric_name="jmeter_requests_total",
        help_text="Total JMeter requests",
        collector_type="COUNTER",
        measuring="CountTotal",
        labels=["label"],
    )

    add_prometheus_collector(
        collectors,
        metric_name="jmeter_success_total",
        help_text="Successful JMeter requests",
        collector_type="COUNTER",
        measuring="SuccessTotal",
        labels=["label"],
    )

    add_prometheus_collector(
        collectors,
        metric_name="jmeter_error_total",
        help_text="Failed JMeter requests",
        collector_type="COUNTER",
        measuring="FailureTotal",
        labels=["label"],
    )

    add_prometheus_collector(
        collectors,
        metric_name="jmeter_response_time_ms",
        help_text=(
            "JMeter response time in milliseconds"
        ),
        collector_type="SUMMARY",
        measuring="ResponseTime",
        labels=["label"],
        quantiles_or_buckets=(
            "0.5,0.05|"
            "0.9,0.01|"
            "0.95,0.005|"
            "0.99,0.001"
        ),
    )

    string_prop(
        listener,
        "prometheus.port",
        (
            "${__P(prometheus_port,"
            + str(prometheus_port)
            + ")}"
        ),
    )

    string_prop(
        listener,
        "TestPlan.comments",
        "",
    )

    # Every JMeter test element must be followed by its hashTree.
    ET.SubElement(
        parent_hash,
        "hashTree",
    )

    return True


def add_csv(
    parent_hash: ET.Element,
    csv_path: Path,
    profile: dict[str, Any],
) -> None:
    data = profile.get(
        "data",
        {},
    )

    csv_config = ET.SubElement(
        parent_hash,
        "CSVDataSet",
        {
            "guiclass": "TestBeanGUI",
            "testclass": "CSVDataSet",
            "testname": "Scenario Test Data",
            "enabled": "true",
        },
    )

    string_prop(
        csv_config,
        "filename",
        str(csv_path),
    )
    string_prop(
        csv_config,
        "fileEncoding",
        "UTF-8",
    )
    string_prop(
        csv_config,
        "delimiter",
        ",",
    )
    bool_prop(
        csv_config,
        "quotedData",
        False,
    )
    bool_prop(
        csv_config,
        "recycle",
        bool(
            data.get(
                "recycle",
                True,
            )
        ),
    )
    bool_prop(
        csv_config,
        "stopThread",
        bool(
            data.get(
                "stop_thread_on_eof",
                False,
            )
        ),
    )
    string_prop(
        csv_config,
        "shareMode",
        (
            "shareMode.all"
            if data.get(
                "sharing_mode"
            ) == "all_threads"
            else "shareMode.thread"
        ),
    )

    ET.SubElement(
        parent_hash,
        "hashTree",
    )


def add_headers(
    sampler_tree: ET.Element,
    headers: list[dict[str, Any]],
) -> None:
    if not headers:
        return

    manager = ET.SubElement(
        sampler_tree,
        "HeaderManager",
        {
            "guiclass": "HeaderPanel",
            "testclass": "HeaderManager",
            "testname": "HTTP Header Manager",
            "enabled": "true",
        },
    )

    collection = ET.SubElement(
        manager,
        "collectionProp",
        {
            "name": "HeaderManager.headers",
        },
    )

    for index, header in enumerate(
        headers
    ):
        element = ET.SubElement(
            collection,
            "elementProp",
            {
                "name": str(index),
                "elementType": "Header",
            },
        )
        string_prop(
            element,
            "Header.name",
            header.get("name", ""),
        )
        string_prop(
            element,
            "Header.value",
            header.get("value", ""),
        )

    ET.SubElement(
        sampler_tree,
        "hashTree",
    )


def add_json_extractor(
    sampler_tree: ET.Element,
    extractor: dict[str, Any],
) -> None:
    post = ET.SubElement(
        sampler_tree,
        "JSONPostProcessor",
        {
            "guiclass": "JSONPostProcessorGui",
            "testclass": "JSONPostProcessor",
            "testname": (
                "Extract "
                + str(
                    extractor.get(
                        "variable"
                    )
                )
            ),
            "enabled": "true",
        },
    )

    string_prop(
        post,
        "JSONPostProcessor.referenceNames",
        extractor.get(
            "variable",
            "",
        ),
    )
    string_prop(
        post,
        "JSONPostProcessor.jsonPathExprs",
        extractor.get(
            "json_path",
            "",
        ),
    )
    string_prop(
        post,
        "JSONPostProcessor.match_numbers",
        "1",
    )
    string_prop(
        post,
        "JSONPostProcessor.defaultValues",
        "__CORRELATION_MISSING__",
    )

    ET.SubElement(
        sampler_tree,
        "hashTree",
    )


def add_status_assertion(
    sampler_tree: ET.Element,
) -> None:
    assertion = ET.SubElement(
        sampler_tree,
        "ResponseAssertion",
        {
            "guiclass": "AssertionGui",
            "testclass": "ResponseAssertion",
            "testname": "HTTP success assertion",
            "enabled": "true",
        },
    )

    collection = ET.SubElement(
        assertion,
        "collectionProp",
        {
            "name": "Asserion.test_strings",
        },
    )

    string_prop(
        collection,
        "49586",
        "^[23]\\d\\d$",
    )
    string_prop(
        assertion,
        "Assertion.custom_message",
        "Expected HTTP 2xx/3xx response",
    )
    string_prop(
        assertion,
        "Assertion.test_field",
        "Assertion.response_code",
    )
    bool_prop(
        assertion,
        "Assertion.assume_success",
        False,
    )
    string_prop(
        assertion,
        "Assertion.test_type",
        "2",
    )

    ET.SubElement(
        sampler_tree,
        "hashTree",
    )


def add_correlation_assertion(
    sampler_tree: ET.Element,
    variable: str,
) -> None:
    assertion = ET.SubElement(
        sampler_tree,
        "JSR223Assertion",
        {
            "guiclass": "TestBeanGUI",
            "testclass": "JSR223Assertion",
            "testname": (
                f"Validate correlation {variable}"
            ),
            "enabled": "true",
        },
    )

    string_prop(
        assertion,
        "scriptLanguage",
        "groovy",
    )

    script = (
        f"def v = vars.get('{variable}'); "
        f"if (v == null || v == '' || "
        f"v == '__CORRELATION_MISSING__') "
        "{ AssertionResult.setFailure(true); "
        f"AssertionResult.setFailureMessage("
        f"'Missing correlation: {variable}') }}"
    )

    string_prop(
        assertion,
        "script",
        script,
    )
    string_prop(
        assertion,
        "parameters",
        "",
    )
    string_prop(
        assertion,
        "filename",
        "",
    )
    bool_prop(
        assertion,
        "cacheKey",
        True,
    )

    ET.SubElement(
        sampler_tree,
        "hashTree",
    )



def render_runtime_json(
    value: Any,
) -> str:
    """
    Render a parameterized JSON structure while preserving JSON
    primitive types.

    STRING parameters remain quoted through json.dumps().
    INTEGER/NUMBER/BOOLEAN parameters are emitted as raw JMeter
    variable expressions so the final request body contains valid
    JSON primitives rather than strings.
    """

    if isinstance(value, dict):
        parameter = value.get(
            "__runtime_parameter__"
        )
        json_type = value.get(
            "__json_type__"
        )

        if parameter and json_type:
            reference = f"${{{parameter}}}"

            if json_type in {
                "INTEGER",
                "NUMBER",
                "BOOLEAN",
            }:
                return reference

            if json_type == "NULL":
                return "null"

            return json.dumps(
                reference,
                ensure_ascii=False,
            )

        items = []

        for key, child in value.items():
            items.append(
                json.dumps(
                    str(key),
                    ensure_ascii=False,
                )
                + ":"
                + render_runtime_json(
                    child
                )
            )

        return "{" + ",".join(items) + "}"

    if isinstance(value, list):
        return (
            "["
            + ",".join(
                render_runtime_json(child)
                for child in value
            )
            + "]"
        )

    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def add_iteration_pacing(
    parent_hash: ET.Element,
    pacing_seconds: float,
) -> None:
    """
    Add a pause action at the END of the scenario iteration.

    A ConstantTimer at ThreadGroup scope applies to every sampler.
    Therefore iteration pacing must not be represented by a
    thread-group-scoped ConstantTimer.
    """

    if pacing_seconds <= 0:
        return

    action = ET.SubElement(
        parent_hash,
        "TestAction",
        {
            "guiclass": "TestActionGui",
            "testclass": "TestAction",
            "testname": "Iteration Pacing",
            "enabled": "true",
        },
    )

    int_action = ET.SubElement(
        action,
        "intProp",
        {
            "name": "ActionProcessor.action",
        },
    )
    # 1 = Pause
    int_action.text = "1"

    int_target = ET.SubElement(
        action,
        "intProp",
        {
            "name": "ActionProcessor.target",
        },
    )
    int_target.text = "0"

    string_prop(
        action,
        "ActionProcessor.duration",
        str(
            int(
                pacing_seconds * 1000
            )
        ),
    )

    ET.SubElement(
        parent_hash,
        "hashTree",
    )



def add_sampler(
    parent_hash: ET.Element,
    request: dict[str, Any],
    use_defaults: bool,
) -> None:
    sampler = ET.SubElement(
        parent_hash,
        "HTTPSamplerProxy",
        {
            "guiclass": "HttpTestSampleGui",
            "testclass": "HTTPSamplerProxy",
            "testname": request.get(
                "id",
                "HTTP Request",
            ),
            "enabled": "true",
        },
    )

    if not use_defaults:
        string_prop(
            sampler,
            "HTTPSampler.domain",
            request.get(
                "host",
                "",
            ),
        )
        string_prop(
            sampler,
            "HTTPSampler.protocol",
            request.get(
                "protocol",
                "",
            ),
        )

        if request.get("port"):
            string_prop(
                sampler,
                "HTTPSampler.port",
                request["port"],
            )

    string_prop(
        sampler,
        "HTTPSampler.path",
        request.get(
            "path",
            "/",
        )
        + (
            "?" + request["query"]
            if request.get("query")
            else ""
        ),
    )

    string_prop(
        sampler,
        "HTTPSampler.method",
        request.get(
            "method",
            "GET",
        ),
    )
    bool_prop(
        sampler,
        "HTTPSampler.follow_redirects",
        True,
    )
    bool_prop(
        sampler,
        "HTTPSampler.auto_redirects",
        False,
    )
    bool_prop(
        sampler,
        "HTTPSampler.use_keepalive",
        True,
    )
    bool_prop(
        sampler,
        "HTTPSampler.DO_MULTIPART_POST",
        False,
    )

    body = request.get(
        "json_body"
    )

    if body is not None:
        arguments = ET.SubElement(
            sampler,
            "elementProp",
            {
                "name": "HTTPsampler.Arguments",
                "elementType": "Arguments",
                "guiclass": "HTTPArgumentsPanel",
                "testclass": "Arguments",
                "enabled": "true",
            },
        )
        collection = ET.SubElement(
            arguments,
            "collectionProp",
            {
                "name": "Arguments.arguments",
            },
        )
        arg = ET.SubElement(
            collection,
            "elementProp",
            {
                "name": "",
                "elementType": "HTTPArgument",
            },
        )
        bool_prop(
            arg,
            "HTTPArgument.always_encode",
            False,
        )
        string_prop(
            arg,
            "Argument.value",
            render_runtime_json(
                body
            ),
        )
        string_prop(
            arg,
            "Argument.metadata",
            "=",
        )
        bool_prop(
            arg,
            "HTTPArgument.use_equals",
            True,
        )
        string_prop(
            arg,
            "Argument.name",
            "",
        )
        bool_prop(
            sampler,
            "HTTPSampler.postBodyRaw",
            True,
        )

    sampler_tree = ET.SubElement(
        parent_hash,
        "hashTree",
    )

    headers = list(
        request.get(
            "headers",
            [],
        )
    )

    if body is not None and not any(
        str(h.get("name", "")).lower()
        == "content-type"
        for h in headers
    ):
        headers.append(
            {
                "name": "Content-Type",
                "value": "application/json",
            }
        )

    # Generic HTTP content-negotiation fallback.
    #
    # Preserve an explicit Accept header from the imported
    # request. When none was supplied, use the non-restrictive
    # HTTP wildcard rather than relying on client-specific
    # defaults. This applies to requests with or without bodies
    # and does not assume that every service returns JSON.
    if not any(
        str(h.get("name", "")).lower()
        == "accept"
        for h in headers
    ):
        headers.append(
            {
                "name": "Accept",
                "value": "*/*",
            }
        )

    add_headers(
        sampler_tree,
        headers,
    )

    for extractor in request.get(
        "extractors",
        [],
    ):
        add_json_extractor(
            sampler_tree,
            extractor,
        )
        add_correlation_assertion(
            sampler_tree,
            extractor["variable"],
        )

    add_status_assertion(
        sampler_tree
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a multi-request JMeter JMX "
            "from an executable Postman scenario model."
        )
    )

    parser.add_argument(
        "--model",
        required=True,
    )
    parser.add_argument(
        "--profile",
        required=True,
    )
    parser.add_argument(
        "--csv",
        required=False,
        help=(
            "Optional CSV dataset. Required only when the "
            "scenario uses external CSV test data."
        ),
    )
    parser.add_argument(
        "--output",
        required=True,
    )

    args = parser.parse_args()

    try:
        model = load_json(
            Path(args.model).expanduser().resolve()
        )
        profile = load_yaml(
            Path(args.profile).expanduser().resolve()
        )
        csv_path = (
            Path(
                args.csv
            )
            .expanduser()
            .resolve()
            if args.csv
            else None
        )

        if (
            csv_path is not None
            and not csv_path.is_file()
        ):
            raise JmxGenerationError(
                f"CSV file does not exist: {csv_path}"
            )
        output = Path(
            args.output
        ).expanduser().resolve()

        execution = profile.get(
            "execution",
            {},
        )

        if (
            str(
                execution.get(
                    "mode",
                    "",
                )
            ).upper()
            != "DURATION"
        ):
            raise JmxGenerationError(
                "v1 generator supports DURATION profiles only."
            )

        requests = model.get(
            "requests",
            [],
        )

        if not requests:
            raise JmxGenerationError(
                "Executable model has no requests."
            )

        root = ET.Element(
            "jmeterTestPlan",
            {
                "version": "1.2",
                "properties": "5.0",
                "jmeter": "5.6.3",
            },
        )

        root_hash = ET.SubElement(
            root,
            "hashTree",
        )

        test_plan = ET.SubElement(
            root_hash,
            "TestPlan",
            {
                "guiclass": "TestPlanGui",
                "testclass": "TestPlan",
                "testname": (
                    model.get(
                        "scenario_candidate",
                        {},
                    ).get(
                        "id",
                        "Postman E2E",
                    )
                ),
                "enabled": "true",
            },
        )

        bool_prop(
            test_plan,
            "TestPlan.functional_mode",
            False,
        )
        bool_prop(
            test_plan,
            "TestPlan.tearDown_on_shutdown",
            True,
        )
        bool_prop(
            test_plan,
            "TestPlan.serialize_threadgroups",
            False,
        )

        ET.SubElement(
            test_plan,
            "elementProp",
            {
                "name": "TestPlan.user_defined_variables",
                "elementType": "Arguments",
                "guiclass": "ArgumentsPanel",
                "testclass": "Arguments",
                "enabled": "true",
            },
        )

        plan_tree = ET.SubElement(
            root_hash,
            "hashTree",
        )

        thread_group = ET.SubElement(
            plan_tree,
            "ThreadGroup",
            {
                "guiclass": "ThreadGroupGui",
                "testclass": "ThreadGroup",
                "testname": "Postman E2E Virtual Users",
                "enabled": "true",
            },
        )

        string_prop(
            thread_group,
            "ThreadGroup.num_threads",
            "${__P(threads,"
            + str(
                execution.get(
                    "threads",
                    1,
                )
            )
            + ")}",
        )
        string_prop(
            thread_group,
            "ThreadGroup.ramp_time",
            "${__P(ramp_time,"
            + str(
                execution.get(
                    "ramp_time_seconds",
                    1,
                )
            )
            + ")}",
        )
        bool_prop(
            thread_group,
            "ThreadGroup.scheduler",
            True,
        )
        string_prop(
            thread_group,
            "ThreadGroup.duration",
            "${__P(duration,"
            + str(
                execution.get(
                    "duration_seconds",
                    30,
                )
            )
            + ")}",
        )
        string_prop(
            thread_group,
            "ThreadGroup.delay",
            "0",
        )

        loop = ET.SubElement(
            thread_group,
            "elementProp",
            {
                "name": "ThreadGroup.main_controller",
                "elementType": "LoopController",
                "guiclass": "LoopControlPanel",
                "testclass": "LoopController",
                "enabled": "true",
            },
        )
        bool_prop(
            loop,
            "LoopController.continue_forever",
            True,
        )
        string_prop(
            loop,
            "LoopController.loops",
            "-1",
        )

        tg_tree = ET.SubElement(
            plan_tree,
            "hashTree",
        )

        host_set = {
            (
                req.get("protocol"),
                req.get("host"),
                req.get("port"),
            )
            for req in requests
        }

        use_defaults = (
            len(host_set) == 1
        )

        add_http_defaults(
            tg_tree,
            model,
        )

        if csv_path is not None:
            add_csv(
                tg_tree,
                csv_path,
                profile,
            )

        for request in requests:
            add_sampler(
                tg_tree,
                request,
                use_defaults,
            )

        pacing = float(
            execution.get(
                "pacing_seconds",
                0,
            )
        )

        add_iteration_pacing(
            tg_tree,
            pacing,
        )

        prometheus_enabled = (
            add_prometheus_listener(
                tg_tree,
                profile,
            )
        )

        tree = ET.ElementTree(
            root
        )
        ET.indent(
            tree,
            space="  ",
        )

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        tree.write(
            output,
            encoding="utf-8",
            xml_declaration=True,
        )

        ET.parse(
            output
        )

    except (
        JmxGenerationError,
        ET.ParseError,
        OSError,
    ) as exc:
        print(
            f"POSTMAN JMX ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print("=" * 72)
    print("POSTMAN MULTI-REQUEST JMX GENERATION")
    print("=" * 72)
    print(
        f"Scenario : "
        f"{model['scenario_candidate']['id']}"
    )
    print(
        f"Requests : {len(requests)}"
    )
    print(
        "CSV      : "
        + (
            str(csv_path)
            if csv_path is not None
            else "NOT REQUIRED"
        )
    )
    print(
        f"JMX      : {output}"
    )
    print(
        "XML      : VALID"
    )
    print(
        "Metrics  : "
        + (
            "PROMETHEUS ENABLED"
            if prometheus_enabled
            else "NOT CONFIGURED"
        )
    )
    print(
        "JMeter   : NOT EXECUTED"
    )
    print("=" * 72)
    print("POSTMAN JMX READY FOR VALIDATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
