from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_module(relative: str, name: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PostmanResponseContractDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiler = load_module(
            "src/performance_engineering/design/compilers/postman_scenario.py",
            "postman_scenario_contract_test",
        )
        cls.resolver = load_module(
            "scripts/resolve_postman_response_contract.py",
            "postman_response_contract_test",
        )

    def test_explicit_postman_status_is_preserved(self):
        item = {
            "name": "CreateToken",
            "event": [{
                "listen": "test",
                "script": {"exec": [
                    'pm.test("status", function () {',
                    '  pm.response.to.have.status(200)',
                    '})',
                ]},
            }],
            "response": [],
        }
        self.assertEqual(
            self.compiler.expected_status_from_postman_item(item),
            200,
        )

    def test_conflicting_postman_statuses_fail_closed(self):
        item = {
            "name": "Ambiguous",
            "event": [{
                "script": {"exec": [
                    "pm.response.to.have.status(200)",
                    "pm.response.to.have.status(201)",
                ]},
            }],
        }
        with self.assertRaises(self.compiler.CompileError):
            self.compiler.expected_status_from_postman_item(item)


    def test_functional_request_adds_neutral_accept_when_source_omits_it(self):
        captured = {}

        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"{}"

        def fake_urlopen(request, timeout):
            captured["accept"] = request.get_header("Accept")
            captured["content_type"] = request.get_header("Content-type")
            return FakeResponse()

        request = {
            "id": "Booking/CreateBooking",
            "method": "POST",
            "protocol": "https",
            "host": "example.test",
            "path": "/booking",
            "headers": [],
            "json_body": {"firstname": "Jim"},
        }

        with patch.object(self.resolver, "urlopen", fake_urlopen):
            status, _ = self.resolver.execute_request(
                request, {}, {}, {}, 1.0
            )

        self.assertEqual(status, 200)
        self.assertEqual(captured["accept"], "*/*")
        self.assertEqual(captured["content_type"], "application/json")

    def test_explicit_accept_header_is_preserved(self):
        captured = {}

        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"{}"

        def fake_urlopen(request, timeout):
            captured["accept"] = request.get_header("Accept")
            return FakeResponse()

        request = {
            "id": "A",
            "method": "GET",
            "protocol": "https",
            "host": "example.test",
            "path": "/a",
            "headers": [{"name": "Accept", "value": "application/xml"}],
            "json_body": None,
        }

        with patch.object(self.resolver, "urlopen", fake_urlopen):
            self.resolver.execute_request(request, {}, {}, {}, 1.0)

        self.assertEqual(captured["accept"], "application/xml")

    def test_cleanup_dependency_detection_finds_runtime_path_values(self):
        request = {
            "path": "/booking/${booking_id}",
            "headers": [{"name": "Cookie", "value": "token=${access_token}"}],
            "json_body": None,
        }
        self.assertEqual(
            self.resolver.request_runtime_dependencies(request),
            {"booking_id", "access_token"},
        )

    def test_plan_update_supports_per_transaction_statuses(self):
        model = {
            "requests": [
                {"id": "A", "method": "POST", "path": "/a", "expected_status": 200},
                {"id": "B", "method": "DELETE", "path": "/b/${id}", "expected_status": 201},
            ]
        }
        plan = {
            "transactions": [
                {"name": "A", "method": "POST", "path": "/a", "expected_status": "UNRESOLVED"},
                {"name": "B", "method": "DELETE", "path": "/b/${id}", "expected_status": "UNRESOLVED"},
            ],
            "assertions": [],
        }
        self.resolver.update_plan(plan, model)
        self.assertEqual(plan["transactions"][0]["expected_status"], 200)
        self.assertEqual(plan["transactions"][1]["expected_status"], 201)
        self.assertEqual(
            [item["expected_value"] for item in plan["assertions"]],
            ["200", "201"],
        )


if __name__ == "__main__":
    unittest.main()
