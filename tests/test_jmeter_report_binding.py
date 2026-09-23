from __future__ import annotations

import json
from pathlib import Path

from performance_engineering.reporting.report_context import (
    resolve_report_scope,
)


ROOT = Path(__file__).resolve().parents[1]


def test_multitransaction_target_ignores_first_request_override(
    tmp_path,
):
    plans = (
        tmp_path
        / "tests"
        / "plans"
        / "multi"
    )
    plans.mkdir(parents=True)

    plan = plans / "test-plan.yaml"

    plan.write_text(
        """
scenario:
  name: multi
system:
  name: Demo API
target:
  protocol: https
  host: api.example.com
  port: 443
  base_path: ""
transactions:
  - name: Auth
    method: POST
    path: /auth
  - name: Read
    method: GET
    path: /resource
""".strip()
        + "\n",
        encoding="utf-8",
    )

    scope = resolve_report_scope(
        project_root=tmp_path,
        scenario="multi",
        explicit_target=(
            "POST https://api.example.com/auth"
        ),
    )

    assert scope.transaction_count == 2
    assert scope.target == "https://api.example.com"


def test_single_transaction_keeps_explicit_target(
    tmp_path,
):
    plans = (
        tmp_path
        / "tests"
        / "plans"
        / "single"
    )
    plans.mkdir(parents=True)

    plan = plans / "test-plan.yaml"

    plan.write_text(
        """
scenario:
  name: single
system:
  name: Demo API
target:
  protocol: https
  host: api.example.com
  port: 443
  base_path: ""
transactions:
  - name: Read
    method: GET
    path: /resource
""".strip()
        + "\n",
        encoding="utf-8",
    )

    scope = resolve_report_scope(
        project_root=tmp_path,
        scenario="single",
        explicit_target=(
            "GET https://api.example.com/resource"
        ),
    )

    assert scope.transaction_count == 1
    assert (
        scope.target
        == "GET https://api.example.com/resource"
    )


def test_jmeter_workflow_writes_execution_bound_metadata():
    source = (
        ROOT
        / "scripts"
        / "performance_workflow.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "write_jmeter_report_metadata" in source
    assert '"execution_id"' in source
    assert '"source_stats_sha256"' in source
    assert '"analysis_sha256"' in source
    assert '"report_sha256"' in source
    assert '"engine": "JMETER"' in source
