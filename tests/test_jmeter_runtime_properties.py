from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from performance_engineering.execution.runtime_properties import (
    RuntimePropertiesError,
    resolve_jmeter_runtime_properties,
)


class JMeterRuntimePropertiesTests(
    unittest.TestCase
):

    def create_bundle(
        self,
        root: Path,
        *,
        secrets: list[dict],
        values: dict[str, str] | None,
    ) -> Path:
        scenario = "arbitrary-generated-scenario"

        requirements = (
            root
            / "tests"
            / "plans"
            / scenario
            / "data-requirements.json"
        )

        requirements.parent.mkdir(
            parents=True,
        )

        requirements.write_text(
            json.dumps(
                {
                    "scenario": scenario,
                    "secrets": secrets,
                }
            ),
            encoding="utf-8",
        )

        plan = (
            requirements.parent
            / "test-plan.yaml"
        )

        plan.write_text(
            yaml.safe_dump(
                {
                    "metadata": {
                        "name": scenario,
                    },
                    "data": {
                        "requirements_file":
                            str(requirements),
                    },
                }
            ),
            encoding="utf-8",
        )

        if values is not None:
            properties = (
                root
                / "data"
                / scenario
                / "secrets.properties"
            )

            properties.parent.mkdir(
                parents=True,
            )

            properties.write_text(
                "\n".join(
                    f"{key}={value}"
                    for key, value in values.items()
                )
                + "\n",
                encoding="utf-8",
            )

        return plan

    def test_zero_secrets_requires_nothing(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            plan = self.create_bundle(
                root,
                secrets=[],
                values=None,
            )

            result = resolve_jmeter_runtime_properties(
                project_root=root,
                plan_path=plan,
            )

            self.assertIsNone(
                result
            )

    def test_one_secret_is_resolved(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            plan = self.create_bundle(
                root,
                secrets=[
                    {
                        "name": "client_secret",
                        "source": "JMETER_PROPERTY",
                    }
                ],
                values={
                    "client_secret": "configured",
                },
            )

            result = resolve_jmeter_runtime_properties(
                project_root=root,
                plan_path=plan,
            )

            self.assertIsNotNone(
                result
            )

            self.assertEqual(
                result.required_names,
                ("client_secret",),
            )

    def test_multiple_secrets_are_resolved(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            required = [
                {
                    "name": "client_secret",
                    "source": "JMETER_PROPERTY",
                },
                {
                    "name": "api_key",
                    "source": "JMETER_PROPERTY",
                },
                {
                    "name": "password",
                    "source": "JMETER_PROPERTY",
                },
            ]

            plan = self.create_bundle(
                root,
                secrets=required,
                values={
                    "client_secret": "a",
                    "api_key": "b",
                    "password": "c",
                },
            )

            result = resolve_jmeter_runtime_properties(
                project_root=root,
                plan_path=plan,
            )

            self.assertEqual(
                set(result.required_names),
                {
                    "client_secret",
                    "api_key",
                    "password",
                },
            )

    def test_missing_file_is_blocked(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            plan = self.create_bundle(
                root,
                secrets=[
                    {
                        "name": "secret_x",
                        "source": "JMETER_PROPERTY",
                    }
                ],
                values=None,
            )

            with self.assertRaises(
                RuntimePropertiesError
            ):
                resolve_jmeter_runtime_properties(
                    project_root=root,
                    plan_path=plan,
                )

    def test_missing_key_is_blocked(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            plan = self.create_bundle(
                root,
                secrets=[
                    {
                        "name": "secret_a",
                        "source": "JMETER_PROPERTY",
                    },
                    {
                        "name": "secret_b",
                        "source": "JMETER_PROPERTY",
                    },
                ],
                values={
                    "secret_a": "configured",
                },
            )

            with self.assertRaises(
                RuntimePropertiesError
            ):
                resolve_jmeter_runtime_properties(
                    project_root=root,
                    plan_path=plan,
                )

    def test_empty_value_is_blocked(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            plan = self.create_bundle(
                root,
                secrets=[
                    {
                        "name": "arbitrary_secret",
                        "source": "JMETER_PROPERTY",
                    }
                ],
                values={
                    "arbitrary_secret": "",
                },
            )

            with self.assertRaises(
                RuntimePropertiesError
            ):
                resolve_jmeter_runtime_properties(
                    project_root=root,
                    plan_path=plan,
                )

    def test_other_secret_sources_are_ignored(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            plan = self.create_bundle(
                root,
                secrets=[
                    {
                        "name": "something_else",
                        "source": "VAULT",
                    }
                ],
                values=None,
            )

            result = resolve_jmeter_runtime_properties(
                project_root=root,
                plan_path=plan,
            )

            self.assertIsNone(
                result
            )


if __name__ == "__main__":
    unittest.main()
