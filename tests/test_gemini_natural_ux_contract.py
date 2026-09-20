from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GeminiNaturalUXContractTests(unittest.TestCase):

    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(
            encoding="utf-8"
        )

    def test_global_contract_is_compact(self):
        text = self.read("GEMINI.md")

        self.assertLess(
            len(text.splitlines()),
            400,
        )

    def test_two_natural_entrypoints_exist(self):
        text = self.read("GEMINI.md")

        self.assertIn(
            "scripts/natural_performance_design.sh",
            text,
        )

        self.assertIn(
            "scripts/natural_performance_execute.sh",
            text,
        )

    def test_legacy_public_orchestration_removed(self):
        text = self.read("GEMINI.md")

        forbidden = (
            "## Canonical Public Performance Workflow",
            "### APPROVE command",
            "### AUTHORIZE command",
            "### PREFLIGHT command",
            "### EXECUTE command",
            "## MULTI-ENGINE EXECUTION - AUTHORITATIVE CONTRACT",
        )

        for item in forbidden:
            self.assertNotIn(
                item,
                text,
            )

    def test_single_functional_request_supported(self):
        text = self.read("GEMINI.md")

        self.assertIn(
            "single functional request",
            text,
        )

    def test_runner_uses_natural_execution(self):
        text = self.read(
            ".gemini/skills/performance-test-runner/SKILL.md"
        )

        self.assertIn(
            "scripts/natural_performance_execute.sh",
            text,
        )

    def test_run_is_final_gate(self):
        text = self.read("GEMINI.md")

        self.assertIn(
            "`RUN`",
            text,
        )


if __name__ == "__main__":
    unittest.main()
