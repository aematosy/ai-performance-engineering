from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MultiEngineWorkflowContractTests(
    unittest.TestCase
):
    def test_public_workflow_exposes_engine_selection(self):
        text = (
            ROOT
            / "scripts"
            / "performance_workflow.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            '"select-engine"',
            text,
        )

    def test_public_workflow_exposes_engine_prepare(self):
        text = (
            ROOT
            / "scripts"
            / "performance_workflow.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            '"prepare"',
            text,
        )

    def test_public_workflow_supports_generic_artifact(self):
        text = (
            ROOT
            / "scripts"
            / "performance_workflow.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "--artifact",
            text,
        )

    def test_axet_contract_mentions_jmeter_and_locust(self):
        text = (
            ROOT
            / "AXET.md"
        ).read_text(
            encoding="utf-8"
        ).lower()

        self.assertIn(
            "jmeter",
            text,
        )

        self.assertIn(
            "locust",
            text,
        )

    def test_engine_selection_happens_before_run(self):
        text = (
            ROOT
            / "AXET.md"
        ).read_text(
            encoding="utf-8"
        )

        marker = (
            "MULTI-ENGINE EXECUTION"
        )

        self.assertIn(
            marker,
            text,
        )

        section = text[
            text.index(marker):
        ]

        self.assertIn(
            "ENGINE SELECTION",
            section,
        )

        self.assertIn(
            "STOP FOR RUN",
            section,
        )

        self.assertLess(
            section.index(
                "ENGINE SELECTION"
            ),
            section.index(
                "STOP FOR RUN"
            ),
        )

    def test_run_is_not_engine_selection(self):
        text = (
            ROOT
            / "AXET.md"
        ).read_text(
            encoding="utf-8"
        ).lower()

        self.assertIn(
            "run is not",
            text.replace("`", ""),
        )

        self.assertIn(
            "engine selection",
            text,
        )

    def test_engine_must_not_change_after_preflight(self):
        text = (
            ROOT
            / "AXET.md"
        ).read_text(
            encoding="utf-8"
        ).lower()

        self.assertIn(
            "change engine after",
            text,
        )


if __name__ == "__main__":
    unittest.main()
