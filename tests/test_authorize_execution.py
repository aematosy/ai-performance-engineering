#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "authorize_execution.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "authorize_execution_v11",
        SCRIPT,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ExecutionAuthorizationV11Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def approved_plan(self):
        return {
            "metadata": {
                "name": "demo",
            },
            "status": "APPROVED",
            "workload": {
                "status": "APPROVED",
            },
            "authorization": {
                "required": True,
                "status": "PENDING",
                "authorized_by": None,
                "authorized_at": None,
            },
            "approval": {
                "approved_by": "Adrian Matos",
                "approved_at": "2026-08-22T20:04:51-05:00",
                "scope": "DESIGN_AND_WORKLOAD",
                "execution_authorized": False,
            },
        }

    def test_approved_plan_passes_preconditions(self):
        self.module.validate_preconditions(
            self.approved_plan()
        )

    def test_draft_plan_is_rejected(self):
        plan = self.approved_plan()
        plan["status"] = "DRAFT"

        with self.assertRaises(
            self.module.AuthorizationError
        ):
            self.module.validate_preconditions(
                plan
            )

    def test_generic_identity_is_rejected(self):
        with self.assertRaises(
            self.module.AuthorizationError
        ):
            self.module.require_explicit_human(
                "User"
            )

    def test_markdown_is_synchronized_to_authorized(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test-plan.md"
            path.write_text(
                "# Demo\n\n"
                "## Estado\n\n"
                "- **Test Plan:** `APPROVED`\n"
                "- **Workload:** `APPROVED`\n"
                "- **Execution Authorization:** `PENDING`\n",
                encoding="utf-8",
            )

            self.module.sync_markdown(
                path,
                plan_status="APPROVED",
                workload_status="APPROVED",
                authorization_status="AUTHORIZED",
                authorized_by="Adrian Matos",
                authorized_at="2026-08-23T00:10:00-05:00",
            )

            content = path.read_text(
                encoding="utf-8"
            )

            self.assertIn(
                "**Authorization Status:** `AUTHORIZED`",
                content,
            )
            self.assertIn(
                "**Authorized By:** `Adrian Matos`",
                content,
            )
            self.assertNotIn(
                "Execution Authorization:** `PENDING`",
                content,
            )

    def test_markdown_sync_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test-plan.md"
            path.write_text(
                "# Demo\n\nBody\n",
                encoding="utf-8",
            )

            kwargs = {
                "plan_status": "APPROVED",
                "workload_status": "APPROVED",
                "authorization_status": "AUTHORIZED",
                "authorized_by": "Adrian Matos",
                "authorized_at": "2026-08-23T00:10:00-05:00",
            }

            self.module.sync_markdown(
                path,
                **kwargs,
            )
            first = path.read_text(
                encoding="utf-8"
            )

            self.module.sync_markdown(
                path,
                **kwargs,
            )
            second = path.read_text(
                encoding="utf-8"
            )

            self.assertEqual(
                first,
                second,
            )

    def test_atomic_yaml_write_preserves_authorization(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "plan.yaml"
            plan = self.approved_plan()
            plan["authorization"]["status"] = "AUTHORIZED"
            plan["authorization"]["authorized_by"] = "Adrian Matos"
            plan["authorization"]["authorized_at"] = (
                "2026-08-23T00:10:00-05:00"
            )
            plan["approval"]["execution_authorized"] = True

            self.module.atomic_write_yaml(
                path,
                plan,
            )

            loaded = yaml.safe_load(
                path.read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                loaded["authorization"]["status"],
                "AUTHORIZED",
            )
            self.assertTrue(
                loaded["approval"]["execution_authorized"]
            )

    def test_source_contains_no_jmeter_execution(self):
        source = SCRIPT.read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            "subprocess.run",
            source,
        )
        self.assertNotIn(
            "jmeter -n",
            source,
        )


if __name__ == "__main__":
    unittest.main()
