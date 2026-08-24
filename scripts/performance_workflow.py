#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class WorkflowError(RuntimeError):
    pass


def resolve_path(
    value: Path | None,
) -> Path | None:
    if value is None:
        return None

    value = value.expanduser()

    if not value.is_absolute():
        value = ROOT / value

    return value.resolve()


def require_file(
    path: Path | None,
    description: str,
) -> Path:
    if path is None:
        raise WorkflowError(
            f"{description} is required."
        )

    if not path.is_file():
        raise WorkflowError(
            f"{description} not found: {path}"
        )

    return path


def run_command(
    command: Sequence[str],
) -> None:
    print()
    print("=" * 78)
    print("PERFORMANCE WORKFLOW COMMAND")
    print("=" * 78)

    # Deliberately do not print secret/property contents.
    print(
        " ".join(
            str(part)
            for part in command
        )
    )

    print("=" * 78)
    print()

    completed = subprocess.run(
        list(command),
        cwd=ROOT,
        check=False,
    )

    if completed.returncode != 0:
        raise WorkflowError(
            "Deterministic stage failed with "
            f"exit code {completed.returncode}."
        )


def python_command(
    script_name: str,
) -> list[str]:
    script = SCRIPTS / script_name

    if not script.is_file():
        raise WorkflowError(
            f"Required script not found: {script}"
        )

    return [
        sys.executable,
        str(script),
    ]


def add_optional_path(
    command: list[str],
    flag: str,
    path: Path | None,
) -> None:
    if path is None:
        return

    command.extend(
        [
            flag,
            str(path),
        ]
    )



def build_design_profile(
    *,
    base_profile: Path,
    workspace: Path,
    users: int | None,
    duration_seconds: int | None,
    ramp_time_seconds: int | None,
    pacing_seconds: float | None,
) -> Path:
    import yaml

    supplied = [
        users is not None,
        duration_seconds is not None,
        ramp_time_seconds is not None,
        pacing_seconds is not None,
    ]

    # No design-time workload was supplied.
    # Preserve backward compatibility.
    if not any(supplied):
        return base_profile

    # Users and duration are the minimum meaningful workload.
    if users is None or duration_seconds is None:
        raise WorkflowError(
            "Dynamic workload requires both "
            "--users and --duration-seconds."
        )

    if users <= 0:
        raise WorkflowError(
            "--users must be greater than 0."
        )

    if duration_seconds <= 0:
        raise WorkflowError(
            "--duration-seconds must be greater than 0."
        )

    if (
        ramp_time_seconds is not None
        and ramp_time_seconds < 0
    ):
        raise WorkflowError(
            "--ramp-time-seconds cannot be negative."
        )

    if (
        pacing_seconds is not None
        and pacing_seconds < 0
    ):
        raise WorkflowError(
            "--pacing-seconds cannot be negative."
        )

    try:
        payload = yaml.safe_load(
            base_profile.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        raise WorkflowError(
            f"Unable to load base execution profile: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise WorkflowError(
            "Base execution profile must be a YAML object."
        )

    execution = payload.setdefault(
        "execution",
        {},
    )

    execution["mode"] = "DURATION"
    execution["threads"] = users
    execution["duration_seconds"] = duration_seconds

    if ramp_time_seconds is not None:
        execution["ramp_time_seconds"] = (
            ramp_time_seconds
        )

    if pacing_seconds is not None:
        execution["pacing_seconds"] = (
            pacing_seconds
        )

    profile = payload.setdefault(
        "profile",
        {},
    )

    profile["name"] = "generated-design-workload"
    profile["description"] = (
        "Scenario workload generated during governed "
        "performance intake from explicit user parameters."
    )

    workspace.mkdir(
        parents=True,
        exist_ok=True,
    )

    generated = (
        workspace
        / "execution-profile.yaml"
    )

    generated.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            width=1000,
        ),
        encoding="utf-8",
    )

    return generated




