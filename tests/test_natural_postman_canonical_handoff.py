from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NaturalPostmanCanonicalHandoffTests(
    unittest.TestCase
):

    def test_wrapper_reads_design_manifest(
        self,
    ):
        text = (
            ROOT
            / "scripts"
            / "natural_performance_design_request.sh"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'design-manifest.json',
            text,
        )

        self.assertIn(
            'Canonical scenario',
            text,
        )

    def test_wrapper_does_not_assume_requested_id_is_plan_directory(
        self,
    ):
        text = (
            ROOT
            / "scripts"
            / "natural_performance_design_request.sh"
        ).read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            'PLAN="tests/plans/${SCENARIO}/test-plan.yaml"',
            text,
        )

    def test_wrapper_requires_design_ready_state(
        self,
    ):
        text = (
            ROOT
            / "scripts"
            / "natural_performance_design_request.sh"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'DESIGN_ARTIFACTS_READY',
            text,
        )


if __name__ == "__main__":
    unittest.main()
