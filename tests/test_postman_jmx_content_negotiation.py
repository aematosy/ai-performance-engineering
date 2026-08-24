import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

GENERATOR = (
    ROOT
    / "scripts"
    / "generate_postman_jmx.py"
)


class PostmanJmxContentNegotiationTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls):
        cls.source = GENERATOR.read_text()

    def test_json_body_has_content_type_fallback(self):
        self.assertIn(
            '"Content-Type"',
            self.source,
        )
        self.assertIn(
            '"application/json"',
            self.source,
        )

    def test_missing_accept_gets_non_restrictive_fallback(self):
        self.assertIn(
            '"Accept"',
            self.source,
        )
        self.assertIn(
            '"*/*"',
            self.source,
        )

    def test_accept_fallback_is_not_body_only(self):
        accept_position = self.source.find(
            '== "accept"'
        )

        self.assertGreater(
            accept_position,
            0,
        )

        preceding = self.source[
            max(0, accept_position - 120):
            accept_position
        ]

        self.assertNotIn(
            "body is not None",
            preceding,
        )

    def test_explicit_accept_is_preserved(self):
        self.assertIn(
            '== "accept"',
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
