#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISCOVER = ROOT / "scripts" / "discover_postman_scenarios.py"
VALIDATE = ROOT / "scripts" / "validate_scenario_candidates.py"


def request(
    request_id: str,
    method: str,
    raw_url: str,
    *,
    resolved_url: str | None,
    path: str | None,
    unresolved=None,
    folder: str = "API",
    created=None,
    refs=None,
    static=None,
):
    return {
        "id": request_id,
        "name": request_id.split("/")[-1],
        "folder_path": [folder],
        "method": method,
        "url": {
            "raw": raw_url,
            "resolved": resolved_url or raw_url,
            "path": path,
            "unresolved_variables": unresolved or [],
        },
        "variable_references": refs or [],
        "variables_created": created or [],
        "static_resource_candidates": static or [],
        "unsupported_features": [],
    }


class ScenarioDiscoveryV12Tests(unittest.TestCase):
    def run_discovery(self, model):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            input_path = tmp / "normalized.json"
            output_path = tmp / "candidates.json"

            input_path.write_text(
                json.dumps(model),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(DISCOVER),
                    "--input",
                    str(input_path),
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
                output_path.read_text(encoding="utf-8")
            )

    def model(
        self,
        requests,
        dependencies=None,
        dynamic_runtime=None,
    ):
        return {
            "schema_version": "2.0",
            "collection": {"name": "Fixture"},
            "variables": {
                "dynamic_runtime": dynamic_runtime or [],
            },
            "requests": requests,
            "dependencies": dependencies or [],
        }

    def test_unresolved_base_url_still_discovers_e2e(self):
        requests = [
            request(
                "Orders/Create",
                "POST",
                "{{baseUrl}}/orders",
                resolved_url=None,
                path=None,
                unresolved=["baseUrl"],
                folder="Orders",
            ),
            request(
                "Orders/Get",
                "GET",
                "{{baseUrl}}/orders/123",
                resolved_url=None,
                path=None,
                unresolved=["baseUrl"],
                folder="Orders",
                static=[
                    {
                        "value": "123",
                        "kind": "NUMERIC",
                        "confidence": "HIGH",
                    }
                ],
            ),
            request(
                "Orders/Update",
                "PUT",
                "{{baseUrl}}/orders/123",
                resolved_url=None,
                path=None,
                unresolved=["baseUrl"],
                folder="Orders",
                static=[
                    {
                        "value": "123",
                        "kind": "NUMERIC",
                        "confidence": "HIGH",
                    }
                ],
            ),
            request(
                "Orders/Delete",
                "DELETE",
                "{{baseUrl}}/orders/123",
                resolved_url=None,
                path=None,
                unresolved=["baseUrl"],
                folder="Orders",
                static=[
                    {
                        "value": "123",
                        "kind": "NUMERIC",
                        "confidence": "HIGH",
                    }
                ],
            ),
        ]

        data = self.run_discovery(
            self.model(requests)
        )

        e2e = [
            c for c in data["candidates"]
            if c["type"] == "E2E_CANDIDATE"
        ]

        self.assertEqual(len(e2e), 1)
        self.assertEqual(
            e2e[0]["unresolved_variables"],
            ["baseUrl"],
        )
        self.assertEqual(
            e2e[0]["confidence"],
            "MEDIUM",
        )

    def test_unresolved_dependency_flow_is_not_high_confidence(self):
        requests = [
            request(
                "Auth/CreateToken",
                "POST",
                "{{baseUrl}}/auth",
                resolved_url=None,
                path=None,
                unresolved=["baseUrl"],
                folder="Auth",
                created=[
                    {
                        "name": "token",
                        "scope": "environment",
                    }
                ],
            ),
            request(
                "Orders/Update",
                "PUT",
                "{{baseUrl}}/orders/123",
                resolved_url=None,
                path=None,
                unresolved=["baseUrl"],
                folder="Orders",
                refs=["token"],
                static=[
                    {
                        "value": "123",
                        "kind": "NUMERIC",
                        "confidence": "HIGH",
                    }
                ],
            ),
        ]

        data = self.run_discovery(
            self.model(
                requests,
                dependencies=[
                    {
                        "producer": "Auth/CreateToken",
                        "consumer": "Orders/Update",
                        "variable": "token",
                    }
                ],
                dynamic_runtime=["token"],
            )
        )

        flow = next(
            c for c in data["candidates"]
            if c["type"] == "DEPENDENCY_FLOW"
        )

        self.assertEqual(flow["confidence"], "MEDIUM")
        self.assertEqual(
            flow["unresolved_variables"],
            ["baseUrl"],
        )

    def test_resolved_flow_remains_high_when_clean(self):
        requests = [
            request(
                "Users/List",
                "GET",
                "https://example.test/users",
                resolved_url="https://example.test/users",
                path="/users",
                unresolved=[],
                folder="Users",
            )
        ]

        data = self.run_discovery(
            self.model(requests)
        )

        candidate = next(
            c for c in data["candidates"]
            if c["type"] == "READ_ONLY"
        )

        self.assertEqual(
            candidate["confidence"],
            "HIGH",
        )

    def test_validator_accepts_v12(self):
        requests = [
            request(
                "Users/List",
                "GET",
                "{{baseUrl}}/users",
                resolved_url=None,
                path=None,
                unresolved=["baseUrl"],
                folder="Users",
            )
        ]

        data = self.run_discovery(
            self.model(requests)
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "candidates.json"
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
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )


if __name__ == "__main__":
    unittest.main()
