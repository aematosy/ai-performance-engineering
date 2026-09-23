from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ReportExecutionIdentityTests(unittest.TestCase):

    def test_finalizer_rejects_report_from_other_execution(self):
        module = load_module(
            "_finalizer_identity_test",
            ROOT / "scripts" / "finalize_execution_state.py",
        )

        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            (report_dir / "report-metadata.json").write_text(
                json.dumps({"execution_id": "old-run"}),
                encoding="utf-8",
            )

            self.assertFalse(
                module.report_matches_execution_id(
                    report_dir,
                    "current-run",
                )
            )
            self.assertTrue(
                module.report_matches_execution_id(
                    report_dir,
                    "old-run",
                )
            )

    def test_current_report_requires_same_execution_id(self):
        module = load_module(
            "_current_report_identity_test",
            ROOT / "scripts" / "current_execution_report.py",
        )

        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            (report_dir / "report-metadata.json").write_text(
                json.dumps({"execution_id": "run-2"}),
                encoding="utf-8",
            )

            self.assertFalse(
                module._report_matches_execution(
                    report_dir,
                    {"execution_id": "run-1"},
                )
            )
            self.assertTrue(
                module._report_matches_execution(
                    report_dir,
                    {"execution_id": "run-2"},
                )
            )


if __name__ == "__main__":
    unittest.main()
