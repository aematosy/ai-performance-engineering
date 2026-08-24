#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PREPARE = (
    ROOT
    / "scripts"
    / "prepare_postman_design_context.py"
)

VALIDATE = (
    ROOT
    / "scripts"
    / "validate_postman_design_context.py"
)


class PostmanDesignContextV12Tests(
    unittest.TestCase
):
    def run_prepare(
        self,
        extraction=None,
        static_id=False,
        requires_correlation=False,
    ):
        created_variable = {
            "scope": "environment",
            "name": "access_token",
            "sensitive": True,
        }

        if extraction is not None:
            created_variable[
                "extraction"
            ] = extraction

        static = (
            [
                {
                    "value": "123",
                    "kind": "NUMERIC",
                    "confidence": "HIGH",
                }
            ]
            if static_id
            else []
        )

        normalized = {
            "schema_version": "2.0",
            "collection": {
                "name": "Fixture",
            },
            "environment": {
                "name": "Fixture Env",
                "provided": True,
            },
            "variables": {
                "dynamic_runtime": [
                    "access_token",
                ],
            },
            "requests": [
                {
                    "id": "Auth/CreateToken",
                    "name": "CreateToken",
                    "folder_path": [
                        "Auth",
                    ],
                    "method": "POST",
                    "url": {
                        "raw": (
                            "https://example.test/"
                            "auth"
                        ),
                        "resolved": (
                            "https://example.test/"
                            "auth"
                        ),
                        "protocol": "https",
                        "host": "example.test",
                        "port": None,
                        "path": "/auth",
                        "unresolved_variables": [],
                    },
                    "headers": [],
                    "query": [],
                    "path_variables": [],
                    "auth": {
                        "type": "NOAUTH",
                        "details": [],
                        "unsupported": False,
                    },
                    "body": {
                        "mode": "raw",
                        "content": {
                            "raw": "{}",
                        },
                        "unsupported": False,
                    },
                    "variable_references": [],
                    "variables_created": [
                        created_variable,
                    ],
                    "candidate_assertions": [],
                    "static_resource_candidates": [],
                    "unsupported_features": [],
                },
                {
                    "id": "Orders/Update",
                    "name": "Update",
                    "folder_path": [
                        "Orders",
                    ],
                    "method": "PUT",
                    "url": {
                        "raw": (
                            "https://example.test/"
                            "orders/123"
                        ),
                        "resolved": (
                            "https://example.test/"
                            "orders/123"
                        ),
                        "protocol": "https",
                        "host": "example.test",
                        "port": None,
                        "path": "/orders/123",
                        "unresolved_variables": [],
                    },
                    "headers": [],
                    "query": [],
                    "path_variables": [],
                    "auth": {
                        "type": "INHERIT",
                        "details": [],
                        "unsupported": False,
                    },
                    "body": {
                        "mode": "raw",
                        "content": {
                            "raw": "{}",
                        },
                        "unsupported": False,
                    },
                    "variable_references": [
                        "access_token",
                    ],
                    "variables_created": [],
                    "candidate_assertions": [],
                    "static_resource_candidates": static,
                    "unsupported_features": [],
                },
            ],
            "dependencies": [
                {
                    "producer": (
                        "Auth/CreateToken"
                    ),
                    "consumer": (
                        "Orders/Update"
                    ),
                    "variable": (
                        "access_token"
                    ),
                }
            ],
        }

        candidates = {
            "schema_version": "1.1",
            "candidate_count": 1,
            "candidates": [
                {
                    "id": (
                        "orders-update-flow"
                    ),
                    "type": (
                        "DEPENDENCY_FLOW"
                    ),
                    "requests": [
                        "Auth/CreateToken",
                        "Orders/Update",
                    ],
                    "required_runtime_variables": [
                        "access_token",
                    ],
                    "requires_correlation": (
                        requires_correlation
                    ),
                    "warnings": [],
                    "risks": [],
                    "unsupported_features": [],
                    "confidence": "HIGH",
                    "rationale": (
                        "Runtime dependency."
                    ),
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)

            normalized_path = (
                tmp / "normalized.json"
            )
            candidates_path = (
                tmp / "candidates.json"
            )
            output_path = (
                tmp / "context.json"
            )

            normalized_path.write_text(
                json.dumps(normalized),
                encoding="utf-8",
            )

            candidates_path.write_text(
                json.dumps(candidates),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(PREPARE),
                    "--normalized",
                    str(normalized_path),
                    "--candidates",
                    str(candidates_path),
                    "--candidate-id",
                    "orders-update-flow",
                    "--output",
                    str(output_path),
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
                output_path.read_text(
                    encoding="utf-8",
                )
            )

    def test_runtime_dependency_without_extractor_blocks_execution(
        self,
    ):
        data = self.run_prepare()

        runtime = [
            item
            for item in data[
                "correlation_requirements"
            ]
            if item["type"]
            == "RUNTIME_VARIABLE"
        ]

        self.assertEqual(
            runtime[0]["status"],
            "EXTRACTION_STRATEGY_REQUIRED",
        )

        self.assertTrue(
            data[
                "design_readiness"
            ]["ready_for_design"]
        )

        self.assertFalse(
            data[
                "design_readiness"
            ]["ready_for_execution"]
        )

    def test_runtime_dependency_with_extractor_is_detected(
        self,
    ):
        data = self.run_prepare(
            extraction={
                "type": "JSON_PATH",
                "expression": "$.token",
            }
        )

        runtime = [
            item
            for item in data[
                "correlation_requirements"
            ]
            if item["type"]
            == "RUNTIME_VARIABLE"
        ]

        self.assertEqual(
            runtime[0]["status"],
            "DETECTED",
        )

        self.assertEqual(
            runtime[0]["extraction"][
                "expression"
            ],
            "$.token",
        )

        self.assertTrue(
            data[
                "design_readiness"
            ]["ready_for_execution"]
        )

    def test_static_resource_still_blocks_execution(
        self,
    ):
        data = self.run_prepare(
            extraction={
                "type": "JSON_PATH",
                "expression": "$.token",
            },
            static_id=True,
        )

        self.assertTrue(
            any(
                item["status"]
                == "REVIEW_REQUIRED"
                for item in data[
                    "correlation_requirements"
                ]
            )
        )

        self.assertFalse(
            data[
                "design_readiness"
            ]["ready_for_execution"]
        )

    def test_required_e2e_resource_correlation_blocks_execution(
        self,
    ):
        data = self.run_prepare(
            extraction={
                "type": "JSON_PATH",
                "expression": "$.token",
            },
            static_id=True,
            requires_correlation=True,
        )

        self.assertTrue(
            any(
                item["status"]
                == "REQUIRED_NOT_DEFINED"
                for item in data[
                    "correlation_requirements"
                ]
            )
        )

        self.assertFalse(
            data[
                "design_readiness"
            ]["ready_for_execution"]
        )

    def test_execution_ready_validator_fails_without_extractor(
        self,
    ):
        data = self.run_prepare()

        with tempfile.TemporaryDirectory() as tmp:
            path = (
                Path(tmp)
                / "context.json"
            )

            path.write_text(
                json.dumps(data),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATE),
                    "--input",
                    str(path),
                    "--execution-ready",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(
                result.returncode,
                0,
            )

            self.assertIn(
                "Execution ready : False",
                result.stdout,
            )


if __name__ == "__main__":
    unittest.main()
