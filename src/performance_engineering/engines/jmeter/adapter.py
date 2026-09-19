from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from performance_engineering.domain.engine import PerformanceEngine


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
    ) -> None:
        completed = subprocess.run(
            command,
            cwd=self.project_root,
            check=False,
        )

        if completed.returncode != 0:
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
        model_path = Path(
            model["artifact_path"]
        ).resolve()

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

        self._run(command)

        execution_dir = Path(
            context["execution_dir"]
        ).resolve()

        if not execution_dir.exists():
            raise RuntimeError(
                "JMeter execution completed but the "
                "expected execution directory does not exist: "
                f"{execution_dir}"
            )

        return execution_dir
