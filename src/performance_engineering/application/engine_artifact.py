from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from performance_engineering.application.engine_runtime import (
    read_engine_from_profile,
    resolve_engine,
)


class EngineArtifactError(RuntimeError):
    """Raised when an executable engine artifact cannot be prepared."""


def scenario_name_from_model(
    model_path: Path,
) -> str:
    payload = json.loads(
        model_path.read_text(
            encoding="utf-8"
        )
    )

    executable_requests = payload.get(
        "requests"
    )

    scenario_candidate = payload.get(
        "scenario_candidate"
    )

    if (
        isinstance(
            executable_requests,
            list,
        )
        and executable_requests
        and isinstance(
            scenario_candidate,
            dict,
        )
    ):
        canonical = (
            model_path
            .resolve()
            .parent
            .name
            .strip()
        )

        if not canonical:
            raise EngineArtifactError(
                "Executable model has no canonical "
                "scenario directory."
            )

        return canonical

    scenarios = payload.get(
        "scenarios",
        []
    )

    if len(scenarios) != 1:
        raise EngineArtifactError(
            "Engine preparation requires exactly one normalized scenario."
        )

    scenario = scenarios[0]

    candidate = (
        scenario.get("name")
        or scenario.get("id")
    )

    if not candidate:
        raise EngineArtifactError(
            "Normalized scenario has no name/id."
        )

    return str(candidate)


def default_artifact_path(
    *,
    project_root: Path,
    engine_name: str,
    scenario: str,
) -> Path:
    if engine_name == "jmeter":
        return (
            project_root
            / "tests"
            / "generated"
            / f"{scenario}.jmx"
        )

    if engine_name == "locust":
        return (
            project_root
            / "tests"
            / "generated"
            / "locust"
            / scenario
            / "locustfile.py"
        )

    raise EngineArtifactError(
        f"Unsupported engine: {engine_name}"
    )


def prepare_engine_artifact(
    *,
    project_root: Path,
    model_path: Path,
    profile_path: Path,
    output_path: Path | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()

    model_path = (
        model_path
        .expanduser()
        .resolve()
    )

    profile_path = (
        profile_path
        .expanduser()
        .resolve()
    )

    if not model_path.is_file():
        raise EngineArtifactError(
            f"Normalized model not found: {model_path}"
        )

    if not profile_path.is_file():
        raise EngineArtifactError(
            f"Execution profile not found: {profile_path}"
        )

    engine_name = (
        read_engine_from_profile(
            profile_path
        )
    )

    scenario = (
        scenario_name_from_model(
            model_path
        )
    )

    artifact = (
        output_path.resolve()
        if output_path is not None
        else default_artifact_path(
            project_root=root,
            engine_name=engine_name,
            scenario=scenario,
        )
    )

    artifact.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    engine = resolve_engine(
        project_root=root,
        engine_name=engine_name,
    )

    generated = engine.generate(
        model={
            "artifact_path":
                model_path,
        },
        profile={
            "artifact_path":
                profile_path,
        },
        output=artifact,
    )

    validation_context: dict[str, Any] = {
        "profile": str(profile_path),
    }

    governed_plan = (
        root
        / "tests"
        / "plans"
        / scenario
        / "test-plan.yaml"
    ).resolve()

    if governed_plan.is_file():
        validation_context["plan"] = str(
            governed_plan
        )

    engine.validate(
        generated,
        validation_context,
    )

    return {
        "engine": engine_name,
        "scenario": scenario,
        "artifact":
            str(generated.resolve()),
        "model":
            str(model_path),
        "profile":
            str(profile_path),
        "status": "VALID",
    }
