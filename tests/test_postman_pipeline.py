#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "scripts" / "postman_pipeline.py"


class PostmanPipelineTests(unittest.TestCase):
    def test_help(self):
        result = subprocess.run(
            [sys.executable, str(PIPELINE), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--collection", result.stdout)
        self.assertIn("--candidate-id", result.stdout)


if __name__ == "__main__":
    unittest.main()
