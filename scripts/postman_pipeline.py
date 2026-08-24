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


class PipelineError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_stage(name: str, command: list[str], cwd: Path) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
    )

    stage = {
        "name": name,
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "status": "PASS" if result.returncode == 0 else "FAIL",
    }

    print()
    print("=" * 78)
    print(f"POSTMAN PIPELINE STAGE: {name}")
    print("=" * 78)
    if result.stdout.strip():
        print(result.stdout.rstrip())
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr)

    return stage


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PipelineError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PipelineError(
            f"Invalid JSON in {path}: line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(data, dict):
        raise PipelineError(f"JSON root must be an object: {path}")
    return data


def candidate_exists(path: Path, candidate_id: str) -> bool:
    data = load_json(path)
    candidates = data.get("candidates", [])
    return any(
        isinstance(item, dict) and item.get("id") == candidate_id
        for item in candidates
    )


def print_candidates(path: Path) -> None:
    data = load_json(path)
    candidates = data.get("candidates", [])

    print()
    print("=" * 78)
    print("POSTMAN SCENARIO CANDIDATES")
    print("=" * 78)

    for index, candidate in enumerate(candidates, 1):
        if not isinstance(candidate, dict):
            continue
        print(
            f"{index:02d}. {candidate.get('id')} | "
            f"{candidate.get('type')} | "
            f"{candidate.get('confidence')} | "
            f"requests={len(candidate.get('requests', []))} | "
            f"correlation={candidate.get('requires_correlation', False)}"
        )

    print("=" * 78)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the deterministic Postman intake pipeline: normalize, validate, "
            "discover candidates, validate candidates, and optionally prepare a "
            "minimal design context for one candidate."
        )
    )
    parser.add_argument("--collection", required=True)
    parser.add_argument("--environment")
    parser.add_argument("--candidate-id")
    parser.add_argument(
        "--workspace",
        default="work/postman",
        help="Directory for generated deterministic artifacts.",
    )
    parser.add_argument(
        "--require-execution-ready",
        action="store_true",
        help="Fail the final context validation unless it is execution-ready.",
    )
    args = parser.parse_args()

    project_root = Path.cwd().resolve()
    scripts = project_root / "scripts"

    required_scripts = [
        "parse_postman_collection.py",
        "validate_normalized_postman.py",
        "discover_postman_scenarios.py",
        "validate_scenario_candidates.py",
        "prepare_postman_design_context.py",
        "validate_postman_design_context.py",
    ]

    missing_scripts = [
        name for name in required_scripts if not (scripts / name).is_file()
    ]
    if missing_scripts:
        print(
            "POSTMAN PIPELINE ERROR: missing required scripts: "
            + ", ".join(missing_scripts),
            file=sys.stderr,
        )
        return 2

    collection = Path(args.collection).expanduser().resolve()
    environment = (
        Path(args.environment).expanduser().resolve()
        if args.environment
        else None
    )
    workspace = Path(args.workspace).expanduser()
    if not workspace.is_absolute():
        workspace = project_root / workspace
    workspace = workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    normalized = workspace / "normalized-postman.json"
    candidates = workspace / "scenario-candidates.json"
    design_context = workspace / "design-context.json"
    manifest = workspace / "pipeline-manifest.json"

    stages: list[dict[str, Any]] = []

    parse_command = [
        sys.executable,
        str(scripts / "parse_postman_collection.py"),
        "--collection",
        str(collection),
        "--output",
        str(normalized),
    ]
    if environment:
        parse_command += ["--environment", str(environment)]

    stages.append(run_stage("NORMALIZE", parse_command, project_root))
    if stages[-1]["returncode"] != 0:
        return 2

    stages.append(
        run_stage(
            "VALIDATE_NORMALIZED",
            [
                sys.executable,
                str(scripts / "validate_normalized_postman.py"),
                "--input",
                str(normalized),
            ],
            project_root,
        )
    )
    if stages[-1]["returncode"] != 0:
        return 2

    stages.append(
        run_stage(
            "DISCOVER_SCENARIOS",
            [
                sys.executable,
                str(scripts / "discover_postman_scenarios.py"),
                "--input",
                str(normalized),
                "--output",
                str(candidates),
            ],
            project_root,
        )
    )
    if stages[-1]["returncode"] != 0:
        return 2

    stages.append(
        run_stage(
            "VALIDATE_CANDIDATES",
            [
                sys.executable,
                str(scripts / "validate_scenario_candidates.py"),
                "--input",
                str(candidates),
            ],
            project_root,
        )
    )
    if stages[-1]["returncode"] != 0:
        return 2

    print_candidates(candidates)

    selected_candidate: str | None = None
    final_status = "DISCOVERY_READY"

    if args.candidate_id:
        selected_candidate = args.candidate_id
        if not candidate_exists(candidates, selected_candidate):
            print(
                f"POSTMAN PIPELINE ERROR: candidate not found: {selected_candidate}",
                file=sys.stderr,
            )
            return 2

        stages.append(
            run_stage(
                "PREPARE_DESIGN_CONTEXT",
                [
                    sys.executable,
                    str(scripts / "prepare_postman_design_context.py"),
                    "--normalized",
                    str(normalized),
                    "--candidates",
                    str(candidates),
                    "--candidate-id",
                    selected_candidate,
                    "--output",
                    str(design_context),
                ],
                project_root,
            )
        )
        if stages[-1]["returncode"] != 0:
            return 2

        validate_context_command = [
            sys.executable,
            str(scripts / "validate_postman_design_context.py"),
            "--input",
            str(design_context),
        ]
        if args.require_execution_ready:
            validate_context_command.append("--execution-ready")

        stages.append(
            run_stage(
                "VALIDATE_DESIGN_CONTEXT",
                validate_context_command,
                project_root,
            )
        )

        final_status = (
            "DESIGN_CONTEXT_READY"
            if stages[-1]["returncode"] == 0
            else "DESIGN_CONTEXT_BLOCKED"
        )

    manifest_data = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "source": {
            "collection": str(collection),
            "collection_sha256": sha256_file(collection),
            "environment": str(environment) if environment else None,
            "environment_sha256": sha256_file(environment)
            if environment
            else None,
        },
        "artifacts": {
            "normalized": str(normalized),
            "candidates": str(candidates),
            "design_context": str(design_context)
            if design_context.exists()
            else None,
        },
        "selected_candidate": selected_candidate,
        "stages": [
            {
                "name": stage["name"],
                "status": stage["status"],
                "returncode": stage["returncode"],
            }
            for stage in stages
        ],
        "final_status": final_status,
    }

    manifest.write_text(
        json.dumps(manifest_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 78)
    print("POSTMAN INTAKE PIPELINE SUMMARY")
    print("=" * 78)
    print(f"Collection        : {collection}")
    print(f"Environment       : {environment or 'NOT PROVIDED'}")
    print(f"Workspace         : {workspace}")
    print(f"Selected candidate: {selected_candidate or 'NONE'}")
    print(f"Final status      : {final_status}")
    print(f"Manifest          : {manifest}")
    print("=" * 78)

    if args.candidate_id and stages[-1]["returncode"] != 0:
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
