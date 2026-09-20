from pathlib import Path
import unittest

from performance_engineering.design.response_contract import (
    ResponseContractError,
    normalize_expected_status,
)


class ResponseContractTests(unittest.TestCase):

    def test_explicit_200_is_preserved(self):
        self.assertEqual(
            normalize_expected_status(
                200,
                context="GET /resource",
            ),
            [200],
        )

    def test_explicit_201_is_preserved(self):
        self.assertEqual(
            normalize_expected_status(
                [201],
                context="POST /resource",
            ),
            [201],
        )

    def test_post_does_not_imply_201(self):
        with self.assertRaises(ResponseContractError):
            normalize_expected_status(
                None,
                context="POST /resource",
            )

    def test_missing_contract_does_not_imply_200(self):
        with self.assertRaises(ResponseContractError):
            normalize_expected_status(
                None,
                context="GET /resource",
            )


if __name__ == "__main__":
    unittest.main()


class NoSilentDefaultRegressionTests(unittest.TestCase):

    def test_locust_requires_explicit_contract(self):
        from performance_engineering.engines.locust.adapter import (
            LocustEngine,
        )

        engine = LocustEngine(Path("."))

        transaction = {
            "name": "POST /resource",
            "method": "POST",
            "path": "/resource",
        }

        with self.assertRaises(ValueError):
            engine._expected_statuses(
                transaction
            )
