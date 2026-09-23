from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from performance_engineering.application.engine_runtime import (
    EngineResolutionError,
    persist_engine_in_profile,
    read_engine_from_profile,
)


class ExplicitEngineSwitchTests(
    unittest.TestCase
):

    def create_profile(
        self,
        root: Path,
    ) -> Path:
        path = (
            root
            / "execution-profile.yaml"
        )

        path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": "1.0",
                    "execution": {
                        "mode": "DURATION",
                        "threads": 10,
                        "ramp_time_seconds": 100,
                        "duration_seconds": 180,
                        "pacing_seconds": 2.0,
                    },
                    "engine": "jmeter",
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        return path

    def test_silent_change_remains_blocked(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            profile = self.create_profile(
                Path(tmp)
            )

            with self.assertRaises(
                EngineResolutionError
            ):
                persist_engine_in_profile(
                    profile_path=profile,
                    engine_name="locust",
                )

            self.assertEqual(
                read_engine_from_profile(
                    profile
                ),
                "jmeter",
            )

    def test_explicit_change_is_allowed(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            profile = self.create_profile(
                Path(tmp)
            )

            persist_engine_in_profile(
                profile_path=profile,
                engine_name="locust",
                allow_change=True,
            )

            self.assertEqual(
                read_engine_from_profile(
                    profile
                ),
                "locust",
            )

    def test_workload_is_not_modified(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            profile = self.create_profile(
                Path(tmp)
            )

            before = yaml.safe_load(
                profile.read_text(
                    encoding="utf-8"
                )
            )["execution"]

            persist_engine_in_profile(
                profile_path=profile,
                engine_name="locust",
                allow_change=True,
            )

            after = yaml.safe_load(
                profile.read_text(
                    encoding="utf-8"
                )
            )["execution"]

            self.assertEqual(
                before,
                after,
            )


if __name__ == "__main__":
    unittest.main()
