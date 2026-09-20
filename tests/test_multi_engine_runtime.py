from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from performance_engineering.application.engine_runtime import (
    EngineResolutionError,
    persist_engine_in_profile,
    read_engine_from_profile,
    resolve_engine,
)
from performance_engineering.engines.jmeter.adapter import (
    JMeterEngine,
)
from performance_engineering.engines.locust.adapter import (
    LocustEngine,
)


class MultiEngineRuntimeTests(
    unittest.TestCase
):
    def setUp(self):
        self.root = Path.cwd()

    def test_resolves_jmeter(self):
        engine = resolve_engine(
            project_root=self.root,
            engine_name="jmeter",
        )

        self.assertIsInstance(
            engine,
            JMeterEngine,
        )

    def test_resolves_locust(self):
        engine = resolve_engine(
            project_root=self.root,
            engine_name="locust",
        )

        self.assertIsInstance(
            engine,
            LocustEngine,
        )

    def test_rejects_unknown_engine(self):
        with self.assertRaises(
            EngineResolutionError
        ):
            resolve_engine(
                project_root=self.root,
                engine_name="gatling",
            )

    def test_engine_is_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = (
                Path(tmp)
                / "execution-profile.yaml"
            )

            profile.write_text(
                yaml.safe_dump(
                    {
                        "execution": {
                            "threads": 10,
                            "ramp_time_seconds": 100,
                            "duration_seconds": 120,
                            "pacing_seconds": 2,
                        }
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            persist_engine_in_profile(
                profile_path=profile,
                engine_name="locust",
            )

            self.assertEqual(
                read_engine_from_profile(
                    profile
                ),
                "locust",
            )

            payload = yaml.safe_load(
                profile.read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                payload["execution"]["threads"],
                10,
            )

    def test_engine_cannot_silently_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = (
                Path(tmp)
                / "execution-profile.yaml"
            )

            profile.write_text(
                yaml.safe_dump(
                    {
                        "engine": "locust",
                        "execution": {
                            "threads": 1,
                            "ramp_time_seconds": 1,
                            "duration_seconds": 1,
                            "pacing_seconds": 1,
                        },
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(
                EngineResolutionError
            ):
                persist_engine_in_profile(
                    profile_path=profile,
                    engine_name="jmeter",
                )


if __name__ == "__main__":
    unittest.main()
