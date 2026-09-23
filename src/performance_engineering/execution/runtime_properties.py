from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class RuntimePropertiesError(RuntimeError):
    """Runtime properties contract cannot be satisfied."""


@dataclass(frozen=True)
class RuntimeProperties:
    scenario: str
    path: Path
    required_names: tuple[str, ...]


def _resolve_project_path(
    project_root: Path,
    value: str | Path,
) -> Path:
    path = Path(value).expanduser()

    if not path.is_absolute():
        path = (
            project_root
            / path
        )

    return path.resolve()


def _load_json(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        raise RuntimePropertiesError(
            "Unable to read runtime data contract: "
            f"{path}: {exc}"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimePropertiesError(
            "Runtime data contract must contain "
            f"a JSON object: {path}"
        )

    return payload


def _load_plan(
    plan_path: Path,
) -> dict[str, Any]:
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
        raise RuntimePropertiesError(
            "Unable to read performance plan: "
            f"{plan_path}: {exc}"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimePropertiesError(
            "Performance plan must contain "
            f"a YAML object: {plan_path}"
        )

    return payload


def data_requirements_path(
    *,
    project_root: Path,
    plan_path: Path,
    plan: dict[str, Any] | None = None,
) -> Path | None:
    payload = (
        plan
        if plan is not None
        else _load_plan(
            plan_path
        )
    )

    data = payload.get(
        "data"
    )

    if not isinstance(
        data,
        dict,
    ):
        return None

    value = str(
        data.get(
            "requirements_file",
            "",
        )
        or ""
    ).strip()

    if not value:
        return None

    return _resolve_project_path(
        project_root,
        value,
    )


def required_jmeter_properties(
    contract: dict[str, Any],
) -> tuple[str, ...]:
    names: list[str] = []

    secrets = contract.get(
        "secrets"
    )

    if not isinstance(
        secrets,
        list,
    ):
        return ()

    for item in secrets:
        if not isinstance(
            item,
            dict,
        ):
            continue

        source = str(
            item.get(
                "source",
                "",
            )
        ).strip().upper()

        if source != "JMETER_PROPERTY":
            continue

        name = str(
            item.get(
                "name",
                "",
            )
        ).strip()

        if (
            name
            and name not in names
        ):
            names.append(
                name
            )

    return tuple(
        names
    )


def _read_properties(
    path: Path,
) -> dict[str, str]:
    configured: dict[str, str] = {}

    try:
        lines = path.read_text(
            encoding="utf-8"
        ).splitlines()
    except OSError as exc:
        raise RuntimePropertiesError(
            "Unable to read JMeter runtime "
            f"properties file: {path}: {exc}"
        ) from exc

    for raw in lines:
        line = raw.strip()

        if (
            not line
            or line.startswith("#")
            or line.startswith("!")
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

    return configured


def resolve_jmeter_runtime_properties(
    *,
    project_root: Path,
    plan_path: Path,
    plan: dict[str, Any] | None = None,
) -> RuntimeProperties | None:
    project_root = (
        project_root
        .expanduser()
        .resolve()
    )

    plan_path = (
        plan_path
        .expanduser()
        .resolve()
    )

    payload = (
        plan
        if plan is not None
        else _load_plan(
            plan_path
        )
    )

    requirements = data_requirements_path(
        project_root=project_root,
        plan_path=plan_path,
        plan=payload,
    )

    if requirements is None:
        return None

    if not requirements.is_file():
        raise RuntimePropertiesError(
            "Data requirements file does not exist: "
            f"{requirements}"
        )

    contract = _load_json(
        requirements
    )

    required = required_jmeter_properties(
        contract
    )

    if not required:
        return None

    scenario = str(
        contract.get(
            "scenario",
            "",
        )
        or ""
    ).strip()

    if not scenario:
        metadata = payload.get(
            "metadata"
        )

        if isinstance(
            metadata,
            dict,
        ):
            scenario = str(
                metadata.get(
                    "name",
                    "",
                )
                or ""
            ).strip()

    if not scenario:
        raise RuntimePropertiesError(
            "Runtime properties are required but "
            "the canonical scenario could not be "
            "resolved from the generated contracts."
        )

    properties = (
        project_root
        / "data"
        / scenario
        / "secrets.properties"
    ).resolve()

    if not properties.is_file():
        raise RuntimePropertiesError(
            "Required JMeter runtime properties "
            "file does not exist: "
            f"{properties}. Required properties: "
            + ", ".join(
                required
            )
        )

    configured = _read_properties(
        properties
    )

    missing = [
        name
        for name in required
        if not configured.get(
            name,
            ""
        ).strip()
    ]

    if missing:
        raise RuntimePropertiesError(
            "Required JMeter runtime properties "
            "are missing or empty in "
            f"{properties}: "
            + ", ".join(
                missing
            )
        )

    return RuntimeProperties(
        scenario=scenario,
        path=properties,
        required_names=required,
    )
