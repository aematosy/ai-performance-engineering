#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, filename: str):
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(
        name,
        path,
    )
    module = importlib.util.module_from_spec(
        spec
    )
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PostmanE2ECompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resolver = load(
            "resolver",
            "resolve_postman_correlations.py",
        )
        cls.compiler = load(
            "compiler",
            "compile_postman_scenario.py",
        )

    def test_auth_script_correlation_is_detected(self):
        collection = {
            "item": [
                {
                    "name": "Auth",
                    "item": [
                        {
                            "name": "CreateToken",
                            "request": {
                                "method": "POST",
                            },
                            "event": [
                                {
                                    "listen": "test",
                                    "script": {
                                        "exec": [
                                            "var jsonData = JSON.parse(responseBody)",
                                            "var access_token_response = jsonData['token']",
                                            'pm.globals.set("access_token", access_token_response);',
                                        ]
                                    },
                                }
                            ],
                        }
                    ],
                }
            ]
        }

        items = (
            self.resolver
            .detect_postman_script_correlations(
                collection,
                {"Auth/CreateToken"},
            )
        )

        self.assertEqual(
            len(items),
            1,
        )
        self.assertEqual(
            items[0]["runtime_variable"],
            "access_token",
        )
        self.assertEqual(
            items[0]["json_path"],
            "$.token",
        )

    def test_resource_id_inference_for_booking(self):
        normalized = {
            "requests": [
                {
                    "id": "Booking/CreateBooking",
                    "method": "POST",
                    "url": {
                        "path": "/booking",
                    },
                },
                {
                    "id": "Booking/UpdateBooking",
                    "method": "PUT",
                    "url": {
                        "path": "/booking/1911",
                    },
                },
            ],
            "static_resource_candidates": [
                {
                    "request_id": "Booking/UpdateBooking",
                    "value": "1911",
                }
            ],
        }

        candidate = {
            "requests": [
                "Booking/CreateBooking",
                "Booking/UpdateBooking",
            ]
        }

        item = (
            self.resolver
            .infer_resource_correlation(
                normalized,
                candidate,
            )
        )

        self.assertIsNotNone(item)
        self.assertEqual(
            item["runtime_variable"],
            "booking_id",
        )
        self.assertEqual(
            item["json_path"],
            "$.bookingid",
        )

    def test_secret_fields_become_jmeter_properties(self):
        columns = {}
        secrets = set()
        seen = {}

        body = (
            self.compiler
            .parameterize_json_body(
                request_id="Auth/CreateToken",
                body={
                    "username": "admin",
                    "password": "secret",
                },
                seen_leafs=seen,
                csv_columns=columns,
                secret_properties=secrets,
            )
        )

        self.assertIn(
            "auth_createtoken_username",
            columns,
        )
        self.assertNotIn(
            "password",
            columns,
        )
        self.assertTrue(
            str(body["password"]).startswith(
                "${__P(secret_"
            )
        )

    def test_static_resource_tail_is_replaced(self):
        path = (
            self.compiler
            .apply_resource_id(
                "/booking/1911",
                [
                    {
                        "source": "INFERRED_RESOURCE_LIFECYCLE",
                        "runtime_variable": "booking_id",
                    }
                ],
            )
        )

        self.assertEqual(
            path,
            "/booking/${booking_id}",
        )


if __name__ == "__main__":
    unittest.main()
