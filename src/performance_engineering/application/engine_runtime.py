from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from performance_engineering.domain.engine import (
    PerformanceEngine,
)
from performance_engineering.engines.jmeter.adapter import (
    JMeterEngine,
)
from performance_engineering.engines.locust.adapter import (
    LocustEngine,
)


class EngineResolutionError(ValueError):
    """Raised when a performance engine cannot be resolved."""


SUPPORTED_ENGINES = (
    "jmeter",
    "locust",
)


def normalize_engine_name(
    value: Any,
) -> str:
    if value is None:
        raise EngineResolutionError(
            "Performance engine is required. "
            "Expected one of: "
            + ", ".join(SUPPORTED_ENGINES)
            + "."
        )

    name = str(value).strip().lower()

    if name not in SUPPORTED_ENGINES:
        raise EngineResolutionError(
            f"Unsupported performance engine: {value!r}. "
            "Expected one of: "
            + ", ".join(SUPPORTED_ENGINES)
            + "."
        )

    return name


def resolve_engine(
    *,
    project_root: Path,
    engine_name: str,
) -> PerformanceEngine:
    name = normalize_engine_name(
        engine_name
    )

    root = project_root.resolve()

    if name == "jmeter":
        return JMeterEngine(root)

    if name == "locust":
        return LocustEngine(root)

    raise EngineResolutionError(
        f"Unsupported performance engine: {name}"
    )


def read_engine_from_profile(
    profile_path: Path,
) -> str:
    profile_path = profile_path.resolve()

    if not profile_path.is_file():
        raise EngineResolutionError(
            "Execution profile not found: "
            f"{profile_path}"
        )

    payload = yaml.safe_load(
        profile_path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise EngineResolutionError(
            "Execution profile must be a YAML object."
        )

    value = payload.get(
        "engine"
    )

    if value is None:
        execution = payload.get(
            "execution"
        )

        if isinstance(
            execution,
            dict,
        ):
            value = execution.get(
                "engine"
            )

    return normalize_engine_name(
        value
    )


def persist_engine_in_profile(
    *,
    profile_path: Path,
    engine_name: str,
    allow_change: bool = False,
) -> Path:
    """
    Persist engine provenance without modifying workload values.

    Canonical location:
        engine: jmeter | locust

    Existing execution parameters remain unchanged.
    """
    profile_path = profile_path.resolve()

    if not profile_path.is_file():
        raise EngineResolutionError(
            "Execution profile not found: "
            f"{profile_path}"
        )

    name = normalize_engine_name(
        engine_name
    )

    payload = yaml.safe_load(
        profile_path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise EngineResolutionError(
            "Execution profile must be a YAML object."
        )

    existing = payload.get(
        "engine"
    )

    if existing is not None:
        existing_name = (
            normalize_engine_name(
                existing
            )
        )

        if existing_name != name:
            if not allow_change:
                raise EngineResolutionError(
                    "Execution profile already declares "
                    f"engine={existing_name!r}; "
                    f"requested={name!r}. "
                    "An explicit governed engine change is required."
                )

            payload["engine"] = name

            profile_path.write_text(
                yaml.safe_dump(
                    payload,
                    sort_keys=False,
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )

            return profile_path

        return profile_path

    payload["engine"] = name

    profile_path.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    return profile_path
