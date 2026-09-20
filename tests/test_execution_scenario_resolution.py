from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.resolve_execution_scenario as resolver


class ExecutionScenarioResolutionTests(
    unittest.TestCase
):

    def test_direct_plan_keeps_existing_identity(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            plan = (
                root
                / "tests"
                / "plans"
                / "dummyjson-final-e2e-v3"
                / "test-plan.yaml"
            )

            plan.parent.mkdir(
                parents=True
            )

            plan.write_text(
                "status: APPROVED\n",
                encoding="utf-8",
            )

            with patch.object(
                resolver,
                "ROOT",
                root,
            ):
                self.assertEqual(
                    resolver.resolve(
                        "dummyjson-final-e2e-v3"
                    ),
                    "dummyjson-final-e2e-v3",
                )

    def test_postman_request_id_resolves_canonical_scenario(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            manifest = (
                root
                / "workspaces"
                / "restful-booker-e2e-demo"
                / "design-manifest.json"
            )

            manifest.parent.mkdir(
                parents=True
            )

            manifest.write_text(
                json.dumps(
                    {
                        "status": "DESIGN_ARTIFACTS_READY",
                        "scenario": "booking-e2e",
                    }
                ),
                encoding="utf-8",
            )

            plan = (
                root
                / "tests"
                / "plans"
                / "booking-e2e"
                / "test-plan.yaml"
            )

            plan.parent.mkdir(
                parents=True
            )

            plan.write_text(
                "status: DRAFT\n",
                encoding="utf-8",
            )

            with patch.object(
                resolver,
                "ROOT",
                root,
            ):
                self.assertEqual(
                    resolver.resolve(
                        "restful-booker-e2e-demo"
                    ),
                    "booking-e2e",
                )

    def test_missing_alias_does_not_guess(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(
                resolver,
                "ROOT",
                Path(tmp),
            ):
                with self.assertRaises(
                    RuntimeError
                ):
                    resolver.resolve(
                        "unknown"
                    )


if __name__ == "__main__":
    unittest.main()
