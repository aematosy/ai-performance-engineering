#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


class IntakeError(RuntimeError):
    pass


SUPPORTED_HTTP_METHODS = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
}


def run_command(
    command: list[str],
    stage: str,
) -> None:
    print()
    print("=" * 78)
    print(f"PERFORMANCE INTAKE STAGE: {stage}")
    print("=" * 78)

    result = subprocess.run(
        command,
        text=True,
    )

    if result.returncode != 0:
        raise IntakeError(
            f"Stage failed: {stage}"
        )


def detect_type(
    input_path: Path | None,
    forced: str | None,
) -> str:
    if forced:
        forced_upper = forced.strip().upper()

        if forced_upper not in {
            "POSTMAN",
            "JMX",
            "CLI",
        }:
            raise IntakeError(
                f"Unsupported input type: {forced}"
            )

        return forced_upper

    if input_path is None:
        return "CLI"

    lower = input_path.name.lower()

    if lower.endswith(
        ".postman_collection.json"
    ):
        return "POSTMAN"

    if lower.endswith(".jmx"):
        return "JMX"

    # Generic CLI artifacts.
    if input_path.suffix.lower() in {
        ".curl",
        ".json",
        ".yaml",
        ".yml",
    }:
        return "CLI"

    raise IntakeError(
        "Unable to detect input type. "
        "Supported inputs are Postman collections, "
        "JMX, .curl, structured JSON/YAML, "
        "or explicit CLI --target."
    )


def require_input_file(
    path: Path | None,
    description: str,
) -> Path:
    if path is None:
        raise IntakeError(
            f"{description} requires --input."
        )

    if not path.is_file():
        raise IntakeError(
            f"Input file not found: {path}"
        )

    return path


def normalize_http_method(
    value: str | None,
) -> str:
    method = (
        value
        or "GET"
    ).strip().upper()

    if method not in SUPPORTED_HTTP_METHODS:
        raise IntakeError(
            "Unsupported CLI HTTP method: "
            f"{method}"
        )

    return method


def validate_literal_target(
    value: str,
) -> str:
    target = value.strip()

    if not target:
        raise IntakeError(
            "CLI target cannot be empty."
        )

    # Protect against Markdown links accidentally being passed
    # by assistants or copied from rendered output.
    if (
        target.startswith("[")
        or "](" in target
        or "\n" in target
        or "\r" in target
    ):
        raise IntakeError(
            "CLI target must be a literal HTTP/HTTPS URL, "
            "not Markdown or formatted text."
        )

    if not (
        target.startswith("http://")
        or target.startswith("https://")
    ):
        raise IntakeError(
            "CLI target must use http:// or https://."
        )

    return target


