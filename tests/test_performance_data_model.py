#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLASSIFIER = ROOT / "scripts" / "classify_performance_data.py"
VALIDATOR = ROOT / "scripts" / "validate_performance_data_classification.py"


class PerformanceDataModelV11Tests(unittest.TestCase):
    def run_classifier(self, payload):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            inp = tmp / "input.json"
            out = tmp / "classification.json"

            inp.write_text(
                json.dumps(payload),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLASSIFIER),
                    "--input",
                    str(inp),
                    "--output",
                    str(out),
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
                out.read_text(encoding="utf-8")
            )

    def base_payload(self):
        return {
            "schema_version": "2.0",
            "variables": {
                "collection": [],
                "environment": [
                    {
                        "name": "restfullMicroservice",
                        "value": "https://restful-booker.herokuapp.com",
                        "sensitive": False,
                    }
                ],
                "dynamic_runtime": ["access_token"],
            },
            "requests": [
                {
                    "id": "Booking/CreateBooking",
                    "body": {
                        "mode": "raw",
                        "content": {
                            "raw": json.dumps(
                                {
                                    "firstname": "Jim",
                                    "lastname": "Brown",
                                    "totalprice": 111,
                                }
                            )
                        },
                    },
                    "query": [],
                }
            ],
        }

    def test_url_environment_variable_is_configuration(self):
        data = self.run_classifier(
            self.base_payload()
        )

        config_names = {
            item["name"]
            for item in data["classification"]["configuration"]
        }

        test_names = {
            item["name"]
            for item in data["classification"]["test_data"]
        }

        self.assertIn(
            "restfullMicroservice",
            config_names,
        )

        self.assertNotIn(
            "restfullmicroservice",
            test_names,
        )

    def test_runtime_not_in_csv_candidates(self):
        data = self.run_classifier(
            self.base_payload()
        )

        runtime = {
            item["name"]
            for item in data["classification"]["runtime_correlated"]
        }

        test_names = {
            item["name"]
            for item in data["classification"]["test_data"]
        }

        self.assertIn(
            "access_token",
            runtime,
        )

        self.assertNotIn(
            "access_token",
            test_names,
        )

    def test_body_fields_remain_test_data(self):
        data = self.run_classifier(
            self.base_payload()
        )

        test_names = {
            item["name"]
            for item in data["classification"]["test_data"]
        }

        self.assertEqual(
            test_names,
            {
                "firstname",
                "lastname",
                "totalprice",
            },
        )

    def test_validator_rejects_class_overlap(self):
        payload = {
            "schema_version": "1.1",
            "source_type": "POSTMAN",
            "classification": {
                "configuration": [
                    {
                        "name": "baseUrl",
                        "classification": "CONFIGURATION",
                    }
                ],
                "test_data": [
                    {
                        "name": "baseUrl",
                        "classification": "TEST_DATA_CANDIDATE",
                    }
                ],
                "runtime_correlated": [],
                "secrets": [],
            },
            "findings": [],
            "summary": {},
        }

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "classification.json"
            p.write_text(
                json.dumps(payload),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--input",
                    str(p),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(
                result.returncode,
                0,
            )


if __name__ == "__main__":
    unittest.main()
