#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


class DesignError(RuntimeError):
    pass


def run(command: list[str], stage: str) -> None:
    print()
    print("=" * 78)
    print(f"POSTMAN DESIGN STAGE: {stage}")
    print("=" * 78)

    result = subprocess.run(
        command,
        text=True,
    )

    if result.returncode != 0:
        raise DesignError(
            f"Stage failed: {stage}"
        )


def load_json(path: Path) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def slug(value: str) -> str:
    result = []

    for ch in value.lower():
        if ch.isalnum():
            result.append(ch)
        else:
            result.append("-")

    normalized = "".join(result)

    while "--" in normalized:
        normalized = normalized.replace(
            "--",
            "-",
        )

    return normalized.strip("-")


def choose_candidate(
    candidates_path: Path,
) -> dict:
    data = load_json(
        candidates_path
    )

    candidates = (
        data.get("candidates")
        or data.get("scenario_candidates")
        or []
    )

    if not candidates:
        raise DesignError(
            "No Postman scenario candidates found."
        )

    execution_ready = [
        c
        for c in candidates
        if (
            c.get("ready_for_execution") is True
            or c.get("type") == "E2E_CANDIDATE"
        )
    ]

    pool = (
        execution_ready
        if execution_ready
        else candidates
    )

    return pool[0]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare governed performance design artifacts "
            "from a normalized Postman intake."
        )
    )

    parser.add_argument(
        "--collection",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--environment",
        type=Path,
    )
    parser.add_argument(
        "--workspace",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--profile",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    root = (
        Path(__file__)
        .resolve()
        .parents[1]
    )

    workspace = (
        args.workspace
        .expanduser()
        .resolve()
    )

    collection = (
        args.collection
        .expanduser()
        .resolve()
    )

    environment = (
        args.environment
        .expanduser()
        .resolve()
        if args.environment
        else None
    )

    profile = (
        args.profile
        .expanduser()
        .resolve()
    )

    postman_dir = (
        workspace
        / "postman"
    )

    normalized = (
        postman_dir
        / "normalized-postman.json"
    )

    candidates = (
        postman_dir
        / "scenario-candidates.json"
    )

    # Bootstrap Postman intake automatically when the workspace
    # does not already contain normalized artifacts.
    if (
        not normalized.is_file()
        or not candidates.is_file()
    ):
        postman_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        pipeline_command = [
            sys.executable,
            str(
                root
                / "scripts"
                / "postman_pipeline.py"
            ),
            "--collection",
            str(collection),
            "--workspace",
            str(postman_dir),
        ]

        if environment is not None:
            pipeline_command.extend(
                [
                    "--environment",
                    str(environment),
                ]
            )

        run(
            pipeline_command,
            "POSTMAN_PIPELINE",
        )

    if not normalized.is_file():
        raise DesignError(
            f"Normalized Postman artifact missing "
            f"after POSTMAN_PIPELINE: {normalized}"
        )

    if not candidates.is_file():
        raise DesignError(
            f"Scenario candidates missing "
            f"after POSTMAN_PIPELINE: {candidates}"
        )

    candidate = choose_candidate(
        candidates
    )

    candidate_id = str(
        candidate.get("id")
        or candidate.get("name")
        or "postman-e2e"
    )

    scenario = slug(
        candidate_id.replace(
            "-candidate",
            "",
        )
    )

    if scenario.endswith("-e2e-e2e"):
        scenario = scenario[:-4]

    if not scenario:
        scenario = "postman-e2e"

    work_dir = (
        root
        / "work"
        / "postman"
        / scenario
    )

    data_dir = (
        root
        / "data"
        / scenario
    )

    plan_dir = (
        root
        / "tests"
        / "plans"
        / scenario
    )

    generated_dir = (
        root
        / "tests"
        / "generated"
    )

    for directory in (
        work_dir,
        data_dir,
        plan_dir,
        generated_dir,
    ):
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    correlations = (
        work_dir
        / "correlations.json"
    )

    model = (
        work_dir
        / "executable-model.json"
    )

    csv_path = (
        data_dir
        / "test-data.csv"
    )

    secrets_template = (
        data_dir
        / "secrets.properties.template"
    )

    jmx = (
        generated_dir
        / f"{scenario}.jmx"
    )

    run(
        [
            sys.executable,
            str(
                root
                / "scripts"
                / "resolve_postman_correlations.py"
            ),
            "--collection",
            str(collection),
            "--normalized",
            str(normalized),
            "--candidates",
            str(candidates),
            "--candidate-id",
            candidate_id,
            "--output",
            str(correlations),
        ],
        "RESOLVE_CORRELATIONS",
    )

    compile_command = [
        sys.executable,
        str(
            root
            / "scripts"
            / "compile_postman_scenario.py"
        ),
        "--collection",
        str(collection),
        "--candidates",
        str(candidates),
        "--correlations",
        str(correlations),
        "--candidate-id",
        candidate_id,
        "--output",
        str(model),
        "--csv",
        str(csv_path),
        "--secrets-template",
        str(secrets_template),
    ]

    if environment is not None:
        compile_command.extend(
            [
                "--environment",
                str(environment),
            ]
        )

    run(
        compile_command,
        "COMPILE_EXECUTABLE_MODEL",
    )

    run(
        [
            sys.executable,
            str(
                root
                / "scripts"
                / "generate_postman_test_plan.py"
            ),
            "--model",
            str(model),
            "--profile",
            str(profile),
            "--csv",
            str(csv_path),
            "--secrets-template",
            str(secrets_template),
            "--scenario",
            scenario,
            "--output-dir",
            str(plan_dir),
        ],
        "GENERATE_TEST_PLAN",
    )

    # JMX generation is deterministic from model/profile/data.
    run(
        [
            sys.executable,
            str(
                root
                / "scripts"
                / "generate_postman_jmx.py"
            ),
            "--model",
            str(model),
            "--profile",
            str(profile),
            "--csv",
            str(csv_path),
            "--output",
            str(jmx),
        ],
        "GENERATE_JMX",
    )

    run(
        [
            sys.executable,
            str(
                root
                / "scripts"
                / "validate_postman_jmx.py"
            ),
            "--model",
            str(model),
            "--jmx",
            str(jmx),
            "--csv",
            str(csv_path),
        ],
        "VALIDATE_JMX",
    )

    manifest = {
        "schema_version": "1.0",
        "status": "DESIGN_ARTIFACTS_READY",
        "scenario": scenario,
        "scenario_candidate": candidate,
        "artifacts": {
            "normalized": str(
                normalized
            ),
            "candidates": str(
                candidates
            ),
            "correlations": str(
                correlations
            ),
            "executable_model": str(
                model
            ),
            "csv": str(
                csv_path
            ),
            "secrets_template": str(
                secrets_template
            ),
            "jmx": str(
                jmx
            ),
            "plan_directory": str(
                plan_dir
            ),
        },
    }

    manifest_path = (
        workspace
        / "design-manifest.json"
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

    print()
    print("=" * 78)
    print("POSTMAN DESIGN PREPARATION COMPLETE")
    print("=" * 78)
    print(f"Scenario       : {scenario}")
    print(f"Candidate      : {candidate_id}")
    print(f"Model          : {model}")
    print(f"CSV            : {csv_path}")
    print(
        f"Secrets tmpl   : "
        f"{secrets_template}"
    )
    print(f"JMX            : {jmx}")
    print(f"Manifest       : {manifest_path}")
    print(
        "Status         : "
        "DESIGN_ARTIFACTS_READY"
    )
    print("=" * 78)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
