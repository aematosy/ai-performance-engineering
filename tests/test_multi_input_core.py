#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DETECT = ROOT / "scripts" / "detect_input_type.py"
PARSE_JMX = ROOT / "scripts" / "parse_jmx.py"
VALIDATE = (
    ROOT
    / "scripts"
    / "validate_normalized_performance_model.py"
)


class MultiInputCoreTests(unittest.TestCase):
    def test_detect_postman(self):
        result = subprocess.run(
            [
                sys.executable,
                str(DETECT),
                "--input",
                "x.postman_collection.json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout.strip(),
            "POSTMAN",
        )

    def test_detect_jmx(self):
        result = subprocess.run(
            [
                sys.executable,
                str(DETECT),
                "--input",
                "x.jmx",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout.strip(),
            "JMX",
        )

    def test_parse_basic_jmx(self):
        jmx = """<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
  <hashTree>
    <TestPlan testname="Demo"/>
    <hashTree>
      <ThreadGroup testname="Users">
        <stringProp name="ThreadGroup.num_threads">${__P(threads,5)}</stringProp>
        <stringProp name="ThreadGroup.ramp_time">${__P(ramp_time,10)}</stringProp>
        <boolProp name="ThreadGroup.scheduler">true</boolProp>
        <stringProp name="ThreadGroup.duration">${__P(duration,60)}</stringProp>
      </ThreadGroup>
      <hashTree>
        <HTTPSamplerProxy testname="GET /ping">
          <stringProp name="HTTPSampler.domain">example.test</stringProp>
          <stringProp name="HTTPSampler.protocol">https</stringProp>
          <stringProp name="HTTPSampler.path">/ping</stringProp>
          <stringProp name="HTTPSampler.method">GET</stringProp>
        </HTTPSamplerProxy>
        <hashTree/>
      </hashTree>
    </hashTree>
  </hashTree>
</jmeterTestPlan>
"""

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            jmx_path = tmp / "demo.jmx"
            out = tmp / "model.json"

            jmx_path.write_text(
                jmx,
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(PARSE_JMX),
                    "--jmx",
                    str(jmx_path),
                    "--output",
                    str(out),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(
                result.returncode,
                0,
                result.stderr,
            )

            data = json.loads(
                out.read_text()
            )

            self.assertEqual(
                data["source"]["type"],
                "JMX",
            )

            self.assertEqual(
                data["summary"][
                    "transaction_count"
                ],
                1,
            )

            self.assertEqual(
                data["workload"][
                    "thread_groups"
                ][0]["threads"]["source"],
                "JMETER_PROPERTY",
            )

    def test_validator_accepts_valid_model(self):
        model = {
            "schema_version": "1.0",
            "source": {
                "type": "CLI",
            },
            "system": {
                "type": "API",
            },
            "scenarios": [
                {
                    "name": "demo",
                    "transactions": [
                        {
                            "name": "GET /ping",
                            "method": "GET",
                        }
                    ],
                }
            ],
            "data": {},
            "runtime": {},
            "workload": {},
            "assertions": [],
            "observability": [],
            "risks": [],
            "findings": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "model.json"
            p.write_text(
                json.dumps(model)
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATE),
                    "--input",
                    str(p),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )


if __name__ == "__main__":
    unittest.main()
