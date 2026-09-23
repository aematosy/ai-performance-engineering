from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


UNKNOWN_TARGETS = {
    "",
    "none",
    "not specified",
    "not_specified",
    "unknown",
    "n/a",
}


@dataclass(frozen=True)
class ReportScope:
    scenario: str
    objective: str
    system: str
    target: str
    transaction_count: int

    @property
    def scope_label(self) -> str:
        if self.transaction_count == 1:
            return "1 transacción"
        return f"{self.transaction_count} transacciones"


def normalize_scenario_name(
    scenario: str,
) -> str:
    value = str(
        scenario or ""
    ).strip()

    for prefix in (
        "locust-",
        "jmeter-",
    ):
        if value.startswith(
            prefix
        ):
            value = value[
                len(prefix):
            ]

    return value


def load_plan(
    *,
    project_root: Path,
    scenario: str,
) -> dict[str, Any] | None:
    normalized = normalize_scenario_name(
        scenario
    )

    if not normalized:
        return None

    path = (
        project_root
        / "tests"
        / "plans"
        / normalized
        / "test-plan.yaml"
    )

    if not path.is_file():
        return None

    payload = yaml.safe_load(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        payload,
        dict,
    ):
        return None

    return payload


def _target_base_url(
    target: dict[str, Any],
) -> str | None:
    protocol = str(
        target.get(
            "protocol",
            "https",
        )
    ).strip()

    host = str(
        target.get(
            "host",
            "",
        )
    ).strip()

    if not protocol or not host:
        return None

    port = target.get(
        "port"
    )

    try:
        numeric_port = (
            int(port)
            if port is not None
            else None
        )
    except (
        TypeError,
        ValueError,
    ):
        numeric_port = None

    port_text = ""

    if numeric_port is not None:
        default_port = (
            protocol == "https"
            and numeric_port == 443
        ) or (
            protocol == "http"
            and numeric_port == 80
        )

        if not default_port:
            port_text = (
                f":{numeric_port}"
            )

    base_path = str(
        target.get(
            "base_path",
            "",
        )
        or ""
    ).strip()

    normalized_base_path = (
        "/" + base_path.strip("/")
        if base_path.strip("/")
        else ""
    )

    return (
        f"{protocol}://{host}"
        f"{port_text}"
        f"{normalized_base_path}"
    )


def _single_transaction_target(
    *,
    base_url: str,
    transaction: dict[str, Any],
) -> str | None:
    method = str(
        transaction.get(
            "method",
            "",
        )
    ).strip().upper()

    path = str(
        transaction.get(
            "path",
            "",
        )
        or ""
    ).strip()

    if not method:
        return None

    full_url = (
        base_url.rstrip("/")
        + (
            "/" + path.lstrip("/")
            if path
            else ""
        )
    )

    return f"{method} {full_url}"


def build_target_from_plan(
    plan: dict[str, Any],
) -> str | None:
    target = (
        plan.get(
            "target"
        )
        or {}
    )

    if not isinstance(
        target,
        dict,
    ):
        return None

    base_url = _target_base_url(
        target
    )

    if not base_url:
        return None

    transactions = (
        plan.get(
            "transactions"
        )
        or []
    )

    transactions = [
        tx
        for tx in transactions
        if isinstance(tx, dict)
    ]

    if len(transactions) == 1:
        single = _single_transaction_target(
            base_url=base_url,
            transaction=transactions[0],
        )
        return single or base_url

    # A multi-transaction scenario must not be represented by its first
    # request. The report target is the evaluated system/base endpoint;
    # individual requests belong in the transaction breakdown.
    return base_url


def resolve_report_scope(
    *,
    project_root: Path,
    scenario: str,
    explicit_target: str | None = None,
    explicit_objective: str | None = None,
) -> ReportScope:
    normalized_scenario = (
        normalize_scenario_name(
            scenario
        )
        or str(scenario or "").strip()
        or "Performance Test"
    )

    plan = load_plan(
        project_root=project_root,
        scenario=scenario,
    )

    explicit = str(
        explicit_target
        or ""
    ).strip()

    explicit_is_valid = (
        explicit
        and explicit.lower()
        not in UNKNOWN_TARGETS
    )

    if plan is None:
        target = (
            explicit
            if explicit_is_valid
            else "Not specified"
        )
        objective = str(
            explicit_objective
            or ""
        ).strip() or (
            "Validar el comportamiento de performance "
            f"del escenario {normalized_scenario}."
        )
        return ReportScope(
            scenario=normalized_scenario,
            objective=objective,
            system="Not specified",
            target=target,
            transaction_count=0,
        )

    transactions = [
        tx
        for tx in (
            plan.get("transactions")
            or []
        )
        if isinstance(tx, dict)
    ]

    derived_target = (
        build_target_from_plan(plan)
        or "Not specified"
    )

    # REPORT_TARGET_SCOPE_V2
    #
    # A multi-transaction scenario represents a system/journey,
    # not its first HTTP request. Some engines may provide an
    # explicit target corresponding to the first sampler
    # (for example POST /auth). That value must not override
    # the scenario-level target in the report.
    #
    # For a single transaction, an explicit target remains
    # meaningful and is preserved.
    if len(transactions) > 1:
        target = derived_target
    elif explicit_is_valid:
        target = explicit
    else:
        target = derived_target

    system_payload = (
        plan.get("system")
        or {}
    )
    system = (
        str(
            system_payload.get("name", "")
        ).strip()
        if isinstance(system_payload, dict)
        else ""
    ) or "Not specified"

    objective = str(
        explicit_objective
        or ""
    ).strip()

    if not objective:
        if len(transactions) == 1:
            tx = transactions[0]
            method = str(
                tx.get("method", "")
            ).strip().upper()
            path = str(
                tx.get("path", "")
                or ""
            ).strip()
            transaction_label = (
                f"{method} {path}".strip()
                or str(
                    tx.get("name", "")
                ).strip()
                or normalized_scenario
            )
            objective = (
                "Validar el comportamiento de performance de "
                f"{transaction_label}."
            )
        else:
            objective = (
                "Validar el comportamiento de performance "
                f"del escenario {normalized_scenario} "
                "bajo el workload aprobado."
            )

    return ReportScope(
        scenario=normalized_scenario,
        objective=objective,
        system=system,
        target=target,
        transaction_count=len(transactions),
    )


def resolve_report_target(
    *,
    project_root: Path,
    scenario: str,
    explicit_target: str | None = None,
) -> str:
    return resolve_report_scope(
        project_root=project_root,
        scenario=scenario,
        explicit_target=explicit_target,
    ).target


def format_percentage(
    value: Any,
) -> str:
    try:
        number = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return str(
            value
        )

    return f"{number:.2f}"


def format_latency(
    value: Any,
) -> str:
    try:
        number = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return str(
            value
        )

    return f"{number:.2f}"


def format_throughput(
    value: Any,
) -> str:
    try:
        number = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return str(
            value
        )

    return f"{number:.3f}"
