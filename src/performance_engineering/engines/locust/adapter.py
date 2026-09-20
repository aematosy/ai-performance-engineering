from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from performance_engineering.domain.engine import PerformanceEngine


class LocustEngine(PerformanceEngine):
    """Locust implementation of the performance-engine contract."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    @property
    def name(self) -> str:
        return "locust"

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        return json.loads(
            path.read_text(encoding="utf-8")
        )

    @staticmethod
    def _expected_statuses(
        transaction: dict[str, Any],
    ) -> list[int]:
        value = transaction.get(
            "expected_status"
        )

        if value is None:
            raise ValueError(
                "Locust execution requires an explicit "
                "expected_status contract."
            )

        if (
            isinstance(value, str)
            and value.strip().upper() == "UNRESOLVED"
        ):
            raise ValueError(
                "Locust execution cannot be generated while "
                "expected_status is UNRESOLVED."
            )

        if (
            isinstance(value, str)
            and value.strip().upper() == "UNRESOLVED"
        ):
            raise ValueError(
                "Locust execution cannot be generated while "
                "expected_status is UNRESOLVED."
            )

        if isinstance(value, int):
            values = [value]

        elif isinstance(value, (list, tuple)):
            if not value:
                raise ValueError(
                    "expected_status must not be empty."
                )

            values = [
                int(item)
                for item in value
            ]

        else:
            values = [int(value)]

        for status in values:
            if not 100 <= status <= 599:
                raise ValueError(
                    f"HTTP status outside valid range: {status}"
                )

        return values

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

        normalized = self._load_json(
            model_path
        )

        profile_payload = yaml.safe_load(
            profile_path.read_text(
                encoding="utf-8"
            )
        )

        scenarios = normalized.get(
            "scenarios",
            [],
        )

        if len(scenarios) != 1:
            raise RuntimeError(
                "Locust POC currently requires "
                "exactly one scenario."
            )

        scenario = scenarios[0]

        correlations = (
            scenario.get("correlations")
            or normalized.get("correlations")
            or []
        )

        if correlations:
            raise RuntimeError(
                "Locust POC does not yet support "
                "runtime correlations."
            )

        transactions = scenario.get(
            "transactions",
            [],
        )

        if not transactions:
            raise RuntimeError(
                "Scenario contains no transactions."
            )

        system = normalized.get(
            "system",
            {},
        )

        base_url = (
            system.get("base_url")
            or system.get("target")
        )

        if not base_url:
            target = transactions[0].get(
                "target",
                ""
            )
            parsed = urlparse(target)
            base_url = (
                f"{parsed.scheme}://{parsed.netloc}"
            )

        execution = profile_payload.get(
            "execution",
            {},
        )

        pacing = float(
            execution.get(
                "pacing_seconds",
                1.0,
            )
        )

        runtime_transactions = []

        for transaction in transactions:
            target = transaction.get(
                "target",
                ""
            )

            path = transaction.get(
                "path"
            )

            if not path and target:
                parsed = urlparse(target)
                path = parsed.path or "/"

                if parsed.query:
                    path += "?" + parsed.query

            runtime_transactions.append(
                {
                    "name": transaction.get(
                        "name",
                        f"{transaction.get('method', 'GET')} "
                        f"{path}",
                    ),
                    "method": transaction.get(
                        "method",
                        "GET",
                    ).upper(),
                    "path": path or "/",
                    "headers": transaction.get(
                        "headers",
                        {},
                    ),
                    "body": transaction.get(
                        "body",
                    ),
                    "expected_status": (
                        self._expected_statuses(
                            transaction
                        )
                    ),
                }
            )

        payload = json.dumps(
            runtime_transactions,
            indent=4,
        )

        source = f'''from locust import HttpUser, task, constant_pacing

TRANSACTIONS = {payload}


class PerformanceUser(HttpUser):
    host = {base_url!r}
    wait_time = constant_pacing({pacing!r})

    @task
    def execute_scenario(self):
        for transaction in TRANSACTIONS:
            kwargs = {{
                "method": transaction["method"],
                "url": transaction["path"],
                "headers": transaction.get("headers") or {{}},
                "name": transaction["name"],
                "catch_response": True,
            }}

            body = transaction.get("body")

            if isinstance(body, (dict, list)):
                kwargs["json"] = body
            elif body is not None:
                kwargs["data"] = str(body)

            with self.client.request(**kwargs) as response:
                expected = transaction["expected_status"]

                if response.status_code not in expected:
                    response.failure(
                        f"Expected {{expected}}, "
                        f"received {{response.status_code}}"
                    )
'''

        output = output.resolve()
        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output.write_text(
            source,
            encoding="utf-8",
        )

        return output

    def validate(
        self,
        artifact: Path,
        context: dict[str, Any],
    ) -> None:
        artifact = artifact.resolve()

        if not artifact.is_file():
            raise RuntimeError(
                f"Locust artifact not found: {artifact}"
            )

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "py_compile",
                str(artifact),
            ],
            cwd=self.project_root,
            check=False,
        )

        if completed.returncode != 0:
            raise RuntimeError(
                "Generated Locust artifact "
                "is not valid Python."
            )

    def execute(
        self,
        artifact: Path,
        context: dict[str, Any],
    ) -> Path:
        profile_path = Path(
            context["profile"]
        ).resolve()

        execution_dir = Path(
            context["execution_dir"]
        ).resolve()

        profile = yaml.safe_load(
            profile_path.read_text(
                encoding="utf-8"
            )
        )

        execution = profile["execution"]

        users = int(
            execution["threads"]
        )
        ramp = int(
            execution["ramp_time_seconds"]
        )
        duration = int(
            execution["duration_seconds"]
        )

        spawn_rate = (
            users / ramp
            if ramp > 0
            else users
        )

        execution_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        csv_prefix = (
            execution_dir / "locust"
        )

        html_report = (
            execution_dir
            / "locust-report.html"
        )

        command = [
            sys.executable,
            "-m",
            "locust",
            "-f",
            str(artifact.resolve()),
            "--headless",
            "-u",
            str(users),
            "-r",
            str(spawn_rate),
            "-t",
            f"{duration}s",
            "--exit-code-on-error",
            "0",
            "--csv",
            str(csv_prefix),
            "--html",
            str(html_report),
        ]

        completed = subprocess.run(
            command,
            cwd=self.project_root,
            check=False,
        )

        metadata = {
            "engine": "locust",
            "artifact": str(
                artifact.resolve()
            ),
            "profile": str(
                profile_path
            ),
            "users": users,
            "ramp_time_seconds": ramp,
            "duration_seconds": duration,
            "spawn_rate": spawn_rate,
        }

        scenario = context.get(
            "scenario"
        )

        target = context.get(
            "target"
        )

        expected_status = context.get(
            "expected_status"
        )

        if scenario:
            metadata["scenario"] = scenario

        if target:
            metadata["target"] = target

        if expected_status is not None:
            metadata[
                "expected_status"
            ] = expected_status

        metadata_path = (
            execution_dir
            / "metadata.json"
        )

        metadata_path.write_text(
            json.dumps(
                metadata,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        if completed.returncode != 0:
            raise RuntimeError(
                "Locust execution failed with "
                f"exit code {completed.returncode}."
            )

        return execution_dir
