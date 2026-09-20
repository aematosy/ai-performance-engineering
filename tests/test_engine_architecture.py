import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from performance_engineering.domain.engine import (
    PerformanceEngine,
)
from performance_engineering.domain.engine_type import (
    EngineType,
)
from performance_engineering.engines.jmeter import (
    JMeterEngine,
)
from performance_engineering.engines.locust import (
    LocustEngine,
)


class PerformanceEngineArchitectureTests(
    unittest.TestCase
):
    def test_jmeter_implements_engine_contract(
        self,
    ):
        engine = JMeterEngine(ROOT)

        self.assertIsInstance(
            engine,
            PerformanceEngine,
        )

        self.assertEqual(
            engine.name,
            EngineType.JMETER.value,
        )

    def test_locust_implements_engine_contract(
        self,
    ):
        engine = LocustEngine(ROOT)

        self.assertIsInstance(
            engine,
            PerformanceEngine,
        )

        self.assertEqual(
            engine.name,
            EngineType.LOCUST.value,
        )

    def test_engine_types_are_explicit(
        self,
    ):
        self.assertEqual(
            EngineType.JMETER.value,
            "jmeter",
        )

        self.assertEqual(
            EngineType.LOCUST.value,
            "locust",
        )


if __name__ == "__main__":
    unittest.main()
