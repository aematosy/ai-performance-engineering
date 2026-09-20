from __future__ import annotations

import unittest
from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)


class LocustRuntimeResolutionTests(
    unittest.TestCase
):
    def test_locust_uses_current_python_environment(
        self,
    ):
        text = (
            ROOT
            / "src"
            / "performance_engineering"
            / "engines"
            / "locust"
            / "adapter.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "sys.executable",
            text,
        )

        self.assertIn(
            '"-m"',
            text,
        )

        self.assertIn(
            '"locust"',
            text,
        )

    def test_locust_does_not_depend_on_bare_binary(
        self,
    ):
        text = (
            ROOT
            / "src"
            / "performance_engineering"
            / "engines"
            / "locust"
            / "adapter.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            '''[
            "locust",''',
            text,
        )


if __name__ == "__main__":
    unittest.main()
