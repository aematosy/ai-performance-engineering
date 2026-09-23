from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from performance_engineering.domain.engine import PerformanceEngine


def _load_json_object(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8",
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        raise RuntimeError(
            f"Unable to read performance model: {path}"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            f"Performance model must be a JSON object: {path}"
        )

    return payload


def _resolve_executable_model(
    model_path: Path,
) -> Path:
    """
    Resolve the canonical executable model without depending on
    scenario names, endpoints or input source type.

    A model that already exposes top-level requests is executable.

    Otherwise resolution uses governed design metadata first and the
    canonical workspace executable model second.
    """

    model_path = model_path.resolve()

    if not model_path.is_file():
        raise RuntimeError(
            f"Performance model not found: {model_path}"
        )

    payload = _load_json_object(
        model_path
    )

    requests = payload.get(
        "requests",
    )

    if (
        isinstance(
            requests,
            list,
        )
        and requests
    ):
        return model_path

    workspace = model_path.parent

    manifest_candidates = [
        workspace / "design-manifest.json",
        workspace / "intake-manifest.json",
    ]

    for manifest_path in manifest_candidates:
        if not manifest_path.is_file():
            continue

        manifest = _load_json_object(
            manifest_path
        )

        artifacts = manifest.get(
            "artifacts",
            {},
        )

        if not isinstance(
            artifacts,
            dict,
        ):
            artifacts = {}

        candidate_value = (
            artifacts.get(
                "executable_model"
            )
            or manifest.get(
                "executable_model"
            )
        )

        if not candidate_value:
            continue

        candidate = Path(
            str(candidate_value)
        ).expanduser()

        if not candidate.is_absolute():
            candidate = (
                manifest_path.parent
                / candidate
            )

        candidate = candidate.resolve()

        if not candidate.is_file():
            continue

        executable = _load_json_object(
            candidate
        )

        executable_requests = executable.get(
            "requests",
        )

        if (
            isinstance(
                executable_requests,
                list,
            )
            and executable_requests
        ):
            return candidate

    canonical_candidate = (
        workspace
        / "executable-model.json"
    ).resolve()

    if canonical_candidate.is_file():
        executable = _load_json_object(
            canonical_candidate
        )

        executable_requests = executable.get(
            "requests",
        )

        if (
            isinstance(
                executable_requests,
                list,
            )
            and executable_requests
        ):
            return canonical_candidate

    raise RuntimeError(
        "No executable performance model with requests "
        f"could be resolved from design model: {model_path}"
    )


class JMeterEngine(PerformanceEngine):
    """JMeter implementation of the performance-engine contract."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.scripts_dir = self.project_root / "scripts"

    @property
    def name(self) -> str:
        return "jmeter"

    def _run(
        self,
        command: list[str],
        *,
        env: dict[str, str] | None = None,
        allowed_returncodes: tuple[int, ...] = (0,),
    ) -> None:
        completed = subprocess.run(
            command,
            cwd=self.project_root,
            check=False,
            env=env,
        )

        if completed.returncode not in allowed_returncodes:
            raise RuntimeError(
                "JMeter engine command failed "
                f"with exit code {completed.returncode}: "
                + " ".join(command)
            )

    def generate(
        self,
        model: dict[str, Any],
        profile: dict[str, Any],
        output: Path,
    ) -> Path:
        design_model_path = Path(
            model["artifact_path"]
        ).resolve()

        model_path = _resolve_executable_model(
            design_model_path
        )

        profile_path = Path(
            profile["artifact_path"]
        ).resolve()

        output = output.resolve()

        self._run(
            [
                sys.executable,
                str(
                    self.scripts_dir
                    / "generate_postman_jmx.py"
                ),
                "--model",
                str(model_path),
                "--profile",
                str(profile_path),
                "--output",
                str(output),
            ]
        )

        if not output.is_file():
            raise RuntimeError(
                f"JMeter artifact was not generated: {output}"
            )

        return output

    def validate(
        self,
        artifact: Path,
        context: dict[str, Any],
    ) -> None:
        artifact = artifact.resolve()

        plan = Path(
            context["plan"]
        ).resolve()

        metadata_path = Path(
            str(artifact) + ".meta.json"
        )

        if not metadata_path.is_file():
            self._run(
                [
                    sys.executable,
                    str(
                        self.scripts_dir
                        / "refresh_jmx_metadata.py"
                    ),
                    "--plan",
                    str(plan),
                    "--jmx",
                    str(artifact),
                ]
            )

        self._run(
            [
                sys.executable,
                str(
                    self.scripts_dir
                    / "validate_jmx_artifact.py"
                ),
                "--plan",
                str(plan),
                "--jmx",
                str(artifact),
            ]
        )

    def execute(
        self,
        artifact: Path,
        context: dict[str, Any],
    ) -> Path:
        artifact = artifact.resolve()

        runner = Path(
            context["runner"]
        ).resolve()

        results_root = Path(
            context["results_root"]
        ).resolve()

        results_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        before = {
            item.resolve()
            for item in results_root.iterdir()
            if item.is_dir()
        }

        command = [
            sys.executable,
            str(runner),
        ]

        command.extend(
            context.get(
                "arguments",
                [],
            )
        )

        env = os.environ.copy()

        runtime_properties = str(
            context.get(
                "runtime_properties",
                "",
            )
            or ""
        ).strip()

        if runtime_properties:
            env[
                "PERF_JMETER_PROPERTIES_FILE"
            ] = runtime_properties

        # run_test.py exit semantics:
        #   0 = execution completed, SLA PASS
        #   1 = execution completed, SLA FAIL
        #   2 = technical/configuration/evidence failure
        # 130 = interrupted
        #
        # SLA FAIL is a business/performance verdict, not an engine
        # execution failure. Only the execution handoff accepts 0/1.
        # Generation and validation remain strict and accept only 0.
        self._run(
            command,
            env=env,
            allowed_returncodes=(0, 1),
        )

        after = {
            item.resolve()
            for item in results_root.iterdir()
            if item.is_dir()
        }

        created = sorted(
            after - before,
            key=lambda item: (
                item.stat().st_mtime_ns,
                str(item),
            ),
        )

        if not created:
            explicit = context.get(
                "execution_dir"
            )

            if explicit:
                execution_dir = Path(
                    explicit
                ).resolve()

                if execution_dir.is_dir():
                    return execution_dir

            raise RuntimeError(
                "JMeter execution completed but no new "
                "execution directory was detected under: "
                f"{results_root}"
            )

        if len(created) > 1:
            raise RuntimeError(
                "JMeter execution produced multiple candidate "
                "execution directories; cannot determine the "
                "governed result deterministically: "
                + ", ".join(
                    str(item)
                    for item in created
                )
            )

        return created[0]
