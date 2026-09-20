from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(
    __file__
).resolve().parents[1]

NORMALIZER = (
    ROOT
    / "scripts"
    / "normalize_design_contract.py"
)

VALIDATOR = (
    ROOT
    / "scripts"
    / "validate_test_plan.py"
)

BASE_PLAN = (
    ROOT
    / "tests"
    / "plans"
    / "create-post-demo"
    / "test-plan.yaml"
)


def load_normalizer():
    spec = (
        importlib.util
        .spec_from_file_location(
            "normalize_design_contract",
            NORMALIZER,
        )
    )

    assert spec is not None
    assert spec.loader is not None

    module = (
        importlib.util
        .module_from_spec(
            spec
        )
    )

    spec.loader.exec_module(
        module
    )

    return module


class NaturalResponseContractTests(
    unittest.TestCase
):
    def setUp(self):
        if not BASE_PLAN.is_file():
            self.skipTest(
                "create-post-demo fixture not available"
            )

        self.module = (
            load_normalizer()
        )

    def test_unresolved_contract_is_design_valid(self):
        with tempfile.TemporaryDirectory(
            dir=ROOT / "tests" / "plans"
        ) as directory:
            target = (
                Path(directory)
                / "test-plan.yaml"
            )

            plan = yaml.safe_load(
                BASE_PLAN.read_text(
                    encoding="utf-8"
                )
            )

            plan[
                "transactions"
            ][0][
                "expected_status"
            ] = "UNRESOLVED"

            plan["assertions"] = [
                item
                for item
                in plan.get(
                    "assertions",
                    []
                )
                if str(
                    item.get(
                        "type",
                        "",
                    )
                ).upper()
                != "RESPONSE_CODE"
            ]

            target.write_text(
                yaml.safe_dump(
                    plan,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        VALIDATOR
                    ),
                    "--plan",
                    str(
                        target
                    ),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                0,
                msg=(
                    completed.stdout
                    + completed.stderr
                ),
            )

            self.assertIn(
                "PLAN VALID",
                completed.stdout,
            )

    def test_http_zero_is_rejected(self):
        with tempfile.TemporaryDirectory(
            dir=ROOT / "tests" / "plans"
        ) as directory:
            target = (
                Path(directory)
                / "test-plan.yaml"
            )

            plan = yaml.safe_load(
                BASE_PLAN.read_text(
                    encoding="utf-8"
                )
            )

            plan[
                "transactions"
            ][0][
                "expected_status"
            ] = 0

            target.write_text(
                yaml.safe_dump(
                    plan,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        VALIDATOR
                    ),
                    "--plan",
                    str(
                        target
                    ),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(
                completed.returncode,
                0,
            )

    def test_unresolved_removes_response_assertion(self):
        plan = yaml.safe_load(
            BASE_PLAN.read_text(
                encoding="utf-8"
            )
        )

        self.module.force_unresolved(
            plan
        )

        self.assertEqual(
            plan[
                "transactions"
            ][0][
                "expected_status"
            ],
            "UNRESOLVED",
        )

        response_assertions = [
            item
            for item
            in plan.get(
                "assertions",
                []
            )
            if str(
                item.get(
                    "type",
                    "",
                )
            ).upper()
            == "RESPONSE_CODE"
        ]

        self.assertEqual(
            response_assertions,
            [],
        )

    def test_design_observability_is_engine_neutral(self):
        plan = yaml.safe_load(
            BASE_PLAN.read_text(
                encoding="utf-8"
            )
        )

        self.module.normalize_observability(
            plan
        )

        metrics = plan.get(
            "observability",
            {},
        ).get(
            "metrics",
            [],
        )

        sources = [
            str(
                metric.get(
                    "source",
                    "",
                )
            ).lower()
            for metric in metrics
            if isinstance(
                metric,
                dict,
            )
        ]

        self.assertFalse(
            any(
                "jmeter"
                in source
                for source in sources
            )
        )

        self.assertFalse(
            any(
                "locust"
                in source
                for source in sources
            )
        )

        self.assertTrue(
            any(
                "prometheus"
                == source
                for source in sources
            )
        )

        self.assertTrue(
            any(
                "grafana"
                == source
                for source in sources
            )
        )


if __name__ == "__main__":
    unittest.main()