def write_single_target_model(
    *,
    normalized: Path,
    target: str,
    method: str,
) -> None:
    model = {
        "schema_version": "1.0",
        "source": {
            "type": "CLI",
            "artifact": None,
            "format": "LEGACY_SINGLE_TARGET",
        },
        "system": {
            "type": "API",
        },
        "scenarios": [
            {
                "name": "cli-scenario",
                "transactions": [
                    {
                        "name": (
                            f"{method} {target}"
                        ),
                        "method": method,
                        "target": target,
                    }
                ],
            }
        ],
        "data": {
            "strategy": "NONE_OR_PARAMETERIZED",
            "csv_data_sets": [],
            "parameters": [],
        },
        "runtime": {
            "correlations": [],
        },
        "workload": {
            "source": "EXECUTION_PROFILE",
            "thread_groups": [],
        },
        "assertions": [],
        "observability": [],
        "risks": [],
        "findings": [],
        "summary": {
            "transaction_count": 1,
        },
    }

    normalized.write_text(
        json.dumps(
            model,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Unified performance intake entry point "
            "for Postman, JMX, cURL, structured CLI, "
            "or explicit URL inputs."
        )
    )

    parser.add_argument("--input")
    parser.add_argument("--environment")

    parser.add_argument(
        "--input-type",
        choices=[
            "postman",
            "jmx",
            "cli",
        ],
    )

    parser.add_argument("--target")
    parser.add_argument("--method")

    parser.add_argument(
        "--workspace",
        required=True,
    )

    args = parser.parse_args()

    workspace = (
        Path(args.workspace)
        .expanduser()
        .resolve()
    )

    workspace.mkdir(
        parents=True,
        exist_ok=True,
    )

    input_path = (
        Path(args.input)
        .expanduser()
        .resolve()
        if args.input
        else None
    )

    try:
        input_type = detect_type(
            input_path,
            args.input_type,
        )

        # ============================================================
        # JMX
        # ============================================================

        if input_type == "JMX":
            input_path = require_input_file(
                input_path,
                "JMX intake",
            )

            normalized = (
                workspace
                / "normalized-performance-model.json"
            )

            run_command(
                [
                    sys.executable,
                    "scripts/parse_jmx.py",
                    "--jmx",
                    str(input_path),
                    "--output",
                    str(normalized),
                ],
                "PARSE_JMX",
            )

            run_command(
                [
                    sys.executable,
                    "scripts/validate_normalized_performance_model.py",
                    "--input",
                    str(normalized),
                ],
                "VALIDATE_MODEL",
            )

        # ============================================================
        # POSTMAN
        # ============================================================

        elif input_type == "POSTMAN":
            input_path = require_input_file(
                input_path,
                "Postman intake",
            )

            command = [
                sys.executable,
                "scripts/postman_pipeline.py",
                "--collection",
                str(input_path),
                "--workspace",
                str(
                    workspace
                    / "postman"
                ),
            ]

            if args.environment:
                environment_path = (
                    Path(args.environment)
                    .expanduser()
                    .resolve()
                )

                if not environment_path.is_file():
                    raise IntakeError(
                        "Postman environment not found: "
                        f"{environment_path}"
                    )

                command.extend(
                    [
                        "--environment",
                        str(environment_path),
                    ]
                )

            run_command(
                command,
                "POSTMAN_PIPELINE",
            )

            normalized = (
                workspace
                / "postman"
                / "normalized-postman.json"
            )

            if not normalized.is_file():
                raise IntakeError(
                    "Postman pipeline did not generate "
                    f"the normalized artifact: {normalized}"
                )

        # ============================================================
        # CLI
        # ============================================================

        else:
            normalized = (
                workspace
                / "normalized-performance-model.json"
            )

            # --------------------------------------------------------
            # CLI FILE INPUT
            # --------------------------------------------------------

            if input_path is not None:
                input_path = require_input_file(
                    input_path,
                    "CLI intake",
                )

                suffix = (
                    input_path
                    .suffix
                    .lower()
                )

                # Structured generic API scenario.
                if suffix in {
                    ".json",
                    ".yaml",
                    ".yml",
                }:
                    run_command(
                        [
                            sys.executable,
                            "scripts/parse_cli_scenario.py",
                            "--input",
                            str(input_path),
                            "--output",
                            str(normalized),
                        ],
                        "PARSE_STRUCTURED_CLI",
                    )

                # First-class cURL request.
                elif suffix == ".curl":
                    run_command(
                        [
                            sys.executable,
                            "scripts/parse_curl_request.py",
                            "--input",
                            str(input_path),
                            "--output",
                            str(normalized),
                            "--scenario",
                            workspace.name,
                        ],
                        "PARSE_CURL",
                    )

                # Do NOT accept arbitrary lists or text.
                else:
                    raise IntakeError(
                        "CLI file input is ambiguous. "
                        "Supported CLI file formats are "
                        ".curl, .json, .yaml and .yml. "
                        "Use --target with optional --method "
                        "for a single URL-only transaction."
                    )

            # --------------------------------------------------------
            # SINGLE URL CLI INPUT
            # --------------------------------------------------------

            else:
                if not args.target:
                    raise IntakeError(
                        "CLI intake requires either "
                        "a .curl file, a structured "
                        ".json/.yaml/.yml scenario, "
                        "or --target for a single transaction."
                    )

                target = validate_literal_target(
                    args.target
                )

                method = normalize_http_method(
                    args.method
                )

                write_single_target_model(
                    normalized=normalized,
                    target=target,
                    method=method,
                )

            # Every CLI representation must end in the same
            # normalized contract.
            run_command(
                [
                    sys.executable,
                    "scripts/validate_normalized_performance_model.py",
                    "--input",
                    str(normalized),
                ],
                "VALIDATE_MODEL",
            )

        # ============================================================
        # COMMON MANIFEST
        # ============================================================

        manifest = {
            "schema_version": "1.0",
            "input_type": input_type,
            "input": (
                str(input_path)
                if input_path
                else None
            ),
            "environment": (
                str(
                    Path(args.environment)
                    .expanduser()
                    .resolve()
                )
                if args.environment
                else None
            ),
            "workspace": str(
                workspace
            ),
            "normalized_artifact": str(
                normalized
            ),
            "status": "INTAKE_READY",
        }

        manifest_path = (
            workspace
            / "intake-manifest.json"
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

    except IntakeError as exc:
        print(
            f"PERFORMANCE INTAKE ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print()
    print("=" * 78)
    print("PERFORMANCE INTAKE SUMMARY")
    print("=" * 78)
    print(
        f"Input type : {input_type}"
    )
    print(
        f"Workspace  : {workspace}"
    )
    print(
        f"Normalized : {normalized}"
    )
    print(
        f"Manifest   : {manifest_path}"
    )
    print(
        "Status     : INTAKE_READY"
    )
    print("=" * 78)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
