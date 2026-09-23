from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from performance_engineering.application.engine_artifact import (
    scenario_name_from_model,
)
from performance_engineering.engines.locust.postman_generator import (
    generate_postman_locust,
)


class PostmanLocustGenerationTests(
    unittest.TestCase
):

    def test_postman_executable_model_generates_locustfile(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            model_dir = (
                root
                / "work"
                / "postman"
                / "sample-e2e"
            )

            model_dir.mkdir(
                parents=True
            )

            plan_dir = (
                root
                / "tests"
                / "plans"
                / "sample-e2e"
            )

            plan_dir.mkdir(
                parents=True
            )

            data_dir = (
                root
                / "data"
                / "sample-e2e"
            )

            data_dir.mkdir(
                parents=True
            )

            model = {
                "schema_version": "1.0",
                "source": {
                    "type": "POSTMAN",
                },
                "scenario_candidate": {
                    "id": "resource-e2e-e2e-candidate",
                    "type": "E2E_CANDIDATE",
                },
                "requests": [
                    {
                        "id": "Resource/Create",
                        "method": "POST",
                        "protocol": "https",
                        "host": "example.test",
                        "port": None,
                        "path": "/resource",
                        "query": "",
                        "headers": [],
                        "json_body": {
                            "name": {
                                "__runtime_parameter__":
                                    "resource_name",
                                "__json_type__":
                                    "STRING",
                            }
                        },
                        "extractors": [
                            {
                                "variable": "resource_id",
                                "json_path": "$.id",
                            }
                        ],
                    },
                    {
                        "id": "Resource/Get",
                        "method": "GET",
                        "protocol": "https",
                        "host": "example.test",
                        "port": None,
                        "path": "/resource/${resource_id}",
                        "query": "",
                        "headers": [],
                        "json_body": None,
                        "extractors": [],
                    },
                ],
                "csv": {
                    "columns": [
                        {
                            "name": "resource_name",
                            "example_value": "demo",
                            "json_type": "STRING",
                        }
                    ]
                },
                "secrets": {
                    "jmeter_properties": [],
                    "persist_values": False,
                },
                "correlations": [
                    {
                        "runtime_variable": "resource_id",
                        "producer": "Resource/Create",
                        "json_path": "$.id",
                        "consumers": [
                            "Resource/Get",
                        ],
                        "status": "RESOLVED",
                    }
                ],
            }

            model_path = (
                model_dir
                / "executable-model.json"
            )

            model_path.write_text(
                json.dumps(
                    model
                ),
                encoding="utf-8",
            )

            plan = {
                "transactions": [
                    {
                        "name": "Resource/Create",
                        "method": "POST",
                        "path": "/resource",
                        "expected_status": 201,
                    },
                    {
                        "name": "Resource/Get",
                        "method": "GET",
                        "path": "/resource/${resource_id}",
                        "expected_status": 200,
                    },
                ]
            }

            (
                plan_dir
                / "test-plan.yaml"
            ).write_text(
                yaml.safe_dump(
                    plan
                ),
                encoding="utf-8",
            )

            (
                data_dir
                / "test-data.csv"
            ).write_text(
                "resource_name\n"
                "demo\n",
                encoding="utf-8",
            )

            profile_path = (
                root
                / "execution-profile.yaml"
            )

            profile_path.write_text(
                yaml.safe_dump(
                    {
                        "execution": {
                            "mode": "DURATION",
                            "threads": 2,
                            "ramp_time_seconds": 2,
                            "duration_seconds": 10,
                            "pacing_seconds": 1,
                        }
                    }
                ),
                encoding="utf-8",
            )

            output = (
                root
                / "tests"
                / "generated"
                / "locust"
                / "sample-e2e"
                / "locustfile.py"
            )

            generated = generate_postman_locust(
                project_root=root,
                model_path=model_path,
                profile_path=profile_path,
                output=output,
            )

            self.assertTrue(
                generated.is_file()
            )

            content = generated.read_text(
                encoding="utf-8"
            )

            self.assertIn(
                "resource_id",
                content,
            )

            self.assertIn(
                "REQUESTS = json.loads(",
                content,
            )

            self.assertNotIn(
                '"port": null',
                content,
            )

            self.assertNotIn(
                ": true",
                content,
            )

            self.assertNotIn(
                ": false",
                content,
            )

            self.assertIn(
                "Resource/Create",
                content,
            )

            self.assertIn(
                "Resource/Get",
                content,
            )

            self.assertEqual(
                scenario_name_from_model(
                    model_path
                ),
                "sample-e2e",
            )


if __name__ == "__main__":
    unittest.main()
