#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


UNRESOLVED = "UNRESOLVED"
QUESTION_PREFIX = "[RESPONSE_CONTRACT]"
ENGINE_GAP = (
    "Engine-specific metrics are configured only after "
    "JMeter or Locust is selected."
)


class ContractNormalizationError(RuntimeError):
    pass


def load_plan(
    path: Path,
) -> dict[str, Any]:
    if not path.is_file():
        raise ContractNormalizationError(
            f"Plan not found: {path}"
        )

    payload = yaml.safe_load(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise ContractNormalizationError(
            "Plan root must be a YAML mapping."
        )

    return payload


def write_plan(
    path: Path,
    plan: dict[str, Any],
) -> None:
    path.write_text(
        yaml.safe_dump(
            plan,
            sort_keys=False,
            allow_unicode=True,
            width=1000,
        ),
        encoding="utf-8",
    )


def is_unresolved(
    value: Any,
) -> bool:
    return (
        isinstance(
            value,
            str,
        )
        and value.strip().upper()
        == UNRESOLVED
    )


def validate_http_status(
    value: Any,
) -> int:
    try:
        status = int(value)
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ContractNormalizationError(
            "Expected HTTP status must be an integer "
            "between 100 and 599."
        ) from exc

    if not 100 <= status <= 599:
        raise ContractNormalizationError(
            "Expected HTTP status must be between "
            "100 and 599."
        )

    return status


def transaction_label(
    transaction: dict[str, Any],
) -> str:
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
    ).strip()

    return (
        f"{method} {path}"
    ).strip()


def remove_response_code_assertions(
    plan: dict[str, Any],
) -> None:
    assertions = plan.get(
        "assertions"
    )

    if not isinstance(
        assertions,
        list,
    ):
        plan["assertions"] = []
        return

    plan["assertions"] = [
        item
        for item in assertions
        if not (
            isinstance(
                item,
                dict,
            )
            and str(
                item.get(
                    "type",
                    "",
                )
            ).strip().upper()
            == "RESPONSE_CODE"
        )
    ]


def add_response_code_assertion(
    plan: dict[str, Any],
    *,
    transaction: dict[str, Any],
    expected_status: int,
) -> None:
    assertions = plan.get(
        "assertions"
    )

    if not isinstance(
        assertions,
        list,
    ):
        assertions = []

    assertions = [
        item
        for item in assertions
        if not (
            isinstance(
                item,
                dict,
            )
            and str(
                item.get(
                    "type",
                    "",
                )
            ).strip().upper()
            == "RESPONSE_CODE"
        )
    ]

    assertions.append(
        {
            "type":
                "RESPONSE_CODE",
            "expected_value":
                str(expected_status),
            "description":
                (
                    "Validate expected HTTP response "
                    f"for transaction "
                    f"{transaction_label(transaction)}."
                ),
        }
    )

    plan["assertions"] = assertions


def normalize_observability(
    plan: dict[str, Any],
) -> None:
    observability = plan.get(
        "observability"
    )

    if not isinstance(
        observability,
        dict,
    ):
        observability = {}
        plan["observability"] = (
            observability
        )

    metrics = observability.get(
        "metrics"
    )

    if not isinstance(
        metrics,
        list,
    ):
        metrics = []

    neutral_metrics = []

    for metric in metrics:
        if not isinstance(
            metric,
            dict,
        ):
            continue

        source = str(
            metric.get(
                "source",
                "",
            )
        ).strip().lower()

        if (
            "jmeter"
            in source
            or "locust"
            in source
        ):
            continue

        neutral_metrics.append(
            metric
        )

    observability[
        "metrics"
    ] = neutral_metrics

    gaps = observability.get(
        "gaps"
    )

    if not isinstance(
        gaps,
        list,
    ):
        gaps = []

    if ENGINE_GAP not in gaps:
        gaps.append(
            ENGINE_GAP
        )

    observability[
        "gaps"
    ] = gaps


def sync_open_questions(
    plan: dict[str, Any],
) -> None:
    questions = plan.get(
        "open_questions"
    )

    if not isinstance(
        questions,
        list,
    ):
        questions = []

    questions = [
        item
        for item in questions
        if not str(
            item
        ).startswith(
            QUESTION_PREFIX
        )
    ]

    transactions = plan.get(
        "transactions"
    )

    if isinstance(
        transactions,
        list,
    ):
        for transaction in transactions:
            if not isinstance(
                transaction,
                dict,
            ):
                continue

            if is_unresolved(
                transaction.get(
                    "expected_status"
                )
            ):
                questions.append(
                    (
                        f"{QUESTION_PREFIX} "
                        "Define the expected HTTP status "
                        "before performance execution for "
                        f"{transaction_label(transaction)}."
                    )
                )

    plan[
        "open_questions"
    ] = questions


def force_unresolved(
    plan: dict[str, Any],
) -> None:
    transactions = plan.get(
        "transactions"
    )

    if not isinstance(
        transactions,
        list,
    ) or not transactions:
        raise ContractNormalizationError(
            "Plan must contain at least one transaction."
        )

    for transaction in transactions:
        if not isinstance(
            transaction,
            dict,
        ):
            continue

        transaction[
            "expected_status"
        ] = UNRESOLVED

    remove_response_code_assertions(
        plan
    )


