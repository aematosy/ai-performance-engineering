import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "scripts"
    / "performance_workflow.py"
)

spec = importlib.util.spec_from_file_location(
    "performance_workflow",
    SCRIPT,
)

MODULE = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = MODULE
spec.loader.exec_module(MODULE)


class PerformanceWorkflowTests(unittest.TestCase):
    def _args(self, root: Path, artifact_name: str = "test.jmx"):
        plan = root / "plan.yaml"
        profile = root / "profile.yaml"
        artifact = root / artifact_name
        plan.write_text("metadata:\n  name: test-scenario\n")
        profile.write_text("x")
        artifact.write_text("x")
        return SimpleNamespace(
            plan=plan,
            profile=profile,
            artifact=artifact,
            manifest=None,
            execution_dir=None,
        )

    def test_public_contract_does_not_call_run_test(self):
        source = SCRIPT.read_text()
        self.assertNotIn(
            'python_command("run_test.py")',
            source,
        )

    def test_controlled_command_uses_governed_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self._args(Path(tmp))
            command = MODULE.build_controlled_command(args, "preflight")
            joined = " ".join(command)
            self.assertIn("run_governed_engine.py", joined)
            self.assertIn("--artifact", command)
            self.assertIn("--preflight", command)
            self.assertNotIn("--execute", command)

    def test_execute_mode_has_no_load_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self._args(Path(tmp))
            command = MODULE.build_controlled_command(args, "execute")
            forbidden = {
                "--threads",
                "--ramp-time",
                "--duration",
                "--target",
                "--authorized",
            }
            self.assertTrue(forbidden.isdisjoint(command))
            self.assertIn("--execute", command)

    def test_controlled_command_requires_generic_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = self._args(root)
            args.artifact = root / "missing.jmx"
            with self.assertRaises(MODULE.WorkflowError):
                MODULE.build_controlled_command(args, "preflight")


class RuntimePropertiesContractTests(unittest.TestCase):
    def test_legacy_workflow_property_gate_is_not_used(self):
        source = SCRIPT.read_text()
        controlled = source[
            source.index("def build_controlled_command("):
            source.index("def build_review_command(")
        ]
        self.assertNotIn("required_jmeter_properties", controlled)
        self.assertNotIn("Execution requires --properties", controlled)

    def test_runtime_properties_are_delegated_to_governed_runtime(self):
        runner = (
            ROOT
            / "src"
            / "performance_engineering"
            / "execution"
            / "governed_engine_runner.py"
        ).read_text()
        self.assertIn('if engine_name == "jmeter":', runner)
        self.assertIn("resolve_jmeter_runtime_properties(", runner)


if __name__ == "__main__":
    unittest.main()
