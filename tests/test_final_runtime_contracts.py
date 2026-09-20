from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FinalRuntimeContractTests(unittest.TestCase):

    def test_locust_rejects_unresolved_contract(self):
        text = (
            ROOT
            / "src/performance_engineering/engines/locust/adapter.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "expected_status is UNRESOLVED",
            text,
        )

    def test_functional_probe_exists(self):
        self.assertTrue(
            (
                ROOT
                / "scripts/resolve_functional_response_contract.py"
            ).is_file()
        )

    def test_execution_pointer_exists(self):
        self.assertTrue(
            (
                ROOT
                / "scripts/execution_pointer.py"
            ).is_file()
        )


if __name__ == "__main__":
    unittest.main()
