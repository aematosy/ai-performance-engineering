#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class PreExecutionGateError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise PreExecutionGateError(
            f"{label} not found: {path}"
        )

    if not path.is_file():
        raise PreExecutionGateError(
            f"{label} is not a file: {path}"
        )


def artifact_record(
    path: Path | None,
) -> dict[str, str] | None:
    if path is None:
        return None

    return {
        "path": str(path),
        "sha256": sha256(path),
    }


def run_stage(
    *,
    name: str,
    command: list[str],
) -> dict[str, Any]:
    print()
    print("=" * 78)
    print(f"PRE-EXECUTION STAGE: {name}")
    print("=" * 78)

    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
    )

    if result.stdout:
        print(result.stdout, end="")

    if result.stderr:
        print(
            result.stderr,
            end="",
            file=sys.stderr,
        )

    return {
        "name": name,
        "command": command,
        "returncode": result.returncode,
        "status": (
            "PASS"
            if result.returncode == 0
            else "FAIL"
        ),
    }


def build_bundle_command(
    *,
    root: Path,
    plan: Path,
    jmx: Path | None,
    csv_path: Path | None,
    data_requirements: Path | None,
    design_context: Path | None,
) -> list[str]:
    command = [
        sys.executable,
        str(
            root
            / "scripts"
            / "validate_execution_bundle.py"
        ),
        "--plan",
        str(plan),
    ]

    if jmx is not None:
        command.extend(
            [
                "--jmx",
                str(jmx),
            ]
        )

    if design_context is not None:
        command.extend(
            [
                "--design-context",
                str(design_context),
                "--require-explicit-source-binding",
            ]
        )

    if data_requirements is not None:
        command.extend(
            [
                "--data-requirements",
                str(data_requirements),
            ]
        )

    # csv_path is intentionally not passed to validate_execution_bundle.py.
    # Its candidate identity is proven through data-requirements.json.
    _ = csv_path

    return command


def validate_input_contract(
    *,
    csv_path: Path | None,
    data_requirements: Path | None,
    design_context: Path | None,
) -> None:
    if (
        csv_path is not None
        and data_requirements is None
    ):
        raise PreExecutionGateError(
            "CSV requires --data-requirements so the "
            "scenario identity and data contract can be proven."
        )

    if (
        design_context is not None
        and data_requirements is None
    ):
        raise PreExecutionGateError(
            "Design context requires --data-requirements "
            "for candidate-coherence validation."
        )

    if (
        data_requirements is not None
        and csv_path is None
        and design_context is None
    ):
        raise PreExecutionGateError(
            "--data-requirements was provided without "
            "--csv or --design-context."
        )



