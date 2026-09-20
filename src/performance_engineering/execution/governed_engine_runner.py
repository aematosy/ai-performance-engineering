from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
from typing import Any

import yaml

from performance_engineering.application.engine_runtime import (
    EngineResolutionError,
    read_engine_from_profile,
    resolve_engine,
)


class GovernedEngineExecutionError(
    RuntimeError
):
    """Governed multi-engine execution failure."""


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


def load_yaml(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(
            path.read_text(
                encoding="utf-8"
            )
        )
    except FileNotFoundError as exc:
        raise GovernedEngineExecutionError(
            f"File not found: {path}"
        ) from exc
    except yaml.YAMLError as exc:
        raise GovernedEngineExecutionError(
            f"Invalid YAML in {path}: {exc}"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise GovernedEngineExecutionError(
            f"YAML root must be an object: {path}"
        )

    return payload


def load_json(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except FileNotFoundError as exc:
        raise GovernedEngineExecutionError(
            f"File not found: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise GovernedEngineExecutionError(
            f"Invalid JSON in {path}: {exc}"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise GovernedEngineExecutionError(
            f"JSON root must be an object: {path}"
        )

    return payload


def sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def require_file(
    path: Path,
    label: str,
) -> Path:
    path = (
        path
        .expanduser()
        .resolve()
    )

    if not path.is_file():
        raise GovernedEngineExecutionError(
            f"{label} not found: {path}"
        )

    return path


def scenario_name(
    plan: dict[str, Any],
) -> str:
    metadata = plan.get(
        "metadata"
    )

    if isinstance(
        metadata,
        dict,
    ):
        value = str(
            metadata.get(
                "name",
                "",
            )
        ).strip()

        if value:
            return value

    raise GovernedEngineExecutionError(
        "Plan metadata.name is required."
    )


def target_string(
    plan: dict[str, Any],
) -> str:
    transactions = plan.get(
        "transactions"
    )

    target = plan.get(
        "target"
    )

    if (
        not isinstance(
            transactions,
            list,
        )
        or not transactions
        or not isinstance(
            transactions[0],
            dict,
        )
    ):
        raise GovernedEngineExecutionError(
            "Plan must contain at least one transaction."
        )

    if not isinstance(
        target,
        dict,
    ):
        raise GovernedEngineExecutionError(
            "Plan target must be an object."
        )

    tx = transactions[0]

    method = str(
        tx.get(
            "method",
            "",
        )
    ).upper()

    protocol = str(
        target.get(
            "protocol",
            "",
        )
    )

    host = str(
        target.get(
            "host",
            "",
        )
    )

    path = str(
        tx.get(
            "path",
            "",
        )
    )

    try:
        port = int(
            target.get(
                "port"
            )
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise GovernedEngineExecutionError(
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


def validate_authorization(
    plan: dict[str, Any],
) -> dict[str, str]:
    if str(
        plan.get(
            "status",
            "",
        )
    ).upper() != "APPROVED":
        raise GovernedEngineExecutionError(
            "Plan status must be APPROVED."
        )

    workload = plan.get(
        "workload"
    )

    if not isinstance(
        workload,
        dict,
    ):
        raise GovernedEngineExecutionError(
            "Plan workload is missing."
        )

    if str(
        workload.get(
            "status",
            "",
        )
    ).upper() != "APPROVED":
        raise GovernedEngineExecutionError(
            "Workload status must be APPROVED."
        )

    authorization = plan.get(
        "authorization"
    )

    approval = plan.get(
        "approval"
    )

    if not isinstance(
        authorization,
        dict,
    ):
        raise GovernedEngineExecutionError(
            "Plan authorization section is missing."
        )

    if not isinstance(
        approval,
        dict,
    ):
        raise GovernedEngineExecutionError(
            "Plan approval section is missing."
        )

    status = str(
        authorization.get(
            "status",
            "",
        )
    ).upper()

    authorized_by = str(
        authorization.get(
            "authorized_by"
        )
        or ""
    ).strip()

    authorized_at = str(
        authorization.get(
            "authorized_at"
        )
        or ""
    ).strip()

    if status != "AUTHORIZED":
        raise GovernedEngineExecutionError(
            "Execution authorization is not AUTHORIZED."
        )

    if approval.get(
        "execution_authorized"
    ) is not True:
        raise GovernedEngineExecutionError(
            "approval.execution_authorized must be true."
        )

    if not authorized_by:
        raise GovernedEngineExecutionError(
            "authorization.authorized_by is required."
        )

    if (
        authorized_by.lower()
        in GENERIC_IDENTITIES
    ):
        raise GovernedEngineExecutionError(
            "authorization.authorized_by must identify "
            "an explicit human."
        )

    if not authorized_at:
        raise GovernedEngineExecutionError(
            "authorization.authorized_at is required."
        )

    return {
        "status": status,
        "authorized_by":
            authorized_by,
        "authorized_at":
            authorized_at,
    }


def profile_runtime(
    profile: dict[str, Any],
) -> dict[str, Any]:
    execution = profile.get(
        "execution"
    )

    if not isinstance(
        execution,
        dict,
    ):
        raise GovernedEngineExecutionError(
            "Execution profile execution section is missing."
        )

    try:
        return {
            "mode": str(
                execution["mode"]
            ).upper(),
            "threads": int(
                execution["threads"]
            ),
            "ramp_time_seconds": int(
                execution[
                    "ramp_time_seconds"
                ]
            ),
            "duration_seconds": int(
                execution[
                    "duration_seconds"
                ]
            ),
            "pacing_seconds": float(
                execution[
                    "pacing_seconds"
                ]
            ),
        }
    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise GovernedEngineExecutionError(
            "Execution profile contains invalid runtime values."
        ) from exc


def validate_plan_profile(
    *,
    plan: dict[str, Any],
    runtime: dict[str, Any],
) -> None:
    workload = plan.get(
        "workload",
        {}
    )

    parameters = (
        workload.get(
            "parameters",
            {}
        )
        if isinstance(
            workload,
            dict,
        )
        else {}
    )

    comparisons = (
        (
            "threads",
            int,
        ),
        (
            "ramp_time_seconds",
            int,
        ),
        (
            "duration_seconds",
            int,
        ),
        (
            "pacing_seconds",
            float,
        ),
    )

    for key, cast in comparisons:
        if key not in parameters:
            raise GovernedEngineExecutionError(
                f"Approved workload is missing {key}."
            )

        approved = cast(
            parameters[key]
        )

        actual = cast(
            runtime[key]
        )

        if actual != approved:
            raise GovernedEngineExecutionError(
                "Execution profile differs from approved "
                f"workload for {key}: "
                f"approved={approved}, profile={actual}."
            )


def manifest_payload(
    *,
    engine: str,
    plan_path: Path,
    profile_path: Path,
    artifact_path: Path,
    authorization: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": "3.0",
        "status":
            "PRE_EXECUTION_READY",
        "engine":
            engine,
        "execution_performed":
            False,
        "created_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
        "authorization": {
            "status":
                authorization["status"],
            "authorized_by":
                authorization[
                    "authorized_by"
                ],
            "authorized_at":
                authorization[
                    "authorized_at"
                ],
            "granted_by_gate":
                False,
        },
        "inputs": {
            "plan": {
                "path":
                    str(
                        plan_path.resolve()
                    ),
                "sha256":
                    sha256(
                        plan_path
                    ),
            },
            "profile": {
                "path":
                    str(
                        profile_path.resolve()
                    ),
                "sha256":
                    sha256(
                        profile_path
                    ),
            },
            "engine_artifact": {
                "path":
                    str(
                        artifact_path.resolve()
                    ),
                "sha256":
                    sha256(
                        artifact_path
                    ),
            },
        },
    }


def write_manifest(
    *,
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def verify_manifest(
    *,
    manifest_path: Path,
    engine: str,
    plan_path: Path,
    profile_path: Path,
    artifact_path: Path,
) -> None:
    manifest = load_json(
        manifest_path
    )

    if manifest.get(
        "schema_version"
    ) != "3.0":
        raise GovernedEngineExecutionError(
            "Governed engine manifest must use schema_version 3.0."
        )

    if str(
        manifest.get(
            "status",
            "",
        )
    ) != "PRE_EXECUTION_READY":
        raise GovernedEngineExecutionError(
            "Manifest is not PRE_EXECUTION_READY."
        )

    if manifest.get(
        "engine"
    ) != engine:
        raise GovernedEngineExecutionError(
            "Manifest engine differs from execution profile."
        )

    inputs = manifest.get(
        "inputs"
    )

    if not isinstance(
        inputs,
        dict,
    ):
        raise GovernedEngineExecutionError(
            "Manifest inputs are missing."
        )

    expected = {
        "plan": plan_path,
        "profile": profile_path,
        "engine_artifact":
            artifact_path,
    }

    for key, path in expected.items():
        record = inputs.get(
            key
        )

        if not isinstance(
            record,
            dict,
        ):
            raise GovernedEngineExecutionError(
                f"Manifest artifact missing: {key}."
            )

        recorded_path = Path(
            str(
                record.get(
                    "path",
                    "",
                )
            )
        ).expanduser().resolve()

        if recorded_path != path.resolve():
            raise GovernedEngineExecutionError(
                f"Manifest path mismatch: {key}."
            )

        recorded_hash = str(
            record.get(
                "sha256",
                "",
            )
        )

        if recorded_hash != sha256(
            path
        ):
            raise GovernedEngineExecutionError(
                "Artifact changed after preflight: "
                f"{key}."
            )


def print_preflight(
    *,
    engine: str,
    plan: dict[str, Any],
    plan_path: Path,
    profile_path: Path,
    artifact_path: Path,
    manifest_path: Path,
    runtime: dict[str, Any],
    authorization: dict[str, str],
) -> None:
    print()
    print("=" * 74)
    print(
        "GOVERNED MULTI-ENGINE PREFLIGHT"
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
        f"Engine          : "
        f"{engine.upper()}"
    )

    print(
        f"Artifact        : "
        f"{artifact_path}"
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
        f"Plan status     : "
        f"{plan.get('status')}"
    )

    print(
        f"Workload        : "
        f"{plan.get('workload', {}).get('status')}"
    )

    print(
        f"Authorization   : "
        f"{authorization['status']}"
    )

    print(
        f"Authorized by   : "
        f"{authorization['authorized_by']}"
    )

    print(
        f"Manifest        : "
        f"{manifest_path}"
    )

    print(
        "Artifact hashes : VERIFIED"
    )

    print(
        "Execution       : NOT STARTED"
    )

    print("=" * 74)
    print(
        "PRE_EXECUTION_READY"
    )
    print("=" * 74)


def prometheus_port(
    profile: dict[str, Any],
) -> int:
    observability = profile.get(
        "observability"
    )

    if not isinstance(
        observability,
        dict,
    ):
        raise GovernedEngineExecutionError(
            "Execution profile observability section is missing."
        )

    try:
        port = int(
            observability[
                "prometheus_port"
            ]
        )
    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise GovernedEngineExecutionError(
            "observability.prometheus_port must be an integer."
        ) from exc

    if not 1 <= port <= 65535:
        raise GovernedEngineExecutionError(
            "observability.prometheus_port must be between "
            "1 and 65535."
        )

    return port


def execute_engine(
    *,
    project_root: Path,
    engine_name: str,
    engine: Any,
    artifact_path: Path,
    plan: dict[str, Any],
    profile: dict[str, Any],
    profile_path: Path,
    runtime: dict[str, Any],
    execution_dir: Path | None,
) -> Path:
    if engine_name == "locust":
        target_dir = (
            execution_dir
            if execution_dir is not None
            else (
                project_root
                / "results"
                / (
                    "locust-"
                    + scenario_name(plan)
                )
            )
        )

        return engine.execute(
            artifact_path,
            {
                "profile":
                    str(profile_path),
                "execution_dir":
                    str(target_dir),
            },
        )

    if engine_name == "jmeter":
        results_root = (
            project_root
            / "results"
        ).resolve()

        reports_root = (
            project_root
            / "reports"
        ).resolve()

        arguments = [
            "--jmx",
            str(artifact_path),
            "--scenario",
            scenario_name(plan),
            "--target",
            target_string(plan),
            "--environment",
            str(
                plan.get(
                    "environment",
                    "",
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
                prometheus_port(
                    profile
                )
            ),
            "--results-directory",
            str(results_root),
            "--reports-directory",
            str(reports_root),
            "--authorized",
            "--skip-environment-validation",
        ]

        return engine.execute(
            artifact_path,
            {
                "runner":
                    str(
                        project_root
                        / "scripts"
                        / "run_test.py"
                    ),
                "arguments":
                    arguments,
                "results_root":
                    str(results_root),
                "execution_dir":
                    (
                        str(execution_dir)
                        if execution_dir
                        else None
                    ),
            },
        )

    raise GovernedEngineExecutionError(
        f"Unsupported engine: {engine_name}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Governed multi-engine performance execution."
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
        "--artifact",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--manifest",
        type=Path,
    )

    parser.add_argument(
        "--execution-dir",
        type=Path,
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

    return parser


def main() -> int:
    args = build_parser().parse_args()

    project_root = (
        Path(__file__)
        .resolve()
        .parents[3]
    )

    try:
        plan_path = require_file(
            args.plan,
            "Plan",
        )

        profile_path = require_file(
            args.profile,
            "Execution profile",
        )

        artifact_path = require_file(
            args.artifact,
            "Engine artifact",
        )

        engine_name = (
            read_engine_from_profile(
                profile_path
            )
        )

        if engine_name not in {
            "jmeter",
            "locust",
        }:
            raise GovernedEngineExecutionError(
                f"Unsupported engine: {engine_name}"
            )

        plan = load_yaml(
            plan_path
        )

        profile = load_yaml(
            profile_path
        )

        authorization = (
            validate_authorization(
                plan
            )
        )

        runtime = profile_runtime(
            profile
        )

        validate_plan_profile(
            plan=plan,
            runtime=runtime,
        )

        engine = resolve_engine(
            project_root=project_root,
            engine_name=engine_name,
        )

        engine.validate(
            artifact_path,
            {
                "plan":
                    str(plan_path),
                "profile":
                    str(profile_path),
            },
        )

        manifest_path = (
            args.manifest
            .expanduser()
            .resolve()
            if args.manifest
            else (
                project_root
                / "results"
                / "preflight"
                / scenario_name(plan)
                / "controlled-engine-v3.json"
            )
        )

        if args.preflight:
            payload = manifest_payload(
                engine=engine_name,
                plan_path=plan_path,
                profile_path=profile_path,
                artifact_path=artifact_path,
                authorization=authorization,
            )

            write_manifest(
                path=manifest_path,
                payload=payload,
            )

            verify_manifest(
                manifest_path=manifest_path,
                engine=engine_name,
                plan_path=plan_path,
                profile_path=profile_path,
                artifact_path=artifact_path,
            )

            print_preflight(
                engine=engine_name,
                plan=plan,
                plan_path=plan_path,
                profile_path=profile_path,
                artifact_path=artifact_path,
                manifest_path=manifest_path,
                runtime=runtime,
                authorization=authorization,
            )

            print()
            print(
                "EXECUTION NOT STARTED - PREFLIGHT ONLY"
            )

            return 0

        if not manifest_path.is_file():
            raise GovernedEngineExecutionError(
                "Governed execution requires an existing "
                "PRE_EXECUTION_READY manifest produced by "
                "the preflight step: "
                f"{manifest_path}"
            )

        # Never regenerate the governed manifest during execution.
        # The exact preflight bundle must remain immutable.
        verify_manifest(
            manifest_path=manifest_path,
            engine=engine_name,
            plan_path=plan_path,
            profile_path=profile_path,
            artifact_path=artifact_path,
        )

        print_preflight(
            engine=engine_name,
            plan=plan,
            plan_path=plan_path,
            profile_path=profile_path,
            artifact_path=artifact_path,
            manifest_path=manifest_path,
            runtime=runtime,
            authorization=authorization,
        )

        print()
        print(
            "Execution is authorized for this exact "
            "preflight-validated bundle."
        )
        print(
            f"Engine        : {engine_name.upper()}"
        )
        print(
            f"Authorized by : "
            f"{authorization['authorized_by']}"
        )
        print(
            f"Authorized at : "
            f"{authorization['authorized_at']}"
        )
        print()

        confirmation = input(
            "Type RUN to execute exactly "
            "these validated parameters: "
        ).strip()

        if confirmation != "RUN":
            raise GovernedEngineExecutionError(
                "Execution cancelled. "
                "Exact RUN confirmation was not provided."
            )

        # Final TOCTOU verification immediately before load.
        verify_manifest(
            manifest_path=manifest_path,
            engine=engine_name,
            plan_path=plan_path,
            profile_path=profile_path,
            artifact_path=artifact_path,
        )

        requested_execution_dir = (
            args.execution_dir
            .expanduser()
            .resolve()
            if args.execution_dir
            else None
        )

        result = execute_engine(
            project_root=project_root,
            engine_name=engine_name,
            engine=engine,
            artifact_path=artifact_path,
            plan=plan,
            profile=profile,
            profile_path=profile_path,
            runtime=runtime,
            execution_dir=requested_execution_dir,
        )

        print()
        print("=" * 74)
        print("GOVERNED EXECUTION COMPLETE")
        print("=" * 74)
        print(
            f"Engine     : {engine_name.upper()}"
        )
        print(
            f"Results    : {result}"
        )
        print("=" * 74)

        return 0

    except (
        GovernedEngineExecutionError,
        EngineResolutionError,
        RuntimeError,
        OSError,
    ) as exc:
        print(
            f"GOVERNED ENGINE ERROR: {exc}",
            file=sys.stderr,
        )

        return 2


if __name__ == "__main__":
    raise SystemExit(main())
