#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml


class PlanGenerationError(RuntimeError):
    pass


def load_json(path: Path) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(
        path.read_text(
            encoding="utf-8"
        )
    )


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def write_yaml(
    path: Path,
    payload: dict,
) -> None:
    path.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            width=1000,
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate DRAFT performance test plan, "
            "Markdown companion and data requirements "
            "from an executable Postman scenario model."
        )
    )

    parser.add_argument(
        "--model",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--profile",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--csv",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--secrets-template",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--scenario",
        required=True,
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    model_path = (
        args.model
        .expanduser()
        .resolve()
    )

    profile_path = (
        args.profile
        .expanduser()
        .resolve()
    )

    csv_path = (
        args.csv
        .expanduser()
        .resolve()
    )

    secrets_template = (
        args.secrets_template
        .expanduser()
        .resolve()
    )

    output_dir = (
        args.output_dir
        .expanduser()
        .resolve()
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    model = load_json(
        model_path
    )

    profile = load_yaml(
        profile_path
    )

    requests = model.get(
        "requests",
        [],
    )

    if not requests:
        raise PlanGenerationError(
            "Executable model contains no requests."
        )

    execution = profile.get(
        "execution",
        {},
    )

    first_request = requests[0]

    host = str(
        first_request.get(
            "host",
            "",
        )
    )

    protocol = str(
        first_request.get(
            "protocol",
            "https",
        )
    )

    port = (
        first_request.get("port")
        or (
            443
            if protocol == "https"
            else 80
        )
    )

    transactions = []

    for request in requests:
        transactions.append(
            {
                "name": str(
                    request.get(
                        "id",
                        "HTTP Request",
                    )
                ),
                "method": str(
                    request.get(
                        "method",
                        "GET",
                    )
                ).upper(),
                "path": str(
                    request.get(
                        "path",
                        "/",
                    )
                ),
                "expected_status": (
                    request.get(
                        "expected_status"
                    )
                    if request.get(
                        "expected_status"
                    )
                    not in (
                        None,
                        "",
                        [],
                    )
                    else "UNRESOLVED"
                ),
            }
        )

    plan = {
        "metadata": {
            "name": args.scenario,
            "version": "1.0",
            "description": (
                "Performance Test Plan generated "
                "from Postman executable scenario."
            ),
            "created_at": utc_now(),
            "author": (
                "AI-Assisted Performance Engineering"
            ),
        },
        "status": "DRAFT",
        "source": {
            "type": "POSTMAN",
            "candidate_id": (
                model.get(
                    "scenario_candidate",
                    {},
                ).get("id")
            ),
            "candidate_type": (
                model.get(
                    "scenario_candidate",
                    {},
                ).get("type")
            ),
        },
        "objective": (
            "Validate the selected Postman scenario "
            "under a controlled baseline workload."
        ),
        "system": {
            "type": "API",
            "name": (
                model.get(
                    "source",
                    {},
                ).get(
                    "collection_name",
                    args.scenario,
                )
            ),
        },
        "environment": "demo",
        "target": {
            "protocol": protocol,
            "host": host,
            "port": int(port),
            "base_path": "",
        },
        "authentication": {
            "type": (
                "DYNAMIC"
                if model.get(
                    "secrets",
                    {}
                ).get(
                    "jmeter_properties"
                )
                else "NONE"
            ),
            "description": (
                "Authentication inferred from "
                "Postman executable model."
            ),
        },
        "workload": {
            "type": str(
                profile.get(
                    "profile",
                    {},
                ).get(
                    "name",
                    "BASELINE",
                )
            ).upper(),
            "status": "PROPOSED",
            "parameters": {
                "threads": int(
                    execution.get(
                        "threads",
                        1,
                    )
                ),
                "ramp_time_seconds": int(
                    execution.get(
                        "ramp_time_seconds",
                        1,
                    )
                ),
                "duration_seconds": int(
                    execution.get(
                        "duration_seconds",
                        30,
                    )
                ),
                "pacing_seconds": float(
                    execution.get(
                        "pacing_seconds",
                        0,
                    )
                ),
            },
            "description": (
                "Workload proposed from execution "
                "profile and requires human approval."
            ),
        },
        "sla": {
            "error_rate_threshold_pct": 1.0,
            "p95_threshold_ms": 1000,
            "p99_threshold_ms": 2000,
            "min_throughput_req_per_sec": 1.0,
            "source": "config/sla.json",
        },
        "data": {
            "requirements_file": (
                str(
                    output_dir
                    / "data-requirements.json"
                )
            ),
            "source_type": "PARAMETERIZED",
        },
        "transactions": transactions,
        "correlations": {
            "description": (
                "Runtime correlations generated "
                "from Postman dependency analysis."
            ),
            "extractors": model.get(
                "correlations",
                [],
            ),
        },
        "assertions": [
            {
                "type": "RESPONSE_CODE",
                "transaction": transaction["name"],
                "expected_value": str(
                    transaction["expected_status"]
                ),
                "description": (
                    "Validate expected HTTP response for "
                    + transaction["name"]
                    + "."
                ),
            }
            for transaction in transactions
            if transaction["expected_status"] != "UNRESOLVED"
        ],
        "observability": {
            "metrics": [
                {
                    "source": (
                        "JMeter Prometheus Listener"
                    ),
                    "endpoint": (
                        "http://localhost:9270/metrics"
                    ),
                },
                {
                    "source": "Prometheus",
                    "url": (
                        "http://localhost:9090"
                    ),
                },
                {
                    "source": "Grafana",
                    "url": (
                        "http://localhost:3000"
                    ),
                },
            ],
            "gaps": [],
        },
        "risks": [],
        "authorization": {
            "required": True,
            "status": "PENDING",
            "authorized_by": None,
            "authorized_at": None,
            "notes": None,
        },
        "open_questions": [],
        "approval": {
            "approved_by": None,
            "approved_at": None,
            "scope": None,
            "execution_authorized": False,
        },
    }

    candidate = model.get(
        "scenario_candidate",
        {},
    )

    data_requirements = {
        "schema_version": "1.0",
        "status": "DRAFT",
        "scenario": args.scenario,
        "scenario_candidate": {
            "id": candidate.get(
                "id"
            ),
            "type": candidate.get(
                "type"
            ),
        },
        "data_strategy": "CSV",
        "csv": {
            "file": str(
                csv_path
            ),
            "delimiter": ",",
            "encoding": "utf-8",
            "recycle": True,
            "stop_thread_on_eof": False,
            "sharing_mode": "all_threads",
        },
        "runtime_correlations": [],
        "secrets": [],
        "governance": {
            "secrets_in_csv": False,
            "runtime_correlations_in_csv": False,
        },
    }

    for request in requests:
        for extractor in request.get(
            "extractors",
            [],
        ):
            data_requirements[
                "runtime_correlations"
            ].append(
                {
                    "name": extractor.get(
                        "variable"
                    ),
                    "source_request": request.get(
                        "id"
                    ),
                    "type": "JSON_PATH",
                    "expression": extractor.get(
                        "json_path"
                    ),
                }
            )

    for name in (
        model.get(
            "secrets",
            {}
        ).get(
            "jmeter_properties",
            []
        )
    ):
        data_requirements[
            "secrets"
        ].append(
            {
                "name": name,
                "source": "JMETER_PROPERTY",
                "persist_value": False,
            }
        )

    plan_path = (
        output_dir
        / "test-plan.yaml"
    )

    md_path = (
        output_dir
        / "test-plan.md"
    )

    data_path = (
        output_dir
        / "data-requirements.json"
    )

    write_yaml(
        plan_path,
        plan,
    )

    data_path.write_text(
        json.dumps(
            data_requirements,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    markdown = [
        "# Performance Test Plan",
        "",
        f"Scenario: `{args.scenario}`",
        "",
        "Plan Status: DRAFT",
        "",
        "Workload Status: PROPOSED",
        "",
        "Authorization Status: PENDING",
        "",
        "Execution Authorized: False",
        "",
        "## Objective",
        "",
        plan["objective"],
        "",
        "## Target",
        "",
        (
            f"{protocol}://{host}:{port}"
        ),
        "",
        "## Transactions",
        "",
    ]

    for tx in transactions:
        markdown.append(
            (
                f"- `{tx['method']} "
                f"{tx['path']}` "
                f"({tx['name']})"
            )
        )

    markdown.extend(
        [
            "",
            "## Data",
            "",
            f"- CSV: `{csv_path}`",
            (
                "- Secrets template: "
                f"`{secrets_template}`"
            ),
            "",
            "## Governance",
            "",
            (
                "Design and workload require "
                "human approval before execution."
            ),
            (
                "Execution authorization is "
                "recorded separately."
            ),
            "",
        ]
    )

    md_path.write_text(
        "\n".join(markdown),
        encoding="utf-8",
    )

    print("=" * 78)
    print("POSTMAN TEST PLAN GENERATION")
    print("=" * 78)
    print(f"Scenario          : {args.scenario}")
    print(f"Transactions      : {len(transactions)}")
    print(f"Plan              : {plan_path}")
    print(f"Markdown          : {md_path}")
    print(f"Data requirements : {data_path}")
    print("Status            : DRAFT / PROPOSED")
    print("=" * 78)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
