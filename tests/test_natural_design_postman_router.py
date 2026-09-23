from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NaturalPostmanDesignRouterTests(
    unittest.TestCase
):

    def test_router_supports_postman_collection(
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
            "--collection",
            text,
        )

        self.assertIn(
            "--input-type postman",
            text,
        )

    def test_router_uses_public_workflow_for_postman(
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
            "scripts/performance_workflow.py",
            text,
        )

        self.assertIn(
            "intake",
            text,
        )

    def test_router_preserves_existing_http_front_door(
        self,
    ):
        self.assertTrue(
            (
                ROOT
                / "scripts"
                / "natural_performance_design_http.sh"
            ).is_file()
        )

    def test_skill_forbids_direct_postman_internals(
        self,
    ):
        text = (
            ROOT
            / ".axet"
            / "skills"
            / "performance-test-designer"
            / "SKILL.md"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "No ejecutes postman_pipeline.py directamente",
            text,
        )

        self.assertIn(
            "No ejecutes prepare_postman_design.py directamente",
            text,
        )


if __name__ == "__main__":
    unittest.main()
