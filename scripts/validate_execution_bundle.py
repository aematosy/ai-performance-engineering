#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


class BundleValidationError(RuntimeError):
    pass


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BundleValidationError(f"File not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise BundleValidationError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise BundleValidationError(f"YAML root must be an object: {path}")

    return data


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BundleValidationError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BundleValidationError(
            f"Invalid JSON in {path}: line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(data, dict):
        raise BundleValidationError(f"JSON root must be an object: {path}")

    return data


def slug(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "-",
        str(value or "").strip().lower(),
    ).strip("-")


def _nonempty_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def plan_scenario_id(plan: dict[str, Any]) -> str:
    """
    Resolve scenario identity from supported Performance Test Plan shapes.

    Current canonical project shape:
      metadata:
        name: create-post-demo

    Backward-compatible shapes are also accepted:
      scenario: create-post-demo
      scenario:
        id: ...
        name: ...
      scenario_id: ...
      name: ...
      metadata:
        scenario: ...
        scenario_id: ...
        name: ...
      plan:
        scenario: ...
        scenario_id: ...
        name: ...
    """
    scenario = plan.get("scenario")

    direct = _nonempty_string(scenario)
    if direct:
        return direct

    if isinstance(scenario, dict):
        for key in ("id", "name", "scenario_id"):
            direct = _nonempty_string(scenario.get(key))
            if direct:
                return direct

    for key in ("scenario_id", "name"):
        direct = _nonempty_string(plan.get(key))
        if direct:
            return direct

    metadata = plan.get("metadata")
    if isinstance(metadata, dict):
        for key in ("scenario", "scenario_id", "name"):
            direct = _nonempty_string(metadata.get(key))
            if direct:
                return direct

    plan_section = plan.get("plan")
    if isinstance(plan_section, dict):
        for key in ("scenario", "scenario_id", "name"):
            value = plan_section.get(key)

            direct = _nonempty_string(value)
            if direct:
                return direct

            if isinstance(value, dict):
                for nested_key in ("id", "name", "scenario_id"):
                    direct = _nonempty_string(value.get(nested_key))
                    if direct:
                        return direct

    raise BundleValidationError(
        "Unable to resolve scenario identity from test plan. "
        "Expected metadata.name or another supported scenario field."
    )


def plan_source_binding(plan: dict[str, Any]) -> dict[str, Any] | None:
    binding = plan.get("source_binding")
    if isinstance(binding, dict):
        return binding

    source = plan.get("source")
    if isinstance(source, dict):
        if any(
            key in source
            for key in (
                "candidate_id",
                "scenario_candidate_id",
            )
        ):
            return source

    metadata = plan.get("metadata")
    if isinstance(metadata, dict):
        source_binding = metadata.get("source_binding")
        if isinstance(source_binding, dict):
            return source_binding

    return None


def context_candidate_id(context: dict[str, Any]) -> str:
    candidate = context.get("scenario_candidate")
    if not isinstance(candidate, dict):
        raise BundleValidationError(
            "Design context does not contain scenario_candidate."
        )

    value = _nonempty_string(candidate.get("id"))
    if not value:
        raise BundleValidationError(
            "Design context scenario_candidate.id is missing."
        )

    return value


def requirements_candidate_id(requirements: dict[str, Any]) -> str:
    candidate = requirements.get("scenario_candidate")
    if not isinstance(candidate, dict):
        raise BundleValidationError(
            "Data requirements do not contain scenario_candidate."
        )

    value = _nonempty_string(candidate.get("id"))
    if not value:
        raise BundleValidationError(
            "Data requirements scenario_candidate.id is missing."
        )

    return value


def jmx_metadata_scenario(metadata: dict[str, Any]) -> str:
    for path in (
        ("scenario",),
        ("scenario_id",),
        ("plan", "scenario"),
        ("plan", "scenario_id"),
        ("metadata", "name"),
    ):
        current: Any = metadata
        valid = True

        for key in path:
            if not isinstance(current, dict) or key not in current:
                valid = False
                break
            current = current[key]

        if not valid:
            continue

        direct = _nonempty_string(current)
        if direct:
            return direct

        if isinstance(current, dict):
            for key in ("id", "name", "scenario_id"):
                direct = _nonempty_string(current.get(key))
                if direct:
                    return direct

    raise BundleValidationError(
        "Unable to resolve scenario identity from JMX metadata."
    )


def binding_candidate_id(binding: dict[str, Any]) -> str | None:
    for key in ("candidate_id", "scenario_candidate_id"):
        value = _nonempty_string(binding.get(key))
        if value:
            return value
    return None


def add_finding(
    findings: list[dict[str, str]],
    severity: str,
    code: str,
    message: str,
) -> None:
    findings.append(
        {
            "severity": severity,
            "code": code,
            "message": message,
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate coherence of plan, design context, data requirements "
            "and JMX metadata before execution."
        )
    )

    parser.add_argument("--plan", required=True)
    parser.add_argument("--design-context")
    parser.add_argument("--data-requirements")
    parser.add_argument("--jmx")
    parser.add_argument(
        "--require-explicit-source-binding",
        action="store_true",
        help=(
            "When a design context is supplied, require the plan to declare "
            "source_binding.candidate_id (or equivalent supported binding)."
        ),
    )

    args = parser.parse_args()

    plan_path = Path(args.plan).expanduser().resolve()
    context_path = (
        Path(args.design_context).expanduser().resolve()
        if args.design_context
        else None
    )
    requirements_path = (
        Path(args.data_requirements).expanduser().resolve()
        if args.data_requirements
        else None
    )
    jmx_path = (
        Path(args.jmx).expanduser().resolve()
        if args.jmx
        else None
    )

    findings: list[dict[str, str]] = []

    try:
        plan = load_yaml(plan_path)
        plan_scenario = plan_scenario_id(plan)
        binding = plan_source_binding(plan)

        context_candidate = None
        requirements_candidate = None
        metadata_scenario = None

        if context_path is not None:
            context = load_json(context_path)
            context_candidate = context_candidate_id(context)

            if binding is None:
                severity = (
                    "ERROR"
                    if args.require_explicit_source_binding
                    else "INFO"
                )

                add_finding(
                    findings,
                    severity,
                    "BUNDLE-PLAN-SOURCE-BINDING-MISSING",
                    (
                        "A design context was supplied but the test plan "
                        "does not explicitly bind to a source candidate."
                        if severity == "ERROR"
                        else
                        "Plan has no explicit source candidate binding; "
                        "candidate coherence cannot be proven from the plan alone."
                    ),
                )
            else:
                bound_candidate = binding_candidate_id(binding)

                if bound_candidate is None:
                    if args.require_explicit_source_binding:
                        add_finding(
                            findings,
                            "ERROR",
                            "BUNDLE-PLAN-CANDIDATE-ID-MISSING",
                            "Plan source binding does not contain candidate_id.",
                        )
                elif bound_candidate != context_candidate:
                    add_finding(
                        findings,
                        "ERROR",
                        "BUNDLE-PLAN-CONTEXT-CANDIDATE-MISMATCH",
                        "Plan is bound to candidate "
                        f"'{bound_candidate}' but design context is "
                        f"'{context_candidate}'.",
                    )

        if requirements_path is not None:
            requirements = load_json(requirements_path)
            requirements_candidate = requirements_candidate_id(requirements)

            if context_candidate is not None:
                if requirements_candidate != context_candidate:
                    add_finding(
                        findings,
                        "ERROR",
                        "BUNDLE-CONTEXT-DATA-CANDIDATE-MISMATCH",
                        "Design context candidate "
                        f"'{context_candidate}' differs from data requirements "
                        f"candidate '{requirements_candidate}'.",
                    )
            else:
                add_finding(
                    findings,
                    "INFO",
                    "BUNDLE-DATA-CANDIDATE-NO-CONTEXT",
                    "Data requirements contain a candidate identity but no "
                    "design context was supplied for comparison.",
                )

        if jmx_path is not None:
            metadata_path = Path(str(jmx_path) + ".meta.json")

            if not metadata_path.exists():
                add_finding(
                    findings,
                    "ERROR",
                    "BUNDLE-JMX-METADATA-MISSING",
                    f"JMX metadata file is missing: {metadata_path}",
                )
            else:
                metadata = load_json(metadata_path)
                metadata_scenario = jmx_metadata_scenario(metadata)

                if slug(metadata_scenario) != slug(plan_scenario):
                    add_finding(
                        findings,
                        "ERROR",
                        "BUNDLE-PLAN-JMX-SCENARIO-MISMATCH",
                        "Plan scenario "
                        f"'{plan_scenario}' differs from JMX metadata scenario "
                        f"'{metadata_scenario}'.",
                    )

        errors = [
            item
            for item in findings
            if item["severity"] == "ERROR"
        ]

        infos = [
            item
            for item in findings
            if item["severity"] == "INFO"
        ]

        status = "BLOCKED" if errors else "PASS"

    except BundleValidationError as exc:
        print("=" * 72)
        print("EXECUTION BUNDLE COHERENCE")
        print("=" * 72)
        print("Status : BLOCKED")
        print(f"Error  : {exc}")
        print("=" * 72)
        return 2

    print("=" * 72)
    print("EXECUTION BUNDLE COHERENCE v1.1")
    print("=" * 72)
    print(f"Status              : {status}")
    print(f"Plan scenario       : {plan_scenario}")
    print(
        "Context candidate  : "
        f"{context_candidate if context_candidate else 'NOT PROVIDED'}"
    )
    print(
        "Data candidate     : "
        f"{requirements_candidate if requirements_candidate else 'NOT PROVIDED'}"
    )
    print(
        "JMX scenario       : "
        f"{metadata_scenario if metadata_scenario else 'NOT PROVIDED'}"
    )
    print(f"Errors              : {len(errors)}")
    print(f"Info                : {len(infos)}")

    for item in findings:
        print()
        print(f"[{item['severity']}] {item['code']}")
        print(f"  {item['message']}")

    print("=" * 72)

    if status == "PASS":
        print("EXECUTION BUNDLE COHERENT")
        return 0

    print(
        "EXECUTION BLOCKED: ARTIFACTS DO NOT BELONG "
        "TO THE SAME APPROVED SCENARIO"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