def materialize_design_profile(
    *,
    base_profile: Path,
    workspace: Path,
    users: int | None,
    duration_seconds: int | None,
    ramp_time_seconds: int | None,
    pacing_seconds: float | None,
) -> Path:
    """Materialize the effective design profile inside the workspace.

    Used by generic CLI/JMX intake.

    Existing Postman behavior remains unchanged.

    Rules:
    - When workload overrides are supplied, reuse build_design_profile().
    - Without overrides, materialize a validated copy of the configured
      base profile into workspace/execution-profile.yaml.
    - Never modify the original base profile.
    - Only DURATION mode is currently supported by the governed runtime.
    """

    import yaml

    base_profile = (
        base_profile
        .expanduser()
        .resolve()
    )

    if not base_profile.is_file():
        raise WorkflowError(
            "Execution profile not found: "
            f"{base_profile}"
        )

    workspace = (
        workspace
        .expanduser()
        .resolve()
    )

    workspace.mkdir(
        parents=True,
        exist_ok=True,
    )

    workload_supplied = any(
        (
            users is not None,
            duration_seconds is not None,
            ramp_time_seconds is not None,
            pacing_seconds is not None,
        )
    )

    if workload_supplied:
        return build_design_profile(
            base_profile=base_profile,
            workspace=workspace,
            users=users,
            duration_seconds=duration_seconds,
            ramp_time_seconds=ramp_time_seconds,
            pacing_seconds=pacing_seconds,
        )

    destination = (
        workspace
        / "execution-profile.yaml"
    )

    temporary = destination.with_suffix(
        destination.suffix + ".tmp"
    )

    try:
        payload = yaml.safe_load(
            base_profile.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise WorkflowError(
                "Base execution profile must be a YAML object."
            )

        execution = payload.get(
            "execution"
        )

        if not isinstance(
            execution,
            dict,
        ):
            raise WorkflowError(
                "Base execution profile requires "
                "an execution object."
            )

        mode = str(
            execution.get(
                "mode",
                "",
            )
        ).strip().upper()

        if mode != "DURATION":
            raise WorkflowError(
                "Generic intake currently requires "
                "a DURATION execution profile."
            )

        threads = execution.get(
            "threads"
        )

        duration = execution.get(
            "duration_seconds"
        )

        if not isinstance(
            threads,
            int,
        ) or threads <= 0:
            raise WorkflowError(
                "Base execution profile requires "
                "execution.threads > 0."
            )

        if not isinstance(
            duration,
            int,
        ) or duration <= 0:
            raise WorkflowError(
                "Base execution profile requires "
                "execution.duration_seconds > 0."
            )

        ramp = execution.get(
            "ramp_time_seconds"
        )

        if (
            ramp is not None
            and (
                not isinstance(
                    ramp,
                    int,
                )
                or ramp < 0
            )
        ):
            raise WorkflowError(
                "execution.ramp_time_seconds must be >= 0."
            )

        pacing = execution.get(
            "pacing_seconds"
        )

        if (
            pacing is not None
            and (
                not isinstance(
                    pacing,
                    (int, float),
                )
                or pacing < 0
            )
        ):
            raise WorkflowError(
                "execution.pacing_seconds must be >= 0."
            )

        temporary.write_text(
            yaml.safe_dump(
                payload,
                sort_keys=False,
                allow_unicode=True,
                width=1000,
            ),
            encoding="utf-8",
        )

        generated_payload = yaml.safe_load(
            temporary.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(
            generated_payload,
            dict,
        ):
            raise WorkflowError(
                "Generated execution profile is invalid."
            )

        temporary.replace(
            destination
        )

    except WorkflowError:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass

        raise

    except (
        OSError,
        yaml.YAMLError,
    ) as exc:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass

        raise WorkflowError(
            "Unable to materialize execution profile: "
            f"{exc}"
        ) from exc

    return destination


def build_intake_command(
    args: argparse.Namespace,
) -> list[str]:
    command = python_command(
        "performance_intake.py"
    )

    input_path = resolve_path(
        args.input
    )

    environment = resolve_path(
        args.environment
    )

    workspace = resolve_path(
        args.workspace
    )

    if workspace is None:
        raise WorkflowError(
            "Workspace is required."
        )

    forced_type = (
        str(args.input_type).lower()
        if args.input_type
        else None
    )

    detected_postman = (
        forced_type == "postman"
        or (
            forced_type is None
            and input_path is not None
            and input_path.name.lower().endswith(
                ".postman_collection.json"
            )
        )
    )

    if detected_postman:
        if input_path is None:
            raise WorkflowError(
                "Postman intake requires --input."
            )

        require_file(
            input_path,
            "Postman collection",
        )

        base_profile = resolve_path(
            args.profile
        )

        if base_profile is None:
            raise WorkflowError(
                "Postman intake requires an execution profile."
            )

        require_file(
            base_profile,
            "Execution profile",
        )

        profile = build_design_profile(
            base_profile=base_profile,
            workspace=workspace,
            users=args.users,
            duration_seconds=args.duration_seconds,
            ramp_time_seconds=args.ramp_time_seconds,
            pacing_seconds=args.pacing_seconds,
        )

        command = python_command(
            "prepare_postman_design.py"
        )

        command.extend(
            [
                "--collection",
                str(input_path),
                "--workspace",
                str(workspace),
                "--profile",
                str(profile),
            ]
        )

        if environment is not None:
            require_file(
                environment,
                "Postman environment",
            )

            command.extend(
                [
                    "--environment",
                    str(environment),
                ]
            )

        return command

    # Generic CLI/JMX intake uses the same governed execution-profile
    # contract as Postman, but preserves its own normalization path.
    base_profile = resolve_path(
        args.profile
    )

    if base_profile is None:
        raise WorkflowError(
            "CLI/JMX intake requires an execution profile."
        )

    require_file(
        base_profile,
        "Execution profile",
    )

    materialized_profile = (
        materialize_design_profile(
            base_profile=base_profile,
            workspace=workspace,
            users=args.users,
            duration_seconds=args.duration_seconds,
            ramp_time_seconds=args.ramp_time_seconds,
            pacing_seconds=args.pacing_seconds,
        )
    )

    if not materialized_profile.is_file():
        raise WorkflowError(
            "Execution profile was not materialized: "
            f"{materialized_profile}"
        )

    detected_cli = (
        forced_type == "cli"
        or (
            forced_type is None
            and input_path is None
        )
    )

    if detected_cli:
        command = python_command(
            "prepare_cli_design.py"
        )

        command.extend(
            [
                "--workspace",
                str(workspace),
                "--profile",
                str(materialized_profile),
            ]
        )

        if input_path is not None:
            require_file(
                input_path,
                "CLI input",
            )

            command.extend(
                [
                    "--input",
                    str(input_path),
                ]
            )

        elif args.target:
            command.extend(
                [
                    "--target",
                    args.target,
                ]
            )

            if args.method:
                command.extend(
                    [
                        "--method",
                        args.method,
                    ]
                )

        else:
            raise WorkflowError(
                "CLI intake requires either "
                "--input or --target."
            )

        return command

    if input_path is not None:
        require_file(
            input_path,
            "Input",
        )

        command.extend(
            [
                "--input",
                str(input_path),
            ]
        )

    if environment is not None:
        require_file(
            environment,
            "Environment",
        )

        command.extend(
            [
                "--environment",
                str(environment),
            ]
        )

    if args.input_type:
        command.extend(
            [
                "--input-type",
                args.input_type,
            ]
        )

    if args.target:
        command.extend(
            [
                "--target",
                args.target,
            ]
        )

    if args.method:
        command.extend(
            [
                "--method",
                args.method,
            ]
        )

    command.extend(
        [
            "--workspace",
            str(workspace),
        ]
    )

    return command


def resolve_runtime_properties(
    *,
    project_root: Path,
    data_requirements: Path | None,
    explicit_properties: Path | None,
) -> Path | None:
    """Resolve JMeter runtime properties required by the data contract.

    Resolution rules:
    1. Explicit --properties always wins.
    2. If no JMETER_PROPERTY secrets are declared, properties remain optional.
    3. If secrets are required, automatically use
       data/<scenario>/secrets.properties when complete.
    4. Never expose secret values.
    5. Stop only when a required property is missing or empty.
    """

    if explicit_properties is not None:
        properties = (
            explicit_properties
            .expanduser()
            .resolve()
        )

        if not properties.is_file():
            raise WorkflowError(
                "JMeter properties file not found: "
                f"{properties}"
            )

        return properties

    if data_requirements is None:
        return None

    requirements_path = (
        data_requirements
        .expanduser()
        .resolve()
    )

    if not requirements_path.is_file():
        return None

    try:
        payload = json.loads(
            requirements_path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        raise WorkflowError(
            "Unable to read data requirements "
            f"for runtime property resolution: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise WorkflowError(
            "data-requirements.json root "
            "must be an object."
        )

    required_names = []

    for item in payload.get("secrets", []):
        if not isinstance(item, dict):
            continue

        if (
            str(
                item.get("source", "")
            ).upper()
            != "JMETER_PROPERTY"
        ):
            continue

        name = str(
            item.get("name", "")
        ).strip()

        if name:
            required_names.append(name)

    if not required_names:
        return None

    scenario = str(
        payload.get("scenario", "")
    ).strip()

    if not scenario:
        candidate = payload.get(
            "scenario_candidate"
        )

        if isinstance(candidate, dict):
            scenario = str(
                candidate.get("scenario", "")
                or candidate.get("name", "")
                or ""
            ).strip()

    if not scenario:
        raise WorkflowError(
            "JMETER_PROPERTY secrets are required "
            "but scenario identity could not be "
            "resolved from data-requirements.json."
        )

    properties = (
        project_root
        / "data"
        / scenario
        / "secrets.properties"
    ).resolve()

    if not properties.is_file():
        names = ", ".join(
            required_names
        )

        raise WorkflowError(
            "Runtime properties are required but "
            f"{properties} does not exist. "
            "Required JMeter properties: "
            f"{names}"
        )

    configured = {}

    try:
        for raw in properties.read_text(
            encoding="utf-8"
        ).splitlines():
            line = raw.strip()

            if (
                not line
                or line.startswith(("#", "!"))
                or "=" not in line
            ):
                continue

            key, value = line.split(
                "=",
                1,
            )

            configured[
                key.strip()
            ] = value.strip()

    except OSError as exc:
        raise WorkflowError(
            "Unable to read runtime properties "
            f"file: {exc}"
        ) from exc

    missing = [
        name
        for name in required_names
        if not configured.get(name)
    ]

    if missing:
        raise WorkflowError(
            "Runtime properties file exists but "
            "required JMeter properties are "
            "missing or empty: "
            + ", ".join(missing)
        )

    print(
        "Runtime properties : AUTO-RESOLVED"
    )
    print(
        f"Properties file    : {properties}"
    )
    print(
        "Required secrets   : "
        f"{len(required_names)} configured"
    )

    return properties



def build_controlled_command(
    args: argparse.Namespace,
    mode: str,
) -> list[str]:
    plan = require_file(
        resolve_path(args.plan),
        "Plan",
    )

    profile = require_file(
        resolve_path(args.profile),
        "Execution profile",
    )

    jmx = require_file(
        resolve_path(args.jmx),
        "JMX",
    )

    csv_path = resolve_path(
        args.csv
    )

    data_requirements = resolve_path(
        args.data_requirements
    )

    design_context = resolve_path(
        args.design_context
    )

    explicit_properties = resolve_path(
        args.properties
    )

    manifest = resolve_path(
        args.manifest
    )

    data_contract: dict[str, Any] | None = None

    if data_requirements is not None:
        require_file(
            data_requirements,
            "Data requirements",
        )

        try:
            data_contract = json.loads(
                data_requirements.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise WorkflowError(
                "Unable to read data requirements: "
                f"{exc}"
            ) from exc

        if not isinstance(
            data_contract,
            dict,
        ):
            raise WorkflowError(
                "data-requirements.json root "
                "must be an object."
            )

    if (
        csv_path is not None
        and not csv_path.is_file()
    ):
        strategy = ""

        fields: list[Any] = []

        if data_contract is not None:
            strategy = str(
                data_contract.get(
                    "strategy",
                    "",
                )
            ).strip().upper()

            raw_fields = (
                data_contract.get(
                    "fields",
                    [],
                )
            )

            if isinstance(
                raw_fields,
                list,
            ):
                fields = raw_fields

        # A caller may supply the conventional CSV path even
        # for a scenario that explicitly has no data file.
        # This is not a blocking condition.
        if (
            strategy == "NONE"
            and not fields
        ):
            print(
                "[INFO] CSV not required by "
                "data contract; optional --csv "
                "path will be ignored."
            )
            csv_path = None

        else:
            require_file(
                csv_path,
                "CSV",
            )

    if (
        csv_path is not None
        and data_requirements is None
    ):
        raise WorkflowError(
            "CSV requires --data-requirements."
        )

    if design_context is not None:
        require_file(
            design_context,
            "Design context",
        )

    if (
        design_context is not None
        and data_requirements is None
    ):
        raise WorkflowError(
            "Design context requires "
            "--data-requirements."
        )

    properties = resolve_runtime_properties(
        project_root=(
            Path(__file__)
            .resolve()
            .parents[1]
        ),
        data_requirements=(
            data_requirements
        ),
        explicit_properties=(
            explicit_properties
        ),
    )

    if properties is not None:
        require_file(
            properties,
            "JMeter properties",
        )

    # Preserve the existing fail-closed secret gate.
    if data_contract is not None:
        required_jmeter_properties = [
            item
            for item in data_contract.get(
                "secrets",
                [],
            )
            if (
                isinstance(item, dict)
                and str(
                    item.get(
                        "source",
                        "",
                    )
                ).upper()
                == "JMETER_PROPERTY"
            )
        ]

        if (
            required_jmeter_properties
            and properties is None
        ):
            names = ", ".join(
                str(
                    item.get(
                        "name",
                        "<UNKNOWN>",
                    )
                )
                for item
                in required_jmeter_properties
            )

            raise WorkflowError(
                "Execution requires --properties "
                "because the data contract declares "
                "JMETER_PROPERTY secrets: "
                f"{names}"
            )

    command = python_command(
        "run_approved_plan.py"
    )

    command.extend(
        [
            "--plan",
            str(plan),
            "--profile",
            str(profile),
            "--jmx",
            str(jmx),
        ]
    )

    add_optional_path(
        command,
        "--csv",
        csv_path,
    )

    add_optional_path(
        command,
        "--data-requirements",
        data_requirements,
    )

    add_optional_path(
        command,
        "--design-context",
        design_context,
    )

    add_optional_path(
        command,
        "--properties",
        properties,
    )

    add_optional_path(
        command,
        "--manifest",
        manifest,
    )

    if mode == "preflight":
        command.append(
            "--preflight"
        )

    elif mode == "execute":
        command.append(
            "--execute"
        )

    else:
        raise WorkflowError(
            f"Unsupported controlled mode: {mode}"
        )

    return command



def build_review_command(
    args: argparse.Namespace,
) -> list[str]:
    plan = resolve_path(args.plan)

    if plan is None:
        raise WorkflowError("--plan is required.")

    require_file(
        plan,
        "Plan",
    )

    return [
        *python_command(
            "review_test_plan.py"
        ),
        "--plan",
        str(plan),
        "--strict",
    ]


def build_approve_commands(
    args: argparse.Namespace,
) -> list[list[str]]:
    plan = resolve_path(args.plan)
    jmx = resolve_path(args.jmx)

    if plan is None:
        raise WorkflowError("--plan is required.")

    if jmx is None:
        raise WorkflowError("--jmx is required.")

    require_file(
        plan,
        "Plan",
    )

    require_file(
        jmx,
        "JMX",
    )

    approved_by = str(
        args.approved_by
        or ""
    ).strip()

    if not approved_by:
        raise WorkflowError(
            "--approved-by is required."
        )

    return [
        [
            *python_command(
                "approve_test_plan.py"
            ),
            "--plan",
            str(plan),
            "--approved-by",
            approved_by,
        ],
        [
            *python_command(
                "refresh_jmx_metadata.py"
            ),
            "--plan",
            str(plan),
            "--jmx",
            str(jmx),
        ],
        [
            *python_command(
                "validate_jmx_artifact.py"
            ),
            "--plan",
            str(plan),
            "--jmx",
            str(jmx),
        ],
    ]


def build_authorize_commands(
    args: argparse.Namespace,
) -> list[list[str]]:
    plan = resolve_path(args.plan)
    jmx = resolve_path(args.jmx)

    if plan is None:
        raise WorkflowError("--plan is required.")

    if jmx is None:
        raise WorkflowError("--jmx is required.")

    require_file(
        plan,
        "Plan",
    )

    require_file(
        jmx,
        "JMX",
    )

    authorized_by = str(
        args.authorized_by
        or ""
    ).strip()

    if not authorized_by:
        raise WorkflowError(
            "--authorized-by is required."
        )

    command = [
        *python_command(
            "authorize_execution.py"
        ),
        "--plan",
        str(plan),
        "--authorized-by",
        authorized_by,
    ]

    notes = str(
        args.notes
        or ""
    ).strip()

    if notes:
        command.extend(
            [
                "--notes",
                notes,
            ]
        )

    return [
        command,
        [
            *python_command(
                "refresh_jmx_metadata.py"
            ),
            "--plan",
            str(plan),
            "--jmx",
            str(jmx),
        ],
        [
            *python_command(
                "validate_jmx_artifact.py"
            ),
            "--plan",
            str(plan),
            "--jmx",
            str(jmx),
        ],
    ]


def run_commands(
    commands: list[list[str]],
) -> None:
    for command in commands:
        run_command(command)




def execution_directories(
    project_root: Path = ROOT,
) -> set[Path]:
    """Return current immutable execution-result directories."""
    results_dir = project_root / "results"

    if not results_dir.is_dir():
        return set()

    return {
        path.resolve()
        for path in results_dir.iterdir()
        if path.is_dir()
    }


def resolve_plan_scenario(
    plan_path: Path,
) -> str:
    """Resolve the governed scenario name without changing the plan."""
    import yaml

    try:
        payload = yaml.safe_load(
            plan_path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        yaml.YAMLError,
    ) as exc:
        raise WorkflowError(
            "Unable to resolve scenario from "
            f"test plan: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise WorkflowError(
            "Test plan must be a YAML object."
        )

    metadata = payload.get(
        "metadata",
        {},
    )

    if isinstance(metadata, dict):
        scenario = str(
            metadata.get(
                "name",
                "",
            )
        ).strip()

        if scenario:
            return scenario

    raise WorkflowError(
        "Unable to resolve metadata.name "
        "from test plan."
    )


def detect_new_execution_directory(
    *,
    project_root: Path,
    before: set[Path],
    started_at: float,
    scenario: str,
) -> Path | None:
    """Resolve the execution directory created by the just-finished run.

    Primary strategy is directory set-difference. A conservative timestamp
    fallback is used only when no new path is visible, for example when a
    filesystem observer races with the process exit.
    """
    after = execution_directories(
        project_root
    )

    created = [
        path
        for path in after - before
        if path.is_dir()
    ]

    if created:
        matching = [
            path
            for path in created
            if path.name.endswith(
                f"_{scenario}"
            )
        ]

        candidates = (
            matching
            if matching
            else created
        )

        return max(
            candidates,
            key=lambda path: (
                path.stat().st_mtime
            ),
        )

    results_dir = (
        project_root
        / "results"
    )

    if not results_dir.is_dir():
        return None

    fallback = []

    for path in results_dir.iterdir():
        if not path.is_dir():
            continue

        if not path.name.endswith(
            f"_{scenario}"
        ):
            continue

        try:
            modified = (
                path.stat().st_mtime
            )
        except OSError:
            continue

        if modified >= started_at - 2.0:
            fallback.append(path.resolve())

    if not fallback:
        return None

    return max(
        fallback,
        key=lambda path: (
            path.stat().st_mtime
        ),
    )


def professional_reporting_enabled() -> bool:
    """Allow emergency opt-out without changing the public CLI contract."""
    value = os.environ.get(
        "PERF_AUTO_PROFESSIONAL_REPORT",
        "1",
    ).strip().lower()

    return value not in {
        "0",
        "false",
        "no",
        "off",
    }


def generate_professional_report_bundle(
    *,
    project_root: Path,
    scenario: str,
    profile: Path,
    jmx: Path,
    execution_dir: Path,
) -> bool:
    """Generate the professional PDF/HTML enhancement after EXECUTE.

    This is intentionally post-execution and non-blocking. A report-generation
    defect must never invalidate deterministic JMeter evidence or change the
    PASS/FAIL verdict produced by the governed backend.
    """
    if not professional_reporting_enabled():
        print()
        print(
            "Professional report bundle : DISABLED"
        )
        return False

    builder = (
        project_root
        / ".gemini"
        / "skills"
        / "performance-report-interpreter"
        / "scripts"
        / "build_report_bundle.py"
    )

    report_dir = (
        project_root
        / "reports"
        / execution_dir.name
    )

    artifacts = {
        "builder": builder,
        "analysis": (
            execution_dir
            / "analysis.json"
        ),
        "intelligence": (
            execution_dir
            / "intelligence.json"
        ),
        "jtl": (
            execution_dir
            / "results.jtl"
        ),
        "html": (
            report_dir
            / "executive-report.html"
        ),
        "jmx": jmx,
        "profile": profile,
    }

    missing = [
        f"{name}: {path}"
        for name, path in artifacts.items()
        if not path.is_file()
    ]

    if missing:
        print()
        print("=" * 78)
        print(
            "PROFESSIONAL REPORT BUNDLE"
        )
        print("=" * 78)
        print("Status : SKIPPED")
        print(
            "Reason : required artifact "
            "is not available"
        )

        for item in missing:
            print(f"- {item}")

        print(
            "Deterministic execution evidence "
            "remains valid."
        )
        print("=" * 78)
        return False

    report_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        sys.executable,
        str(builder),
        "--analysis",
        str(artifacts["analysis"]),
        "--intelligence",
        str(
            artifacts["intelligence"]
        ),
        "--jtl",
        str(artifacts["jtl"]),
        "--jmx",
        str(jmx),
        "--workload",
        str(profile),
        "--output-dir",
        str(report_dir),
        "--scenario",
        scenario,
        "--html-report",
        str(artifacts["html"]),
    ]

    print()
    print("=" * 78)
    print(
        "PROFESSIONAL REPORT BUNDLE"
    )
    print("=" * 78)
    print(
        "Generating PDF, interpretation "
        "and HTML enhancements..."
    )

    try:
        completed = subprocess.run(
            command,
            cwd=project_root,
            check=False,
        )
    except OSError as exc:
        print("Status : FAILED")
        print(
            "Reason : unable to start "
            f"report generator: {exc}"
        )
        print(
            "Deterministic execution evidence "
            "remains valid."
        )
        print("=" * 78)
        return False

    if completed.returncode != 0:
        print("Status : FAILED")
        print(
            "Reason : report generator exited "
            f"with code {completed.returncode}"
        )
        print(
            "Deterministic execution evidence "
            "remains valid."
        )
        print("=" * 78)
        return False

    pdf = (
        report_dir
        / "executive-report.pdf"
    )
    interpretation = (
        report_dir
        / "interpretation.md"
    )
    evidence = (
        report_dir
        / "evidence.json"
    )

    generated = [
        path
        for path in (
            pdf,
            interpretation,
            evidence,
        )
        if path.is_file()
    ]

    print("Status : COMPLETE")

    for path in generated:
        print(
            f"{path.name:<24}: {path}"
        )

    if not pdf.is_file():
        print(
            "Warning: PDF was not produced. "
            "Execution result is unchanged."
        )

    print("=" * 78)
    return pdf.is_file()



def print_contract() -> None:
    payload = {
        "schema_version": "1.0",
        "public_entrypoint": (
            "scripts/performance_workflow.py"
        ),
        "operations": [
            "intake",
            "review",
            "approve",
            "authorize",
            "preflight",
            "execute",
            "contract",
        ],
        "delegates": {
            "intake": (
                "Postman -> scripts/prepare_postman_design.py; "
                "JMX/CLI -> scripts/performance_intake.py"
            ),
            "review": (
                "scripts/review_test_plan.py --strict"
            ),
            "approve": (
                "scripts/approve_test_plan.py + "
                "refresh_jmx_metadata.py"
            ),
            "authorize": (
                "scripts/authorize_execution.py + "
                "refresh_jmx_metadata.py"
            ),
            "preflight": (
                "scripts/run_approved_plan.py "
                "--preflight"
            ),
            "execute": (
                "scripts/run_approved_plan.py "
                "--execute"
            ),
        },
        "internal_only": [
            "scripts/run_test.py",
            "scripts/pre_execution_gate.py",
        ],
        "safety": {
            "workload_overrides": False,
            "authorization_bypass": False,
            "secret_values_logged": False,
            "jmeter_direct_execution": False,
        },
    }

    print(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Single user-facing orchestration entry point "
            "for the AI-Assisted Performance Engineering "
            "platform."
        )
    )

    subparsers = parser.add_subparsers(
        dest="operation",
        required=True,
    )

    intake = subparsers.add_parser(
        "intake",
        help=(
            "Prepare a performance design from Postman, "
            "or normalize and inspect JMX/CLI input."
        ),
    )

    intake.add_argument(
        "--input",
        type=Path,
    )

    intake.add_argument(
        "--environment",
        type=Path,
    )

    intake.add_argument(
        "--input-type",
        choices=(
            "postman",
            "jmx",
            "cli",
        ),
    )

    intake.add_argument(
        "--target",
    )

    intake.add_argument(
        "--method",
    )

    intake.add_argument(
        "--workspace",
        required=True,
        type=Path,
    )

    intake.add_argument(
        "--profile",
        type=Path,
        default=Path(
            "config/execution-profiles/baseline.yaml"
        ),
        help=(
            "Base execution profile. Workload values may be "
            "overridden only during design/intake."
        ),
    )

    intake.add_argument(
        "--users",
        type=int,
        help=(
            "Proposed virtual users for the design. "
            "Allowed only during intake."
        ),
    )

    intake.add_argument(
        "--duration-seconds",
        type=int,
        help=(
            "Proposed test duration in seconds. "
            "Allowed only during intake."
        ),
    )

    intake.add_argument(
        "--ramp-time-seconds",
        type=int,
        help=(
            "Proposed ramp-up in seconds. "
            "Allowed only during intake."
        ),
    )

    intake.add_argument(
        "--pacing-seconds",
        type=float,
        help=(
            "Proposed pacing between scenario iterations. "
            "Allowed only during intake."
        ),
    )

    review = subparsers.add_parser(
        "review",
        help=(
            "Run deterministic review gates "
            "for a generated performance test plan."
        ),
    )

    review.add_argument(
        "--plan",
        required=True,
        type=Path,
    )

    approve = subparsers.add_parser(
        "approve",
        help=(
            "Approve design/workload and refresh "
            "the governed JMX metadata."
        ),
    )

    approve.add_argument(
        "--plan",
        required=True,
        type=Path,
    )

    approve.add_argument(
        "--jmx",
        required=True,
        type=Path,
    )

    approve.add_argument(
        "--approved-by",
        required=True,
    )

    authorize = subparsers.add_parser(
        "authorize",
        help=(
            "Authorize controlled execution and "
            "refresh governed JMX metadata."
        ),
    )

    authorize.add_argument(
        "--plan",
        required=True,
        type=Path,
    )

    authorize.add_argument(
        "--jmx",
        required=True,
        type=Path,
    )

    authorize.add_argument(
        "--authorized-by",
        required=True,
    )

    authorize.add_argument(
        "--notes",
    )

    for name in (
        "preflight",
        "execute",
    ):
        command = subparsers.add_parser(
            name,
            help=(
                "Run the controlled governed execution "
                f"workflow in {name} mode."
            ),
        )

        command.add_argument(
            "--plan",
            required=True,
            type=Path,
        )

        command.add_argument(
            "--profile",
            required=True,
            type=Path,
        )

        command.add_argument(
            "--jmx",
            required=True,
            type=Path,
        )

        command.add_argument(
            "--csv",
            type=Path,
        )

        command.add_argument(
            "--data-requirements",
            type=Path,
        )

        command.add_argument(
            "--design-context",
            type=Path,
        )

        command.add_argument(
            "--properties",
            type=Path,
        )

        command.add_argument(
            "--manifest",
            type=Path,
        )

    subparsers.add_parser(
        "contract",
        help=(
            "Show the public orchestration contract "
            "without executing any operation."
        ),
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.operation == "contract":
            print_contract()
            return 0

        if args.operation == "intake":
            command = build_intake_command(
                args
            )
            run_command(
                command
            )

        elif args.operation == "review":
            command = build_review_command(
                args
            )
            run_command(
                command
            )

        elif args.operation == "approve":
            run_commands(
                build_approve_commands(
                    args
                )
            )

        elif args.operation == "authorize":
            run_commands(
                build_authorize_commands(
                    args
                )
            )

        elif args.operation in {
            "preflight",
            "execute",
        }:
            command = build_controlled_command(
                args,
                args.operation,
            )

            if args.operation == "execute":
                before_results = (
                    execution_directories(
                        ROOT
                    )
                )
                execute_started_at = (
                    time.time()
                )
                scenario = (
                    resolve_plan_scenario(
                        require_file(
                            resolve_path(
                                args.plan
                            ),
                            "Plan",
                        )
                    )
                )
            else:
                before_results = set()
                execute_started_at = 0.0
                scenario = ""

            run_command(
                command
            )

            if args.operation == "execute":
                execution_dir = (
                    detect_new_execution_directory(
                        project_root=ROOT,
                        before=before_results,
                        started_at=execute_started_at,
                        scenario=scenario,
                    )
                )

                if execution_dir is None:
                    print()
                    print("=" * 78)
                    print(
                        "PROFESSIONAL REPORT BUNDLE"
                    )
                    print("=" * 78)
                    print("Status : SKIPPED")
                    print(
                        "Reason : no new execution "
                        "directory was detected."
                    )
                    print(
                        "Deterministic execution "
                        "result is unchanged."
                    )
                    print("=" * 78)
                else:
                    profile = require_file(
                        resolve_path(
                            args.profile
                        ),
                        "Execution profile",
                    )
                    jmx = require_file(
                        resolve_path(
                            args.jmx
                        ),
                        "JMX",
                    )

                    generate_professional_report_bundle(
                        project_root=ROOT,
                        scenario=scenario,
                        profile=profile,
                        jmx=jmx,
                        execution_dir=execution_dir,
                    )

        else:
            raise WorkflowError(
                "Unknown workflow operation."
            )

        print()
        print("=" * 78)
        print("PERFORMANCE WORKFLOW")
        print("=" * 78)
        print(
            f"Operation : {args.operation.upper()}"
        )
        print("Status    : COMPLETE")
        print("=" * 78)

        return 0

    except (
        WorkflowError,
        OSError,
    ) as exc:
        print(
            f"PERFORMANCE WORKFLOW ERROR: {exc}",
            file=sys.stderr,
        )

        return 2


if __name__ == "__main__":
    raise SystemExit(main())
