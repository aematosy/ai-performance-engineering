from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GovernedMultiEngineRunnerTests(
    unittest.TestCase
):
    def test_public_workflow_uses_generic_artifact(self):
        text = (
            ROOT
            / "scripts"
            / "performance_workflow.py"
        ).read_text(
            encoding="utf-8"
        )

        controlled = text[
            text.index(
                "def build_controlled_command("
            ):
            text.index(
                "def build_review_command("
            )
        ]

        self.assertIn(
            'args.artifact',
            controlled,
        )

        self.assertNotIn(
            'args.jmx',
            controlled,
        )

    def test_public_runner_exists(self):
        self.assertTrue(
            (
                ROOT
                / "scripts"
                / "run_governed_engine.py"
            ).is_file()
        )

    def test_governed_runner_supports_both_engines(self):
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
            '"jmeter"',
            text,
        )

        self.assertIn(
            '"locust"',
            text,
        )

        self.assertIn(
            'engine_name not in',
            text,
        )

    def test_locust_requires_exact_run(self):
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
            'confirmation != "RUN"',
            text,
        )

    def test_manifest_protects_engine_artifact(self):
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
            '"engine_artifact"',
            text,
        )

        self.assertIn(
            'sha256(',
            text,
        )


if __name__ == "__main__":
    unittest.main()


class GovernedSharedPreflightContractTests(
    unittest.TestCase
):
    def test_jmeter_no_longer_uses_legacy_runtime_bypass(self):
        text = (
            ROOT
            / "src"
            / "performance_engineering"
            / "execution"
            / "governed_engine_runner.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            "and args.execute",
            text,
        )

        self.assertNotIn(
            "delegate_jmeter(",
            text,
        )

        self.assertNotIn(
            "run_approved_plan.py",
            text,
        )

    def test_common_validation_receives_plan_and_profile(self):
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
            '"plan":',
            text,
        )
        self.assertIn(
            'str(plan_path)',
            text,
        )
        self.assertIn(
            '"profile":',
            text,
        )
        self.assertIn(
            'str(profile_path)',
            text,
        )


class GovernedRuntimeDispatchTests(
    unittest.TestCase
):
    def _runner_text(self) -> str:
        return (
            ROOT
            / "src"
            / "performance_engineering"
            / "execution"
            / "governed_engine_runner.py"
        ).read_text(
            encoding="utf-8"
        )

    def test_execute_uses_engine_resolver_contract(self):
        text = self._runner_text()

        self.assertIn(
            "resolve_engine(",
            text,
        )

        self.assertIn(
            "engine.execute(",
            text,
        )

    def test_legacy_jmeter_delegate_is_removed(self):
        text = self._runner_text()

        self.assertNotIn(
            "def delegate_jmeter(",
            text,
        )

        self.assertNotIn(
            "run_approved_plan.py",
            text,
        )

    def test_execute_requires_existing_preflight_manifest(self):
        text = self._runner_text()

        self.assertIn(
            "Governed execution requires an existing",
            text,
        )

        self.assertIn(
            "if not manifest_path.is_file()",
            text,
        )

    def test_execute_does_not_rebaseline_manifest(self):
        text = self._runner_text()

        marker = (
            "if not manifest_path.is_file()"
        )

        execute_section = text[
            text.index(marker):
        ]

        self.assertNotIn(
            "write_manifest(",
            execute_section,
        )

    def test_final_toctou_occurs_after_run_confirmation(self):
        text = self._runner_text()

        execute_marker = (
            "if not manifest_path.is_file()"
        )

        section = text[
            text.index(execute_marker):
        ]

        run_index = section.index(
            'confirmation != "RUN"'
        )

        verify_index = section.index(
            "verify_manifest(",
            run_index,
        )

        dispatch_index = section.index(
            "execute_engine(",
            verify_index,
        )

        self.assertLess(
            run_index,
            verify_index,
        )

        self.assertLess(
            verify_index,
            dispatch_index,
        )

    def test_both_engines_reach_generic_dispatch(self):
        text = self._runner_text()

        self.assertIn(
            'if engine_name == "jmeter"',
            text,
        )

        self.assertIn(
            'if engine_name == "locust"',
            text,
        )

        self.assertIn(
            "return engine.execute(",
            text,
        )
