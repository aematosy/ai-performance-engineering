#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_SCRIPTS = [
    "config_loader.py", "validate_environment.py", "generate_jmx.py",
    "generate_jmx_from_plan.py", "validate_jmx_artifact.py", "run_approved_plan.py",
    "review_test_plan.py", "validate_test_plan.py", "approve_test_plan.py",
    "run_test.py", "analyze_results.py", "generate_report.py",
    "history_manager.py", "trend_analyzer.py", "intelligence_engine.py",
]
REQUIRED_SKILLS = [
    "chief-performance-engineer", "performance-engineer",
    "performance-results-analyst", "performance-test-designer",
    "performance-test-runner",
]


class SmokeFailure(RuntimeError):
    pass


def ok(name: str, detail: str = "") -> None:
    print(f"[OK]   {name}" + (f" | {detail}" if detail else ""))


def fail(name: str, detail: str) -> None:
    print(f"[FAIL] {name} | {detail}")
    raise SmokeFailure(f"{name}: {detail}")


def check_file(relative: str) -> Path:
    path = ROOT / relative
    if not path.is_file():
        fail(relative, "missing")
    ok(relative)
    return path


def run_command(name: str, command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        fail(name, detail[-1] if detail else f"exit={result.returncode}")
    ok(name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Non-load smoke test for the demo.")
    parser.add_argument("--plan", default="tests/plans/create-post-demo/test-plan.yaml")
    parser.add_argument("--jmx", default="tests/generated/create-post-demo.jmx")
    args = parser.parse_args()

    print("=" * 70)
    print("AI PERFORMANCE ENGINEERING - DEMO SMOKE TEST")
    print("=" * 70)
    print("Mode: validation only; JMeter load is NOT executed.\n")

    try:
        for relative in [
            "GEMINI.md", "pyproject.toml", "poetry.lock",
            "config/project-config.yaml", "config/sla.json",
            "config/agent-registry.yaml", "docker-compose.yml", "prometheus.yml",
        ]:
            check_file(relative)
        for script in REQUIRED_SCRIPTS:
            check_file(f"scripts/{script}")
        for skill in REQUIRED_SKILLS:
            path = check_file(f".gemini/skills/{skill}/SKILL.md")
            if f"name: {skill}" not in path.read_text(encoding="utf-8"):
                fail(f"skill:{skill}", "frontmatter name mismatch")
            ok(f"skill:{skill}:frontmatter")

        config = yaml.safe_load((ROOT / "config/project-config.yaml").read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            fail("project-config", "YAML root is not a mapping")
        ok("project-config YAML")

        registry = yaml.safe_load((ROOT / "config/agent-registry.yaml").read_text(encoding="utf-8"))
        agents = set((registry or {}).get("agents", {}).keys())
        missing = set(REQUIRED_SKILLS) - agents
        if missing:
            fail("agent-registry", f"missing: {sorted(missing)}")
        ok("agent-registry")

        plan_path = (ROOT / args.plan).resolve()
        if not plan_path.is_file():
            fail("test plan", f"missing: {plan_path}")
        plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
        ok("test plan YAML", f"{plan.get('metadata', {}).get('name')} | {plan.get('status')}")

        data_file = plan.get("data", {}).get("requirements_file")
        if data_file:
            json.loads((ROOT / data_file).read_text(encoding="utf-8"))
            ok("data requirements JSON")
        check_file(str((plan_path.parent / "test-plan.md").relative_to(ROOT)))

        run_command("deterministic plan review", [
            sys.executable, "scripts/review_test_plan.py", "--plan", str(plan_path), "--strict"
        ])
        run_command("deterministic plan validation", [
            sys.executable, "scripts/validate_test_plan.py", "--plan", str(plan_path)
        ])

        jmx_path = (ROOT / args.jmx).resolve()
        if not jmx_path.is_file():
            fail("JMX", f"missing: {jmx_path}")
        ET.parse(jmx_path)
        ok("JMX XML", str(jmx_path.relative_to(ROOT)))

        run_command("JMX artifact provenance", [
            sys.executable, "scripts/validate_jmx_artifact.py",
            "--plan", str(plan_path), "--jmx", str(jmx_path)
        ])

        result = subprocess.run(["docker", "info"], cwd=ROOT, capture_output=True, text=True)
        if result.returncode != 0:
            fail("Docker daemon", "not available")
        ok("Docker daemon")

        result = subprocess.run(["docker", "compose", "config", "--quiet"], cwd=ROOT, capture_output=True, text=True)
        if result.returncode != 0:
            fail("Docker Compose config", (result.stderr or result.stdout).strip() or "invalid")
        ok("Docker Compose config")

    except (SmokeFailure, OSError, ValueError, KeyError, json.JSONDecodeError, yaml.YAMLError, ET.ParseError) as exc:
        print("\n" + "=" * 70)
        print("SMOKE TEST: FAIL")
        print("=" * 70)
        if not isinstance(exc, SmokeFailure):
            print(exc)
        return 2

    print("\n" + "=" * 70)
    print("SMOKE TEST: PASS")
    print("JMX provenance: VALID")
    print("No performance load was executed.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
