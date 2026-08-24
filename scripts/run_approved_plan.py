#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


class ControlledExecutionError(RuntimeError):
    pass


GENERIC_IDENTITIES = {
    "user",
    "admin",
    "administrator",
    "qa",
    "tester",
    "operator",
    "unknown",
    "n/a",
    "na",
}


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ControlledExecutionError(
            f"File not found: {path}"
        ) from exc
    except yaml.YAMLError as exc:
        raise ControlledExecutionError(
            f"Invalid YAML in {path}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ControlledExecutionError(
            f"YAML root must be an object: {path}"
        )

    return data


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ControlledExecutionError(
            f"File not found: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ControlledExecutionError(
            f"Invalid JSON in {path}: "
            f"line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(data, dict):
        raise ControlledExecutionError(
            f"JSON root must be an object: {path}"
        )

    return data


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as fh:
        for chunk in iter(
            lambda: fh.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise ControlledExecutionError(
            f"{label} not found: {path}"
        )

    if not path.is_file():
        raise ControlledExecutionError(
            f"{label} is not a file: {path}"
        )


def target_string(
    plan: dict[str, Any],
) -> str:
    transactions = plan.get("transactions")
    target = plan.get("target")

    if (
        not isinstance(transactions, list)
        or not transactions
        or not isinstance(transactions[0], dict)
    ):
        raise ControlledExecutionError(
            "Plan must contain at least one transaction."
        )

    if not isinstance(target, dict):
        raise ControlledExecutionError(
            "Plan target must be an object."
        )

    transaction = transactions[0]

    method = str(
        transaction.get("method", "")
    ).strip().upper()
    protocol = str(
        target.get("protocol", "")
    ).strip().lower()
    host = str(
        target.get("host", "")
    ).strip()
    path = str(
        transaction.get("path", "")
    ).strip()

    if not all(
        (
            method,
            protocol,
            host,
            path,
        )
    ):
        raise ControlledExecutionError(
            "Plan target/transaction is incomplete."
        )

    try:
        port = int(target.get("port"))
    except (TypeError, ValueError) as exc:
        raise ControlledExecutionError(
            "Plan target.port must be an integer."
        ) from exc

    default_port = (
        443
        if protocol == "https"
        else 80
    )

    port_part = (
        ""
        if port == default_port
        else f":{port}"
    )

    return (
        f"{method} "
        f"{protocol}://{host}"
        f"{port_part}{path}"
    )


def scenario_name(
    plan: dict[str, Any],
) -> str:
    metadata = plan.get("metadata")

    if isinstance(metadata, dict):
        value = metadata.get("name")
        if isinstance(value, str) and value.strip():
            return value.strip()

    raise ControlledExecutionError(
        "Plan metadata.name is required."
    )


def validate_execution_authorization(
    plan: dict[str, Any],
) -> dict[str, str]:
    if str(
        plan.get("status", "")
    ).strip().upper() != "APPROVED":
        raise ControlledExecutionError(
            "Plan status must be APPROVED."
        )

    workload = plan.get("workload")
    if not isinstance(workload, dict):
        raise ControlledExecutionError(
            "Plan workload is missing."
        )

    if str(
        workload.get("status", "")
    ).strip().upper() != "APPROVED":
        raise ControlledExecutionError(
            "Workload status must be APPROVED."
        )

    authorization = plan.get("authorization")
    if not isinstance(authorization, dict):
        raise ControlledExecutionError(
            "Plan authorization section is missing."
        )

    approval = plan.get("approval")
    if not isinstance(approval, dict):
        raise ControlledExecutionError(
            "Plan approval section is missing."
        )

    auth_status = str(
        authorization.get("status", "")
    ).strip().upper()

    execution_authorized = approval.get(
        "execution_authorized"
    )

    authorized_by = str(
        authorization.get("authorized_by")
        or ""
    ).strip()

    authorized_at = str(
        authorization.get("authorized_at")
        or ""
    ).strip()

    if auth_status != "AUTHORIZED":
        raise ControlledExecutionError(
            "Execution authorization is not AUTHORIZED. "
            f"Current status: {auth_status or 'MISSING'}."
        )

    if execution_authorized is not True:
        raise ControlledExecutionError(
            "approval.execution_authorized must be true."
        )

    if not authorized_by:
        raise ControlledExecutionError(
            "authorization.authorized_by is required."
        )

    if authorized_by.lower() in GENERIC_IDENTITIES:
        raise ControlledExecutionError(
            "authorization.authorized_by must be an explicit "
            "human identity, not a generic value."
        )

    if not authorized_at:
        raise ControlledExecutionError(
            "authorization.authorized_at is required."
        )

    return {
        "status": auth_status,
        "authorized_by": authorized_by,
        "authorized_at": authorized_at,
    }


def profile_runtime(
    profile: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    execution = profile.get("execution")

    if not isinstance(execution, dict):
        raise ControlledExecutionError(
            "Execution profile execution section is missing."
        )

    mode = str(
        execution.get("mode", "")
    ).strip().upper()

    # run_test.py currently has only duration-mode runtime properties:
    # threads, ramp_time, duration and prometheus_port.
    if mode != "DURATION":
        raise ControlledExecutionError(
            "Runner v2 currently supports DURATION profiles only. "
            "ITERATIONS remains blocked until run_test.py and JMX runtime "
            "properties support iteration mode deterministically."
        )

    try:
        threads = int(
            execution["threads"]
        )
        ramp_time = int(
            execution["ramp_time_seconds"]
        )
        duration = int(
            execution["duration_seconds"]
        )
        pacing = float(
            execution["pacing_seconds"]
        )
    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise ControlledExecutionError(
            "Execution profile contains invalid runtime values."
        ) from exc

    observability = profile.get(
        "observability"
    )
    if not isinstance(
        observability,
        dict,
    ):
        raise ControlledExecutionError(
            "Execution profile observability section is missing."
        )

    try:
        prometheus_port = int(
            observability[
                "prometheus_port"
            ]
        )
    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise ControlledExecutionError(
            "observability.prometheus_port must be an integer."
        ) from exc

    plan_workload = plan.get(
        "workload",
        {},
    )
    parameters = (
        plan_workload.get(
            "parameters",
            {},
        )
        if isinstance(
            plan_workload,
            dict,
        )
        else {}
    )

    try:
        approved_pacing = float(
            parameters[
                "pacing_seconds"
            ]
        )
    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise ControlledExecutionError(
            "Approved plan workload must define pacing_seconds."
        ) from exc

    # The current low-level runner does not pass a pacing runtime property.
    # Until that is upgraded, a profile must not request different pacing
    # even when the higher-level plan comparison considers slower pacing safe.
    if pacing != approved_pacing:
        raise ControlledExecutionError(
            "Profile pacing differs from the approved JMX pacing. "
            "Runner v2 cannot override pacing safely yet. "
            f"Approved={approved_pacing}, requested={pacing}."
        )

    return {
        "mode": mode,
        "threads": threads,
        "ramp_time_seconds": ramp_time,
        "duration_seconds": duration,
        "pacing_seconds": pacing,
        "prometheus_port": prometheus_port,
    }


def run_pre_execution_gate(
    *,
    project_root: Path,
    plan: Path,
    profile: Path,
    jmx: Path,
    csv_path: Path | None,
    data_requirements: Path | None,
    design_context: Path | None,
    manifest: Path,
    properties_file: Path | None = None,
) -> None:
    command = [
        sys.executable,
        str(
            project_root
            / "scripts"
            / "pre_execution_gate.py"
        ),
        "--plan",
        str(plan),
        "--profile",
        str(profile),
        "--jmx",
        str(jmx),
        "--manifest",
        str(manifest),
    ]

    if csv_path is not None:
        command.extend(
            [
                "--csv",
                str(csv_path),
            ]
        )

    if data_requirements is not None:
        command.extend(
            [
                "--data-requirements",
                str(data_requirements),
            ]
        )

    if design_context is not None:
        command.extend(
            [
                "--design-context",
                str(design_context),
                "--require-execution-ready-context",
            ]
        )

    if properties_file is not None:
        command.extend(
            [
                "--properties",
                str(properties_file),
            ]
        )

    result = subprocess.run(
        command,
        cwd=project_root,
    )

    if result.returncode != 0:
        raise ControlledExecutionError(
            "Pre-execution gate blocked the execution bundle."
        )


def verify_manifest_artifact(
    manifest: dict[str, Any],
    key: str,
    path: Path | None,
) -> None:
    inputs = manifest.get("inputs")
    if not isinstance(inputs, dict):
        raise ControlledExecutionError(
            "Pre-execution manifest inputs section is missing."
        )

    record = inputs.get(key)

    if path is None:
        if record is not None:
            raise ControlledExecutionError(
                f"Manifest contains unexpected artifact: {key}."
            )
        return

    if not isinstance(record, dict):
        raise ControlledExecutionError(
            f"Manifest does not contain artifact: {key}."
        )

    expected_path = str(
        path.resolve()
    )
    manifest_path = str(
        record.get("path", "")
    )

    if (
        Path(manifest_path)
        .expanduser()
        .resolve()
        != path.resolve()
    ):
        raise ControlledExecutionError(
            f"Manifest path mismatch for {key}: "
            f"{manifest_path} != {expected_path}"
        )

    expected_hash = str(
        record.get("sha256", "")
    ).strip().lower()
    actual_hash = sha256(path)

    if not expected_hash:
        raise ControlledExecutionError(
            f"Manifest hash is missing for {key}."
        )

    if expected_hash != actual_hash:
        raise ControlledExecutionError(
            f"Artifact changed after pre-execution validation: {key}."
        )


def verify_manifest(
    *,
    manifest_path: Path,
    plan: Path,
    profile: Path,
    jmx: Path,
    csv_path: Path | None,
    data_requirements: Path | None,
    design_context: Path | None,
    properties_file: Path | None = None,
) -> dict[str, Any]:
    manifest = load_json(
        manifest_path
    )

    if str(
        manifest.get("schema_version", "")
    ) != "2.0":
        raise ControlledExecutionError(
            "Pre-execution manifest schema_version must be 2.0."
        )

    if str(
        manifest.get("status", "")
    ).strip().upper() != "PRE_EXECUTION_READY":
        raise ControlledExecutionError(
            "Pre-execution manifest is not PRE_EXECUTION_READY."
        )

    if manifest.get(
        "execution_performed"
    ) is not False:
        raise ControlledExecutionError(
            "Unexpected execution_performed value in manifest."
        )

    authorization = manifest.get(
        "authorization"
    )

    if not isinstance(
        authorization,
        dict,
    ) or authorization.get(
        "granted_by_gate"
    ) is not False:
        raise ControlledExecutionError(
            "Pre-execution manifest authorization contract is invalid."
        )

    verify_manifest_artifact(
        manifest,
        "plan",
        plan,
    )
    verify_manifest_artifact(
        manifest,
        "profile",
        profile,
    )
    verify_manifest_artifact(
        manifest,
        "jmx",
        jmx,
    )
    verify_manifest_artifact(
        manifest,
        "csv",
        csv_path,
    )
    verify_manifest_artifact(
        manifest,
        "data_requirements",
        data_requirements,
    )
    verify_manifest_artifact(
        manifest,
        "design_context",
        design_context,
    )
    verify_manifest_artifact(
        manifest,
        "properties",
        properties_file,
    )

    return manifest


def print_controlled_preflight(
    *,
    plan: dict[str, Any],
    plan_path: Path,
    profile_path: Path,
    jmx_path: Path,
    manifest_path: Path,
    runtime: dict[str, Any],
) -> None:
    authorization = plan.get(
        "authorization",
        {},
    )
    approval = plan.get(
        "approval",
        {},
    )

    print("=" * 74)
    print(
        "CONTROLLED PERFORMANCE EXECUTION PREFLIGHT v2"
    )
    print("=" * 74)
    print(
        f"Scenario        : "
        f"{scenario_name(plan)}"
    )
    print(
        f"Target          : "
        f"{target_string(plan)}"
    )
    print(
        f"Environment     : "
        f"{plan.get('environment')}"
    )
    print(
        f"Profile         : "
        f"{profile_path}"
    )
    print(
        f"Users           : "
        f"{runtime['threads']}"
    )
    print(
        f"Ramp-up         : "
        f"{runtime['ramp_time_seconds']} s"
    )
    print(
        f"Duration        : "
        f"{runtime['duration_seconds']} s"
    )
    print(
        f"Pacing          : "
        f"{runtime['pacing_seconds']} s"
    )
    print(
        f"Prometheus port : "
        f"{runtime['prometheus_port']}"
    )
    print(
        f"Plan            : "
        f"{plan_path}"
    )
    print(
        f"JMX             : "
        f"{jmx_path}"
    )
    print(
        f"Manifest        : "
        f"{manifest_path}"
    )
    print(
        f"Plan status     : "
        f"{plan.get('status')}"
    )
    print(
        f"Workload        : "
        f"{plan.get('workload', {}).get('status')}"
    )
    print(
        f"Authorization   : "
        f"{authorization.get('status')}"
    )
    print(
        f"Authorized by   : "
        f"{authorization.get('authorized_by')}"
    )
    print(
        f"Authorized at   : "
        f"{authorization.get('authorized_at')}"
    )
    print(
        "Execution flag  : "
        f"{approval.get('execution_authorized')}"
    )
    print(
        "Artifact hashes : VERIFIED"
    )
    print("=" * 74)


def build_low_level_command(
    *,
    project_root: Path,
    plan: dict[str, Any],
    jmx_path: Path,
    runtime: dict[str, Any],
    properties_file: Path | None = None,
) -> list[str]:
    command = [
        sys.executable,
        str(
            project_root
            / "scripts"
            / "run_test.py"
        ),
        "--jmx",
        str(jmx_path),
        "--scenario",
        scenario_name(plan),
        "--target",
        target_string(plan),
        "--environment",
        str(
            plan.get(
                "environment",
                ""
            )
        ),
        "--threads",
        str(
            runtime[
                "threads"
            ]
        ),
        "--ramp-time",
        str(
            runtime[
                "ramp_time_seconds"
            ]
        ),
        "--duration",
        str(
            runtime[
                "duration_seconds"
            ]
        ),
        "--prometheus-port",
        str(
            runtime[
                "prometheus_port"
            ]
        ),
        # This flag is now an internal handoff only. The controlled runner
        # validates plan authorization before it is ever supplied.
        "--authorized",
        # Environment validation has already run inside pre_execution_gate.py.
        "--skip-environment-validation",
    ]

    if properties_file is not None:
        command.extend(
            [
                "--properties",
                str(properties_file),
            ]
        )

    return command



def validate_prometheus_observability(
    *,
    profile: dict[str, Any],
    jmx_path: Path,
) -> None:
    """Fail closed when Prometheus observability is configured
    but the governed JMX cannot expose the configured metrics.
    """

    observability = profile.get(
        "observability",
        {},
    )

    if not isinstance(
        observability,
        dict,
    ):
        raise ControlledExecutionError(
            "Execution profile observability must be an object."
        )

    raw_port = observability.get(
        "prometheus_port"
    )

    # No Prometheus observability configured for this profile.
    if raw_port is None:
        return

    try:
        port = int(
            raw_port
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ControlledExecutionError(
            "observability.prometheus_port "
            "must be an integer."
        ) from exc

    if not 1 <= port <= 65535:
        raise ControlledExecutionError(
            "observability.prometheus_port "
            "must be between 1 and 65535."
        )

    try:
        import xml.etree.ElementTree as ET

        root = ET.parse(
            jmx_path
        ).getroot()

    except (
        OSError,
        ET.ParseError,
    ) as exc:
        raise ControlledExecutionError(
            "Unable to inspect governed JMX "
            f"for Prometheus observability: {exc}"
        ) from exc

    listener_tag = (
        "com.github.johrstrom.listener."
        "PrometheusListener"
    )

    listeners = list(
        root.iter(
            listener_tag
        )
    )

    if not listeners:
        raise ControlledExecutionError(
            "Prometheus observability is configured "
            "in the execution profile, but the governed "
            "JMX does not contain PrometheusListener."
        )

    enabled = [
        item
        for item in listeners
        if str(
            item.attrib.get(
                "enabled",
                "true",
            )
        ).lower()
        == "true"
    ]

    if not enabled:
        raise ControlledExecutionError(
            "PrometheusListener exists in the governed "
            "JMX but is disabled."
        )

    required_metrics = {
        "jmeter_requests_total",
        "jmeter_success_total",
        "jmeter_error_total",
        "jmeter_response_time_ms",
    }

    configured_metrics = {
        str(
            item.text or ""
        ).strip()
        for listener in enabled
        for item in listener.iter(
            "stringProp"
        )
        if (
            item.attrib.get(
                "name"
            )
            == "collector.metric_name"
        )
    }

    missing = sorted(
        required_metrics
        - configured_metrics
    )

    if missing:
        raise ControlledExecutionError(
            "PrometheusListener is missing required "
            "metrics: "
            + ", ".join(
                missing
            )
        )

    port_properties = [
        str(
            item.text or ""
        ).strip()
        for listener in enabled
        for item in listener.iter(
            "stringProp"
        )
        if (
            item.attrib.get(
                "name"
            )
            == "prometheus.port"
        )
    ]

    expected_property = (
        "${__P(prometheus_port,"
        + str(port)
        + ")}"
    )

    if (
        expected_property
        not in port_properties
    ):
        raise ControlledExecutionError(
            "PrometheusListener port configuration "
            "does not match the execution profile. "
            f"Expected {expected_property}."
        )

    print(
        "Prometheus observability : VERIFIED"
    )
    print(
        f"Prometheus port          : {port}"
    )
    print(
        "Prometheus metrics       : "
        f"{len(required_metrics)} verified"
    )



def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Execute an explicitly authorized performance test using "
            "a validated execution profile and immutable pre-execution bundle."
        )
    )

    parser.add_argument(
        "--plan",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--profile",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--jmx",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--csv",
        type=Path,
    )
    parser.add_argument(
        "--data-requirements",
        type=Path,
    )
    parser.add_argument(
        "--design-context",
        type=Path,
    )
    parser.add_argument(
        "--properties",
        type=Path,
        help=(
            "Optional JMeter properties file. "
            "The controlled runner validates its immutable hash "
            "but never reads or prints its values."
        ),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(
            "work/pre-execution/"
            "controlled-runner-v2.json"
        ),
    )

    mode = parser.add_mutually_exclusive_group(
        required=True
    )
    mode.add_argument(
        "--preflight",
        action="store_true",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
    )

    args = parser.parse_args()

    project_root = (
        Path(__file__)
        .resolve()
        .parents[1]
    )

    try:
        plan_path = (
            args.plan
            .expanduser()
            .resolve()
        )
        profile_path = (
            args.profile
            .expanduser()
            .resolve()
        )
        jmx_path = (
            args.jmx
            .expanduser()
            .resolve()
        )
        manifest_path = (
            args.manifest
            .expanduser()
            .resolve()
        )
        csv_path = (
            args.csv
            .expanduser()
            .resolve()
            if args.csv
            else None
        )
        data_requirements = (
            args.data_requirements
            .expanduser()
            .resolve()
            if args.data_requirements
            else None
        )
        design_context = (
            args.design_context
            .expanduser()
            .resolve()
            if args.design_context
            else None
        )
        properties_file = (
            args.properties
            .expanduser()
            .resolve()
            if args.properties
            else None
        )

        require_file(
            plan_path,
            "Plan",
        )
        require_file(
            profile_path,
            "Execution profile",
        )
        require_file(
            jmx_path,
            "JMX",
        )

        if csv_path is not None:
            require_file(
                csv_path,
                "CSV",
            )

        if data_requirements is not None:
            require_file(
                data_requirements,
                "Data requirements",
            )

        if design_context is not None:
            require_file(
                design_context,
                "Design context",
            )

        if properties_file is not None:
            require_file(
                properties_file,
                "JMeter properties",
            )

        plan = load_yaml(
            plan_path
        )
        profile = load_yaml(
            profile_path
        )

        runtime = profile_runtime(
            profile,
            plan,
        )

        validate_prometheus_observability(
            profile=profile,
            jmx_path=jmx_path,
        )

        # Always produce a fresh pre-execution manifest for the exact bundle
        # that this invocation may execute.
        run_pre_execution_gate(
            project_root=project_root,
            plan=plan_path,
            profile=profile_path,
            jmx=jmx_path,
            csv_path=csv_path,
            data_requirements=data_requirements,
            design_context=design_context,
            manifest=manifest_path,
            properties_file=properties_file,
        )

        verify_manifest(
            manifest_path=manifest_path,
            plan=plan_path,
            profile=profile_path,
            jmx=jmx_path,
            csv_path=csv_path,
            data_requirements=data_requirements,
            design_context=design_context,
            properties_file=properties_file,
        )

        print_controlled_preflight(
            plan=plan,
            plan_path=plan_path,
            profile_path=profile_path,
            jmx_path=jmx_path,
            manifest_path=manifest_path,
            runtime=runtime,
        )

        if args.preflight:
            try:
                validate_execution_authorization(
                    plan
                )
                print(
                    "AUTHORIZATION CHECK: AUTHORIZED"
                )
            except ControlledExecutionError as exc:
                print(
                    "AUTHORIZATION CHECK: NOT AUTHORIZED"
                )
                print(
                    f"Reason: {exc}"
                )

            print(
                "EXECUTION NOT STARTED - PREFLIGHT ONLY"
            )
            return 0

        authorization = (
            validate_execution_authorization(
                plan
            )
        )

        # Re-verify immutable inputs after authorization checks and
        # immediately before the human confirmation.
        verify_manifest(
            manifest_path=manifest_path,
            plan=plan_path,
            profile=profile_path,
            jmx=jmx_path,
            csv_path=csv_path,
            data_requirements=data_requirements,
            design_context=design_context,
            properties_file=properties_file,
        )

        print()
        print(
            "Execution is authorized for this exact validated bundle."
        )
        print(
            f"Authorized by: "
            f"{authorization['authorized_by']}"
        )
        print(
            f"Authorized at: "
            f"{authorization['authorized_at']}"
        )
        print()
        confirmation = input(
            "Type RUN to execute exactly these validated parameters: "
        ).strip()

        if confirmation != "RUN":
            print(
                "Execution cancelled."
            )
            return 2

        # Final TOCTOU check immediately before spawning run_test.py.
        verify_manifest(
            manifest_path=manifest_path,
            plan=plan_path,
            profile=profile_path,
            jmx=jmx_path,
            csv_path=csv_path,
            data_requirements=data_requirements,
            design_context=design_context,
            properties_file=properties_file,
        )

        command = build_low_level_command(
            project_root=project_root,
            plan=plan,
            jmx_path=jmx_path,
            runtime=runtime,
            properties_file=properties_file,
        )

        print(
            "Executing exact pre-validated authorized workload..."
        )

        return subprocess.run(
            command,
            cwd=project_root,
        ).returncode

    except (
        ControlledExecutionError,
        KeyError,
        TypeError,
        ValueError,
        OSError,
    ) as exc:
        print(
            f"CONTROLLED EXECUTION ERROR: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
