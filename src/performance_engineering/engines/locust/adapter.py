from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

import yaml

from performance_engineering.domain.engine import PerformanceEngine

from performance_engineering.engines.locust.postman_generator import (
    generate_postman_locust,
)


class LocustEngine(PerformanceEngine):
    """Locust implementation of the performance-engine contract."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    @property
    def name(self) -> str:
        return "locust"

    @staticmethod
    def _wait_for_metrics_exporter(
        process: subprocess.Popen,
        timeout_seconds: float = 10.0,
    ) -> None:
        deadline = (
            time.monotonic()
            + timeout_seconds
        )

        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    "Locust metrics exporter terminó "
                    "antes de quedar disponible."
                )

            try:
                with urlopen(
                    "http://127.0.0.1:9271/metrics",
                    timeout=1.0,
                ) as response:
                    body = response.read().decode(
                        "utf-8",
                        errors="replace",
                    )

                    if (
                        response.status == 200
                        and "locust_metrics_up" in body
                    ):
                        return
            except OSError:
                pass

            time.sleep(0.2)

        raise RuntimeError(
            "Locust metrics exporter no quedó "
            "disponible en "
            "http://localhost:9271/metrics"
        )

    @staticmethod
    def _stop_metrics_exporter(
        process: subprocess.Popen | None,
    ) -> None:
        if (
            process is None
            or process.poll() is not None
        ):
            return

        process.terminate()

        try:
            process.wait(
                timeout=5
            )
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(
                timeout=5
            )

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

        source = normalized.get(
            "source",
            {}
        )

        source_type = str(
            source.get(
                "type",
                "",
            )
            if isinstance(
                source,
                dict,
            )
            else ""
        ).upper()

        if (
            source_type == "POSTMAN"
            and isinstance(
                normalized.get(
                    "requests"
                ),
                list,
            )
        ):
            return generate_postman_locust(
                project_root=self.project_root,
                model_path=model_path,
                profile_path=profile_path,
                output=output,
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

        # Locust result directories are intentionally stable by scenario.
        # Remove artifacts from the previous run before starting so analysis
        # and reporting can never consume stale CSV/HTML evidence.
        if execution_dir.is_dir():
            shutil.rmtree(
                execution_dir
            )

        execution_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        report_dir = (
            self.project_root
            / "reports"
            / execution_dir.name
        )

        if report_dir.is_dir():
            shutil.rmtree(
                report_dir
            )

        execution_id = (
            datetime.now(timezone.utc)
            .strftime("%Y%m%dT%H%M%S.%fZ")
            + "-"
            + uuid4().hex[:8]
        )
        started_at = (
            datetime.now(timezone.utc)
            .isoformat()
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
            "--csv-full-history",
            "--html",
            str(html_report),
        ]

        # LOCUST_LIVE_OBSERVABILITY
        #
        # The exporter reads Locust's live full-history CSV and
        # exposes engine-neutral Prometheus metrics on port 9271.
        scenario = str(
            context.get(
                "scenario"
            )
            or ""
        ).strip()

        if not scenario:
            directory_name = (
                execution_dir.name
            )

            if directory_name.startswith(
                "locust-"
            ):
                scenario = directory_name[
                    len("locust-"):
                ]

        if not scenario:
            raise RuntimeError(
                "No se pudo resolver el scenario "
                "para la observabilidad Locust."
            )

        exporter_script = (
            self.project_root
            / "scripts"
            / "locust_metrics_exporter.py"
        ).resolve()

        if not exporter_script.is_file():
            raise RuntimeError(
                "Locust metrics exporter no encontrado: "
                f"{exporter_script}"
            )

        exporter_log_path = (
            execution_dir
            / "locust-metrics-exporter.log"
        )

        exporter_process = None

        with exporter_log_path.open(
            "w",
            encoding="utf-8",
        ) as exporter_log:
            try:
                exporter_process = subprocess.Popen(
                    [
                        sys.executable,
                        str(exporter_script),
                        "--results-root",
                        str(
                            (
                                self.project_root
                                / "results"
                            ).resolve()
                        ),
                        "--scenario",
                        scenario,
                        "--port",
                        "9271",
                    ],
                    cwd=self.project_root,
                    stdout=exporter_log,
                    stderr=subprocess.STDOUT,
                )

                self._wait_for_metrics_exporter(
                    exporter_process
                )

                print()
                print(
                    "Locust observability : ACTIVE"
                )
                print(
                    "Metrics              : "
                    "http://localhost:9271/metrics"
                )
                print(
                    "Grafana              : "
                    "http://localhost:3000"
                )
                print()

                completed = subprocess.run(
                    command,
                    cwd=self.project_root,
                    check=False,
                )

            finally:
                self._stop_metrics_exporter(
                    exporter_process
                )

                print()
                print(
                    "Locust observability : INACTIVE"
                )
                print()

        metadata = {
            "execution_id": execution_id,
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
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
