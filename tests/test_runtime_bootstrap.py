from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

RUNNER = (
    ROOT
    / "scripts"
    / "run_governed_engine.py"
)


class RuntimeBootstrapTests(
    unittest.TestCase
):
    def test_runner_starts_without_external_pythonpath(
        self,
    ):
        env = os.environ.copy()

        env.pop(
            "PYTHONPATH",
            None,
        )

        completed = subprocess.run(
            [
                "poetry",
                "run",
                "python",
                str(RUNNER),
                "--help",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        output = (
            completed.stdout
            + completed.stderr
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=output,
        )

        self.assertNotIn(
            "ModuleNotFoundError",
            output,
        )

    def test_public_runner_bootstraps_src(
        self,
    ):
        text = RUNNER.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "_SRC_ROOT",
            text,
        )

        self.assertIn(
            "sys.path.insert",
            text,
        )

    def test_natural_flow_bootstraps_src(
        self,
    ):
        text = (
            ROOT
            / "scripts"
            / "natural_performance_execute.sh"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'export PYTHONPATH="${ROOT}/src',
            text,
        )


if __name__ == "__main__":
    unittest.main()