def force_explicit_status(
    plan: dict[str, Any],
    expected_status: int,
) -> None:
    expected_status = (
        validate_http_status(
            expected_status
        )
    )

    transactions = plan.get(
        "transactions"
    )

    if not isinstance(
        transactions,
        list,
    ) or not transactions:
        raise ContractNormalizationError(
            "Plan must contain at least one transaction."
        )

    for transaction in transactions:
        if not isinstance(
            transaction,
            dict,
        ):
            continue

        transaction[
            "expected_status"
        ] = expected_status

    if len(
        transactions
    ) == 1 and isinstance(
        transactions[0],
        dict,
    ):
        add_response_code_assertion(
            plan,
            transaction=transactions[0],
            expected_status=expected_status,
        )


def set_transaction_status(
    plan: dict[str, Any],
    *,
    index: int,
    expected_status: int,
) -> None:
    expected_status = (
        validate_http_status(
            expected_status
        )
    )

    transactions = plan.get(
        "transactions"
    )

    if not isinstance(
        transactions,
        list,
    ):
        raise ContractNormalizationError(
            "transactions must be a list."
        )

    try:
        transaction = transactions[
            index
        ]
    except IndexError as exc:
        raise ContractNormalizationError(
            f"Transaction index not found: {index}"
        ) from exc

    if not isinstance(
        transaction,
        dict,
    ):
        raise ContractNormalizationError(
            "Transaction must be a mapping."
        )

    transaction[
        "expected_status"
    ] = expected_status

    # The current canonical plan keeps RESPONSE_CODE
    # assertions at root level. For the current single-
    # transaction contract we can synchronize it directly.
    if len(
        transactions
    ) == 1:
        add_response_code_assertion(
            plan,
            transaction=transaction,
            expected_status=expected_status,
        )


def sync_markdown(
    plan_path: Path,
    plan: dict[str, Any],
) -> None:
    md_path = plan_path.with_suffix(
        ".md"
    )

    if not md_path.is_file():
        return

    transactions = plan.get(
        "transactions"
    )

    first_status: Any = None

    if (
        isinstance(
            transactions,
            list,
        )
        and transactions
        and isinstance(
            transactions[0],
            dict,
        )
    ):
        first_status = (
            transactions[0].get(
                "expected_status"
            )
        )

    lines = md_path.read_text(
        encoding="utf-8"
    ).splitlines()

    output: list[str] = []
    skip_metric_detail = False

    for line in lines:
        lower = line.lower()

        if (
            "jmeter prometheus listener"
            in lower
            or "locust metrics"
            in lower
        ):
            skip_metric_detail = True
            continue

        if skip_metric_detail:
            stripped = line.strip().lower()

            if (
                "endpoint:"
                in stripped
                or "9270"
                in stripped
            ):
                continue

            skip_metric_detail = False

        if (
            "expected status:"
            in lower
            and first_status
            is not None
        ):
            prefix = line.split(
                "Expected status:",
                1,
            )[0]

            if prefix == line:
                prefix = line.split(
                    "expected status:",
                    1,
                )[0]

            line = (
                prefix
                + "Expected status: "
                + f"`{first_status}`"
            )

        output.append(
            line
        )

    md_path.write_text(
        "\n".join(
            output
        ).rstrip()
        + "\n",
        encoding="utf-8",
    )


def normalize(
    *,
    plan_path: Path,
    unresolved: bool,
    expected_status: int | None,
) -> dict[str, Any]:
    plan = load_plan(
        plan_path
    )

    if unresolved:
        force_unresolved(
            plan
        )

    if expected_status is not None:
        force_explicit_status(
            plan,
            expected_status,
        )

    normalize_observability(
        plan
    )

    sync_open_questions(
        plan
    )

    write_plan(
        plan_path,
        plan,
    )

    sync_markdown(
        plan_path,
        plan,
    )

    return plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize engine-neutral design and "
            "HTTP response-contract semantics."
        )
    )

    parser.add_argument(
        "--plan",
        required=True,
        type=Path,
    )

    group = (
        parser.add_mutually_exclusive_group()
    )

    group.add_argument(
        "--unresolved",
        action="store_true",
    )

    group.add_argument(
        "--expected-status",
        type=int,
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    plan_path = (
        args.plan
        .expanduser()
        .resolve()
    )

    try:
        plan = normalize(
            plan_path=plan_path,
            unresolved=args.unresolved,
            expected_status=(
                args.expected_status
            ),
        )

    except (
        ContractNormalizationError,
        OSError,
        yaml.YAMLError,
    ) as exc:
        print(
            f"CONTRACT NORMALIZATION FAILED: {exc}"
        )
        return 2

    transactions = plan.get(
        "transactions",
        [],
    )

    unresolved_count = sum(
        1
        for transaction in transactions
        if isinstance(
            transaction,
            dict,
        )
        and is_unresolved(
            transaction.get(
                "expected_status"
            )
        )
    )

    print(
        "=" * 62
    )
    print(
        "DESIGN CONTRACT NORMALIZED"
    )
    print(
        "=" * 62
    )
    print(
        f"Unresolved HTTP contracts : "
        f"{unresolved_count}"
    )
    print(
        "Engine-specific metrics   : "
        "NOT INCLUDED IN DESIGN"
    )
    print(
        "Performance load          : "
        "NOT EXECUTED"
    )
    print(
        "=" * 62
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