def detect_postman_artifact_kind(
    path: Path,
) -> str:
    """
    Detect the governed design artifact contract.

    Historical function name is intentionally preserved
    for backward compatibility with existing callers/tests.

    Supported contracts:
    - legacy Postman DESIGN_CONTEXT;
    - strict Postman executable model;
    - normalized CLI executable model.
    """

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8",
            )
        )
    except json.JSONDecodeError as exc:
        raise PreExecutionGateError(
            "Scenario artifact is not valid JSON: "
            f"{path}: line {exc.lineno}, "
            f"column {exc.colno}"
        ) from exc

    if not isinstance(payload, dict):
        raise PreExecutionGateError(
            "Scenario artifact root must be "
            "a JSON object."
        )

    # Historical Postman design-context contract.
    if (
        isinstance(
            payload.get("collection"),
            dict,
        )
        and isinstance(
            payload.get("environment"),
            dict,
        )
        and isinstance(
            payload.get("dependencies"),
            list,
        )
        and isinstance(
            payload.get(
                "scenario_candidate"
            ),
            dict,
        )
    ):
        return "DESIGN_CONTEXT"

    source = payload.get("source")

    if not isinstance(source, dict):
        raise PreExecutionGateError(
            "Scenario artifact source metadata "
            f"is missing: {path}"
        )

    source_type = str(
        source.get("type", "")
    ).strip().upper()

    # Keep the existing Postman contract strict.
    if source_type == "POSTMAN":
        if (
            isinstance(
                payload.get(
                    "scenario_candidate"
                ),
                dict,
            )
            and isinstance(
                payload.get("requests"),
                list,
            )
            and isinstance(
                payload.get(
                    "correlations"
                ),
                list,
            )
            and isinstance(
                payload.get("csv"),
                dict,
            )
            and isinstance(
                payload.get("secrets"),
                dict,
            )
            and isinstance(
                payload.get("readiness"),
                dict,
            )
        ):
            return (
                "POSTMAN_EXECUTABLE_MODEL"
            )

        raise PreExecutionGateError(
            "Unsupported Postman executable "
            f"model contract: {path}"
        )

    # CLI/cURL/structured API executable model.
    # CSV/readiness are not mandatory because those are
    # Postman-specific contract sections.
    if source_type == "NORMALIZED_CLI":
        if (
            isinstance(
                payload.get(
                    "scenario_candidate"
                ),
                dict,
            )
            and isinstance(
                payload.get("requests"),
                list,
            )
            and isinstance(
                payload.get(
                    "correlations"
                ),
                list,
            )
        ):
            return "CLI_EXECUTABLE_MODEL"

        raise PreExecutionGateError(
            "Unsupported normalized CLI "
            f"executable model contract: {path}"
        )

    raise PreExecutionGateError(
        "Unsupported scenario artifact "
        f"source type '{source_type}': {path}"
    )



