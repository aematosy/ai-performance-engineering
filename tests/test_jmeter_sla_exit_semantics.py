from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from performance_engineering.engines.jmeter.adapter import (
    JMeterEngine,
)


class JMeterSlaExitSemanticsTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(
            self.temp_dir.name
        )
        self.engine = JMeterEngine(
            self.project_root
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @patch(
        "performance_engineering.engines.jmeter.adapter.subprocess.run"
    )
    def test_default_run_remains_strict(
        self,
        run_mock,
    ) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["dummy"],
            returncode=1,
        )

        with self.assertRaises(RuntimeError):
            self.engine._run(
                ["dummy"]
            )

    @patch(
        "performance_engineering.engines.jmeter.adapter.subprocess.run"
    )
    def test_sla_fail_can_be_explicitly_accepted(
        self,
        run_mock,
    ) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["dummy"],
            returncode=1,
        )

        self.engine._run(
            ["dummy"],
            allowed_returncodes=(0, 1),
        )

    @patch(
        "performance_engineering.engines.jmeter.adapter.subprocess.run"
    )
    def test_technical_failure_is_still_rejected(
        self,
        run_mock,
    ) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["dummy"],
            returncode=2,
        )

        with self.assertRaises(RuntimeError):
            self.engine._run(
                ["dummy"],
                allowed_returncodes=(0, 1),
            )

    @patch(
        "performance_engineering.engines.jmeter.adapter.subprocess.run"
    )
    def test_interruption_is_still_rejected(
        self,
        run_mock,
    ) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["dummy"],
            returncode=130,
        )

        with self.assertRaises(RuntimeError):
            self.engine._run(
                ["dummy"],
                allowed_returncodes=(0, 1),
            )


if __name__ == "__main__":
    unittest.main()
