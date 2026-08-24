#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCHER = ROOT / "scripts" / "harden_execution_entrypoints.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "entrypoint_hardening_v11",
        PATCHER,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ExecutionEntrypointHardeningV11Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_find_target_block_handles_shell_continuation(self):
        text = (
            "run-demo: validate-jmx\n"
            "\t@read answer; \\\n"
            "\tif [ \"$$answer\" = \"RUN\" ]; then echo ok; fi\n"
            "status:\n"
            "\t@echo status\n"
        )
        start, end = self.module.find_target_block(text, "run-demo")
        block = text[start:end]
        self.assertIn("@read", block)
        self.assertNotIn("status:", block)

    def test_makefile_patch_replaces_legacy_flow(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Makefile"
            path.write_text(
                'PYTHON=poetry run python\n'
                'PLAN ?= tests/plans/demo/test-plan.yaml\n'
                'JMX ?= tests/generated/demo.jmx\n\n'
                'validate-jmx:\n'
                '\t@echo ok\n\n'
                'run-demo: validate-jmx\n'
                '\t$(PYTHON) scripts/run_approved_plan.py --plan "$(PLAN)" --jmx "$(JMX)" --preflight\n'
                '\t@read -r -p "Type RUN to authorize exactly the preflight parameters: " answer; \\\n'
                '\tif [ "$$answer" != "RUN" ]; then echo "Execution cancelled."; exit 2; fi\n'
                '\t$(PYTHON) scripts/run_approved_plan.py --plan "$(PLAN)" --jmx "$(JMX)" --authorized\n\n'
                'status:\n'
                '\t@echo status\n',
                encoding="utf-8",
            )

            self.module.patch_makefile(path)
            text = path.read_text(encoding="utf-8")

            self.assertIn("PROFILE ?=", text)
            self.assertIn("RUN_MANIFEST ?=", text)
            self.assertIn("preflight-demo:", text)
            self.assertIn("authorize-demo:", text)
            self.assertIn("--execute", text)
            self.assertNotIn("Type RUN to authorize exactly", text)
            self.assertNotIn("run_approved_plan.py --plan \"$(PLAN)\" --jmx \"$(JMX)\" --authorized", text)
            self.assertIn("status:", text)

    def test_contract_mentions_controlled_modes(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "execution-contract.md"
            path.write_text("legacy\n", encoding="utf-8")
            self.module.patch_execution_contract(path)
            text = path.read_text(encoding="utf-8")
            self.assertIn("--preflight", text)
            self.assertIn("--execute", text)
            self.assertIn("internal compatibility", text)

    def test_guidance_adds_controlled_section(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "README.md"
            path.write_text("# Demo\n", encoding="utf-8")
            self.module.patch_guidance_file(path)
            text = path.read_text(encoding="utf-8")
            self.assertIn("## Controlled execution entry point", text)
            self.assertIn("Type RUN", text)


if __name__ == "__main__":
    unittest.main()