def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run deterministic pre-execution safety gates. "
            "This command never executes JMeter and never "
            "grants execution authorization."
        )
    )

    parser.add_argument(
        "--plan",
        required=True,
    )
    parser.add_argument(
        "--profile",
        required=True,
    )
    parser.add_argument(
        "--jmx",
    )
    parser.add_argument(
        "--csv",
    )
    parser.add_argument(
        "--data-requirements",
    )
    parser.add_argument(
        "--design-context",
    )
    parser.add_argument(
        "--properties",
        help=(
            "Optional JMeter properties file. "
            "Only path and SHA-256 are persisted in the manifest."
        ),
    )
    parser.add_argument(
        "--manifest",
        default=(
            "work/pre-execution/"
            "pre-execution-manifest.json"
        ),
    )

    parser.add_argument(
        "--skip-environment",
        action="store_true",
    )
    parser.add_argument(
        "--skip-plan-review",
        action="store_true",
    )
    parser.add_argument(
        "--skip-jmx-validation",
        action="store_true",
    )
    parser.add_argument(
        "--require-execution-ready-context",
        action="store_true",
    )

    args = parser.parse_args()

    root = Path.cwd().resolve()

    plan = (
        Path(args.plan)
        .expanduser()
        .resolve()
    )
    profile = (
        Path(args.profile)
        .expanduser()
        .resolve()
    )
    jmx = (
        Path(args.jmx)
        .expanduser()
        .resolve()
        if args.jmx
        else None
    )
    csv_path = (
        Path(args.csv)
        .expanduser()
        .resolve()
        if args.csv
        else None
    )
    data_requirements = (
        Path(args.data_requirements)
        .expanduser()
        .resolve()
        if args.data_requirements
        else None
    )
    design_context = (
        Path(args.design_context)
        .expanduser()
        .resolve()
        if args.design_context
        else None
    )
    properties_file = (
        Path(args.properties)
        .expanduser()
        .resolve()
        if args.properties
        else None
    )
    manifest_path = (
        Path(args.manifest)
        .expanduser()
        .resolve()
    )

    try:
        require_file(
            plan,
            "Plan",
        )
        require_file(
            profile,
            "Execution profile",
        )

        if jmx is not None:
            require_file(
                jmx,
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

        validate_input_contract(
            csv_path=csv_path,
            data_requirements=data_requirements,
            design_context=design_context,
        )

        stages: list[
            dict[str, Any]
        ] = []

        if not args.skip_environment:
            stages.append(
                run_stage(
                    name=(
                        "VALIDATE_ENVIRONMENT"
                    ),
                    command=[
                        sys.executable,
                        str(
                            root
                            / "scripts"
                            / "validate_environment.py"
                        ),
                    ],
                )
            )

        if not args.skip_plan_review:
            stages.append(
                run_stage(
                    name="REVIEW_TEST_PLAN",
                    command=[
                        sys.executable,
                        str(
                            root
                            / "scripts"
                            / "review_test_plan.py"
                        ),
                        "--plan",
                        str(plan),
                        "--strict",
                    ],
                )
            )

        stages.append(
            run_stage(
                name="VALIDATE_TEST_PLAN",
                command=[
                    sys.executable,
                    str(
                        root
                        / "scripts"
                        / "validate_test_plan.py"
                    ),
                    "--plan",
                    str(plan),
                ],
            )
        )

        stages.append(
            run_stage(
                name=(
                    "VALIDATE_EXECUTION_PROFILE"
                ),
                command=[
                    sys.executable,
                    str(
                        root
                        / "scripts"
                        / "validate_execution_profile.py"
                    ),
                    "--profile",
                    str(profile),
                ],
            )
        )

        stages.append(
            run_stage(
                name=(
                    "COMPARE_PROFILE_TO_APPROVED_PLAN"
                ),
                command=[
                    sys.executable,
                    str(
                        root
                        / "scripts"
                        / "validate_execution_against_plan.py"
                    ),
                    "--plan",
                    str(plan),
                    "--profile",
                    str(profile),
                ],
            )
        )

        stages.append(
            run_stage(
                name=(
                    "VALIDATE_EXECUTION_BUNDLE"
                ),
                command=build_bundle_command(
                    root=root,
                    plan=plan,
                    jmx=jmx,
                    csv_path=csv_path,
                    data_requirements=(
                        data_requirements
                    ),
                    design_context=(
                        design_context
                    ),
                ),
            )
        )

        if csv_path is not None:
            stages.append(
                run_stage(
                    name=(
                        "VALIDATE_DATA_CAPACITY"
                    ),
                    command=[
                        sys.executable,
                        str(
                            root
                            / "scripts"
                            / "validate_data_capacity.py"
                        ),
                        "--profile",
                        str(profile),
                        "--csv",
                        str(csv_path),
                        "--execution-ready",
                    ],
                )
            )

        if design_context is not None:
            artifact_kind = (
                detect_postman_artifact_kind(
                    design_context
                )
            )

            if artifact_kind == "DESIGN_CONTEXT":
                command = [
                    sys.executable,
                    str(
                        root
                        / "scripts"
                        / "validate_postman_design_context.py"
                    ),
                    "--input",
                    str(design_context),
                ]

                if (
                    args.require_execution_ready_context
                ):
                    command.append(
                        "--execution-ready"
                    )

            elif (
                artifact_kind
                == "POSTMAN_EXECUTABLE_MODEL"
            ):
                if jmx is None:
                    raise PreExecutionGateError(
                        "Executable Postman model validation "
                        "requires --jmx."
                    )

                if csv_path is None:
                    raise PreExecutionGateError(
                        "Executable Postman model validation "
                        "requires --csv."
                    )

                command = [
                    sys.executable,
                    str(
                        root
                        / "scripts"
                        / "validate_postman_jmx.py"
                    ),
                    "--model",
                    str(design_context),
                    "--jmx",
                    str(jmx),
                    "--csv",
                    str(csv_path),
                ]

            elif (
                artifact_kind
                == "CLI_EXECUTABLE_MODEL"
            ):
                if jmx is None:
                    raise PreExecutionGateError(
                        "Executable CLI model validation "
                        "requires --jmx."
                    )

                command = [
                    sys.executable,
                    str(
                        root
                        / "scripts"
                        / "validate_cli_jmx.py"
                    ),
                    "--model",
                    str(design_context),
                    "--jmx",
                    str(jmx),
                ]

            else:
                raise PreExecutionGateError(
                    "Unsupported Postman artifact kind: "
                    f"{artifact_kind}"
                )

            stages.append(
                run_stage(
                    # Keep the historical stage name so existing
                    # manifests/tests remain backward-compatible.
                    name=(
                        "VALIDATE_DESIGN_CONTEXT"
                    ),
                    command=command,
                )
            )

        if (
            jmx is not None
            and not args.skip_jmx_validation
        ):
            stages.append(
                run_stage(
                    name=(
                        "VALIDATE_JMX_ARTIFACT"
                    ),
                    command=[
                        sys.executable,
                        str(
                            root
                            / "scripts"
                            / "validate_jmx_artifact.py"
                        ),
                        "--jmx",
                        str(jmx),
                        "--plan",
                        str(plan),
                    ],
                )
            )

        failed = [
            stage
            for stage in stages
            if stage[
                "returncode"
            ] != 0
        ]

        final_status = (
            "PRE_EXECUTION_READY"
            if not failed
            else "PRE_EXECUTION_BLOCKED"
        )

        manifest = {
            "schema_version": "2.0",
            "created_at_utc": (
                datetime.now(
                    timezone.utc
                ).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
            ),
            "status": final_status,
            "execution_performed": False,
            "inputs": {
                "plan": artifact_record(
                    plan
                ),
                "profile": artifact_record(
                    profile
                ),
                "jmx": artifact_record(
                    jmx
                ),
                "csv": artifact_record(
                    csv_path
                ),
                "data_requirements": (
                    artifact_record(
                        data_requirements
                    )
                ),
                "design_context": (
                    artifact_record(
                        design_context
                    )
                ),
                "properties": (
                    artifact_record(
                        properties_file
                    )
                ),
            },
            "stages": [
                {
                    "name": stage[
                        "name"
                    ],
                    "status": stage[
                        "status"
                    ],
                    "returncode": stage[
                        "returncode"
                    ],
                }
                for stage
                in stages
            ],
            "failed_stage_count": (
                len(failed)
            ),
            "authorization": {
                "granted_by_gate": False,
                "message": (
                    "This gate never grants "
                    "execution authorization."
                ),
            },
        }

        manifest_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        manifest_path.write_text(
            json.dumps(
                manifest,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    except PreExecutionGateError as exc:
        print(
            "PRE-EXECUTION GATE ERROR: "
            f"{exc}",
            file=sys.stderr,
        )
        return 2

    print()
    print("=" * 78)
    print(
        "PRE-EXECUTION GATE SUMMARY v2"
    )
    print("=" * 78)
    print(
        f"Plan             : "
        f"{plan}"
    )
    print(
        f"Profile          : "
        f"{profile}"
    )
    print(
        "JMX              : "
        f"{jmx if jmx else 'NOT PROVIDED'}"
    )
    print(
        "CSV              : "
        f"{csv_path if csv_path else 'NOT PROVIDED'}"
    )
    print(
        "Data requirements: "
        f"{data_requirements if data_requirements else 'NOT PROVIDED'}"
    )
    print(
        "Design context   : "
        f"{design_context if design_context else 'NOT PROVIDED'}"
    )
    print(
        "Properties file  : "
        f"{properties_file if properties_file else 'NOT PROVIDED'}"
    )
    print(
        f"Stages           : "
        f"{len(stages)}"
    )
    print(
        f"Failed           : "
        f"{len(failed)}"
    )
    print(
        f"Final status     : "
        f"{final_status}"
    )
    print(
        f"Manifest         : "
        f"{manifest_path}"
    )
    print(
        "JMeter run       : "
        "NOT EXECUTED"
    )
    print(
        "Authorization    : "
        "NOT GRANTED BY THIS GATE"
    )
    print("=" * 78)

    return (
        0
        if not failed
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
