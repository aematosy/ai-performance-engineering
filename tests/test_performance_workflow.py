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


class PerformanceWorkflowTests(
    unittest.TestCase
):
    def test_public_contract_does_not_call_run_test(self):
        source = SCRIPT.read_text()

        self.assertNotIn(
            'python_command("run_test.py")',
            source,
        )

    def test_controlled_command_uses_approved_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            plan = root / "plan.yaml"
            profile = root / "profile.yaml"
            jmx = root / "test.jmx"

            for path in (
                plan,
                profile,
                jmx,
            ):
                path.write_text("x")

            args = SimpleNamespace(
                plan=plan,
                profile=profile,
                jmx=jmx,
                csv=None,
                data_requirements=None,
                design_context=None,
                properties=None,
                manifest=None,
            )

            command = (
                MODULE.build_controlled_command(
                    args,
                    "preflight",
                )
            )

            joined = " ".join(command)

            self.assertIn(
                "run_approved_plan.py",
                joined,
            )

            self.assertIn(
                "--preflight",
                command,
            )

            self.assertNotIn(
                "--execute",
                command,
            )

    def test_execute_mode_has_no_load_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            plan = root / "plan.yaml"
            profile = root / "profile.yaml"
            jmx = root / "test.jmx"

            for path in (
                plan,
                profile,
                jmx,
            ):
                path.write_text("x")

            args = SimpleNamespace(
                plan=plan,
                profile=profile,
                jmx=jmx,
                csv=None,
                data_requirements=None,
                design_context=None,
                properties=None,
                manifest=None,
            )

            command = (
                MODULE.build_controlled_command(
                    args,
                    "execute",
                )
            )

            forbidden = {
                "--threads",
                "--ramp-time",
                "--duration",
                "--target",
                "--authorized",
            }

            self.assertTrue(
                forbidden.isdisjoint(
                    command
                )
            )

            self.assertIn(
                "--execute",
                command,
            )

    def test_csv_requires_data_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            plan = root / "plan.yaml"
            profile = root / "profile.yaml"
            jmx = root / "test.jmx"
            csv = root / "data.csv"

            for path in (
                plan,
                profile,
                jmx,
                csv,
            ):
                path.write_text("x")

            args = SimpleNamespace(
                plan=plan,
                profile=profile,
                jmx=jmx,
                csv=csv,
                data_requirements=None,
                design_context=None,
                properties=None,
                manifest=None,
            )

            with self.assertRaises(
                MODULE.WorkflowError
            ):
                MODULE.build_controlled_command(
                    args,
                    "preflight",
                )


if __name__ == "__main__":
    unittest.main()

class RequiredJMeterPropertiesTests(unittest.TestCase):

    def test_execute_blocks_when_data_contract_requires_properties(
        self,
    ):
        source = (
            ROOT
            / "scripts"
            / "performance_workflow.py"
        ).read_text()

        self.assertIn(
            "JMETER_PROPERTY",
            source,
        )

        self.assertIn(
            "Execution requires --properties",
            source,
        )

    def test_properties_remain_optional_for_scenarios_without_secrets(
        self,
    ):
        source = (
            ROOT
            / "scripts"
            / "performance_workflow.py"
        ).read_text()

        self.assertIn(
            "required_jmeter_properties",
            source,
        )
