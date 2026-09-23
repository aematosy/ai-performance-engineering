from __future__ import annotations

import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExecutionPointerActivityTests(unittest.TestCase):

    def test_finalizer_ranks_reused_directory_by_file_activity(self):
        path = ROOT / "scripts" / "finalize_execution_state.py"
        spec = importlib.util.spec_from_file_location("finalizer", path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_dir = root / "locust-demo"
            new_dir = root / "20260101_000000_demo"
            old_dir.mkdir()
            new_dir.mkdir()

            old_file = old_dir / "locust_stats.csv"
            new_file = new_dir / "results.jtl"
            old_file.write_text("old", encoding="utf-8")
            new_file.write_text("new", encoding="utf-8")

            now = time.time()
            os.utime(old_dir, (now - 100, now - 100))
            os.utime(new_dir, (now - 10, now - 10))
            os.utime(new_file, (now - 10, now - 10))
            os.utime(old_file, (now, now))

            self.assertGreater(
                module.execution_directory_activity_mtime(old_dir),
                module.execution_directory_activity_mtime(new_dir),
            )


if __name__ == "__main__":
    unittest.main()
