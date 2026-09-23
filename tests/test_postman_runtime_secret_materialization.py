from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = (
        ROOT
        / "scripts"
        / "materialize_postman_runtime_properties.py"
    )

    spec = importlib.util.spec_from_file_location(
        "postman_runtime_secrets",
        path,
    )

    module = importlib.util.module_from_spec(
        spec
    )

    assert spec.loader is not None

    spec.loader.exec_module(
        module
    )

    return module


class PostmanRuntimeSecretMaterializationTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ):
        cls.module = load_module()

    def test_literal_secret_is_resolved(
        self,
    ):
        collection = {
            "item": [
                {
                    "name": "Auth",
                    "item": [
                        {
                            "name": "Login",
                            "request": {
                                "body": {
                                    "mode": "raw",
                                    "raw": json.dumps(
                                        {
                                            "username": "demo",
                                            "password": "secret-value",
                                        }
                                    ),
                                }
                            },
                        }
                    ],
                }
            ]
        }

        model = {
            "requests": [
                {
                    "id": "Auth/Login",
                }
            ],
            "secrets": {
                "jmeter_properties": [
                    "secret_auth_login_password",
                ]
            },
        }

        required, values = (
            self.module.collect_secret_values(
                collection=collection,
                environment=None,
                model=model,
            )
        )

        self.assertEqual(
            required,
            (
                "secret_auth_login_password",
            ),
        )

        self.assertEqual(
            values[
                "secret_auth_login_password"
            ],
            "secret-value",
        )

    def test_environment_variable_secret_is_resolved(
        self,
    ):
        collection = {
            "item": [
                {
                    "name": "Auth",
                    "item": [
                        {
                            "name": "Login",
                            "request": {
                                "body": {
                                    "mode": "raw",
                                    "raw": json.dumps(
                                        {
                                            "password": "{{apiPassword}}",
                                        }
                                    ),
                                }
                            },
                        }
                    ],
                }
            ]
        }

        environment = {
            "values": [
                {
                    "key": "apiPassword",
                    "value": "resolved-secret",
                    "enabled": True,
                }
            ]
        }

        model = {
            "requests": [
                {
                    "id": "Auth/Login",
                }
            ],
            "secrets": {
                "jmeter_properties": [
                    "secret_auth_login_password",
                ]
            },
        }

        _, values = (
            self.module.collect_secret_values(
                collection=collection,
                environment=environment,
                model=model,
            )
        )

        self.assertEqual(
            values[
                "secret_auth_login_password"
            ],
            "resolved-secret",
        )

    def test_unresolved_secret_is_not_invented(
        self,
    ):
        collection = {
            "item": [
                {
                    "name": "Auth",
                    "item": [
                        {
                            "name": "Login",
                            "request": {
                                "body": {
                                    "mode": "raw",
                                    "raw": json.dumps(
                                        {
                                            "password": "{{missingPassword}}",
                                        }
                                    ),
                                }
                            },
                        }
                    ],
                }
            ]
        }

        model = {
            "requests": [
                {
                    "id": "Auth/Login",
                }
            ],
            "secrets": {
                "jmeter_properties": [
                    "secret_auth_login_password",
                ]
            },
        }

        required, values = (
            self.module.collect_secret_values(
                collection=collection,
                environment=None,
                model=model,
            )
        )

        self.assertEqual(
            len(required),
            1,
        )

        self.assertEqual(
            values,
            {},
        )

    def test_no_secret_requires_no_runtime_properties(
        self,
    ):
        required, values = (
            self.module.collect_secret_values(
                collection={
                    "item": [],
                },
                environment=None,
                model={
                    "requests": [],
                    "secrets": {
                        "jmeter_properties": [],
                    },
                },
            )
        )

        self.assertEqual(
            required,
            (),
        )

        self.assertEqual(
            values,
            {},
        )


if __name__ == "__main__":
    unittest.main()
