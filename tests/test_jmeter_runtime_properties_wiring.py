from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class JMeterRuntimePropertiesWiringTests(
    unittest.TestCase
):

    def test_governed_runner_resolves_only_for_jmeter(
        self,
    ):
        text = (
            ROOT
            / "src"
            / "performance_engineering"
            / "execution"
            / "governed_engine_runner.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'if engine_name == "jmeter":',
            text,
        )

        self.assertIn(
            "resolve_jmeter_runtime_properties(",
            text,
        )

    def test_adapter_passes_only_file_path(
        self,
    ):
        text = (
            ROOT
            / "src"
            / "performance_engineering"
            / "engines"
            / "jmeter"
            / "adapter.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "PERF_JMETER_PROPERTIES_FILE",
            text,
        )

    def test_runner_uses_jmeter_q_option(
        self,
    ):
        text = (
            ROOT
            / "src"
            / "performance_engineering"
            / "engines"
            / "jmeter"
            / "runner.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            '"-q"',
            text,
        )

        self.assertIn(
            "PERF_JMETER_PROPERTIES_FILE",
            text,
        )


if __name__ == "__main__":
    unittest.main()
