#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SCOPE = (
    ROOT
    / "scripts"
    / "scope_performance_data.py"
)

CSVGEN = (
    ROOT
    / "scripts"
    / "generate_scenario_test_data.py"
)


class ScenarioDataTests(
    unittest.TestCase
):
    def fixture_classification(
        self,
    ):
        return {
            "schema_version": "1.1",
            "source_type": "POSTMAN",
            "classification": {
                "configuration": [
                    {
                        "name": "baseUrl",
                        "classification": (
                            "CONFIGURATION"
                        ),
                    }
                ],
                "test_data": [
                    {
                        "name": (
                            "orders_create_firstname"
                        ),
                        "original_name": "firstname",
                        "classification": (
                            "TEST_DATA_CANDIDATE"
                        ),
                        "source": "REQUEST_BODY",
                        "request_id": (
                            "Orders/Create"
                        ),
                        "location": "$.firstname",
                        "parameterizable": True,
                        "type": "STRING",
                        "example_value": "Ana",
                    },
                    {
                        "name": (
                            "orders_update_firstname"
                        ),
                        "original_name": "firstname",
                        "classification": (
                            "TEST_DATA_CANDIDATE"
                        ),
                        "source": "REQUEST_BODY",
                        "request_id": (
                            "Orders/Update"
                        ),
                        "location": "$.firstname",
                        "parameterizable": True,
                        "type": "STRING",
                        "example_value": "Ana2",
                    },
                    {
                        "name": (
                            "orders_update_amount"
                        ),
                        "original_name": "amount",
                        "classification": (
                            "TEST_DATA_CANDIDATE"
                        ),
                        "source": "REQUEST_BODY",
                        "request_id": (
                            "Orders/Update"
                        ),
                        "location": "$.amount",
                        "parameterizable": True,
                        "type": "INTEGER",
                        "example_value": 10,
                    },
                ],
                "runtime_correlated": [
                    {
                        "name": "access_token",
                        "classification": (
                            "RUNTIME_CORRELATED"
                        ),
                    }
                ],
                "secrets": [],
            },
            "findings": [],
            "summary": {},
        }

    def fixture_context(
        self,
        request_ids,
    ):
        return {
            "schema_version": "1.2",
            "scenario_candidate": {
                "id": "orders-update-flow",
                "type": (
                    "DEPENDENCY_FLOW"
                ),
            },
            "requests": [
                {
                    "id": request_id,
                }
                for request_id
                in request_ids
            ],
        }

    def run_scope(
        self,
        request_ids,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)

            classification = (
                tmp
                / "classification.json"
            )
            context = (
                tmp
                / "context.json"
            )
            output = (
                tmp
                / "scenario-data.json"
            )

            classification.write_text(
                json.dumps(
                    self.fixture_classification()
                ),
                encoding="utf-8",
            )

            context.write_text(
                json.dumps(
                    self.fixture_context(
                        request_ids
                    )
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCOPE),
                    "--classification",
                    str(classification),
                    "--design-context",
                    str(context),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(
                result.returncode,
                0,
                result.stderr,
            )

            return json.loads(
                output.read_text(
                    encoding="utf-8"
                )
            )

    def test_single_request_compacts_column_names(
        self,
    ):
        data = self.run_scope(
            [
                "Orders/Update",
            ]
        )

        names = [
            item[
                "scenario_column_name"
            ]
            for item
            in data["test_data"]
        ]

        self.assertEqual(
            names,
            [
                "firstname",
                "amount",
            ],
        )

    def test_other_request_data_is_excluded(
        self,
    ):
        data = self.run_scope(
            [
                "Orders/Update",
            ]
        )

        request_ids = {
            item.get(
                "request_id"
            )
            for item
            in data["test_data"]
        }

        self.assertEqual(
            request_ids,
            {
                "Orders/Update",
            },
        )

    def test_multi_request_duplicate_leaf_names_remain_unique(
        self,
    ):
        data = self.run_scope(
            [
                "Orders/Create",
                "Orders/Update",
            ]
        )

        names = [
            item[
                "scenario_column_name"
            ]
            for item
            in data["test_data"]
        ]

        self.assertEqual(
            len(names),
            len(set(names)),
        )

        self.assertIn(
            "orders_create_firstname",
            names,
        )
        self.assertIn(
            "orders_update_firstname",
            names,
        )

    def test_scenario_csv_generation(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)

            scenario_data = {
                "schema_version": "1.0",
                "scenario_candidate": {
                    "id": (
                        "orders-update-flow"
                    ),
                    "type": (
                        "DEPENDENCY_FLOW"
                    ),
                },
                "test_data": [
                    {
                        "scenario_column_name": (
                            "firstname"
                        ),
                        "parameterizable": True,
                        "type": "STRING",
                        "source": "REQUEST_BODY",
                        "request_id": (
                            "Orders/Update"
                        ),
                        "location": "$.firstname",
                        "example_value": "Ana",
                    },
                    {
                        "scenario_column_name": (
                            "amount"
                        ),
                        "parameterizable": True,
                        "type": "INTEGER",
                        "source": "REQUEST_BODY",
                        "request_id": (
                            "Orders/Update"
                        ),
                        "location": "$.amount",
                        "example_value": 10,
                    },
                ],
            }

            scenario_path = (
                tmp
                / "scenario-data.json"
            )
            csv_path = (
                tmp
                / "data.csv"
            )
            req_path = (
                tmp
                / "requirements.json"
            )

            scenario_path.write_text(
                json.dumps(
                    scenario_data
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(CSVGEN),
                    "--scenario-data",
                    str(scenario_path),
                    "--csv",
                    str(csv_path),
                    "--requirements",
                    str(req_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(
                result.returncode,
                0,
                result.stderr,
            )

            with csv_path.open(
                encoding="utf-8"
            ) as fh:
                reader = csv.DictReader(
                    fh
                )

                self.assertEqual(
                    reader.fieldnames,
                    [
                        "firstname",
                        "amount",
                    ],
                )

            requirements = json.loads(
                req_path.read_text(
                    encoding="utf-8"
                )
            )

            self.assertTrue(
                requirements[
                    "governance"
                ][
                    "scenario_scoped"
                ]
            )


if __name__ == "__main__":
    unittest.main()
