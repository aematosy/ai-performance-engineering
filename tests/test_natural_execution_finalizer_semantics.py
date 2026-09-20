from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NaturalExecutionFinalizerSemanticsTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ):
        cls.text = (
            ROOT
            / "scripts"
            / "natural_performance_execute.sh"
        ).read_text(
            encoding="utf-8"
        )

    def test_check_only_skips_finalizer(
        self,
    ):
        self.assertIn(
            'CHECK_ONLY_REQUESTED="false"',
            self.text,
        )

        self.assertIn(
            '"${ARG}" = "--check-only"',
            self.text,
        )

        self.assertIn(
            "[CHECK ONLY] Finalizer omitido",
            self.text,
        )

    def test_real_execution_uses_resolved_scenario(
        self,
    ):
        self.assertIn(
            'scripts/finalize_execution_state.py',
            self.text,
        )

        self.assertIn(
            '"${RESOLVED_ARGS[@]}"',
            self.text,
        )


if __name__ == "__main__":
    unittest.main()
