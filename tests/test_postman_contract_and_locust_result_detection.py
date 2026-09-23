from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_workflow():
    path = (
        ROOT
        / "scripts"
        / "performance_workflow.py"
    )

    spec = importlib.util.spec_from_file_location(
        "_workflow_test",
        path,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(
        module
    )

    return module


class PostmanContractAndLocustDetectionTests(
    unittest.TestCase
):

    def test_postman_generator_does_not_default_to_200(
        self,
    ):
        text = (
            ROOT
            / "src"
            / "performance_engineering"
            / "design"
            / "compilers"
            / "postman_test_plan.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            '"expected_status": 200,',
            text,
        )

        self.assertIn(
            '"UNRESOLVED"',
            text,
        )

    def test_jmeter_result_identity(
        self,
    ):
        module = load_workflow()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = root / "results"
            results.mkdir()

            execution = (
                results
                / "20260920_061259_booking-e2e"
            )
            execution.mkdir()

            started_at = execution.stat().st_mtime

            resolved = (
                module.detect_new_execution_directory(
                    project_root=root,
                    before=set(),
                    started_at=started_at,
                    scenario="booking-e2e",
                    engine_name="jmeter",
                )
            )

            self.assertEqual(
                resolved,
                execution.resolve(),
            )

    def test_locust_result_identity(
        self,
    ):
        module = load_workflow()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = root / "results"
            results.mkdir()

            execution = (
                results
                / "locust-booking-e2e"
            )
            execution.mkdir()

            started_at = execution.stat().st_mtime

            resolved = (
                module.detect_new_execution_directory(
                    project_root=root,
                    before={
                        execution.resolve()
                    },
                    started_at=started_at,
                    scenario="booking-e2e",
                    engine_name="locust",
                )
            )

            self.assertEqual(
                resolved,
                execution.resolve(),
            )

    def test_existing_locust_directory_can_be_detected_by_mtime(
        self,
    ):
        module = load_workflow()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = root / "results"
            results.mkdir()

            execution = (
                results
                / "locust-booking-e2e"
            )
            execution.mkdir()

            marker = (
                execution
                / "locust_stats_history.csv"
            )
            marker.write_text(
                "Timestamp,User Count\n",
                encoding="utf-8",
            )

            started_at = marker.stat().st_mtime

            resolved = (
                module.detect_new_execution_directory(
                    project_root=root,
                    before={
                        execution.resolve()
                    },
                    started_at=started_at,
                    scenario="booking-e2e",
                    engine_name="locust",
                )
            )

            self.assertEqual(
                resolved,
                execution.resolve(),
            )

    def test_other_scenario_is_rejected(
        self,
    ):
        module = load_workflow()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = root / "results"
            results.mkdir()

            other = (
                results
                / "locust-other-e2e"
            )
            other.mkdir()

            resolved = (
                module.detect_new_execution_directory(
                    project_root=root,
                    before={
                        other.resolve()
                    },
                    started_at=other.stat().st_mtime,
                    scenario="booking-e2e",
                    engine_name="locust",
                )
            )

            self.assertIsNone(
                resolved
            )


if __name__ == "__main__":
    unittest.main()
