#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from normalize_design_contract import (
    ContractNormalizationError,
    is_unresolved,
    load_plan,
    normalize_observability,
    set_transaction_status,
    sync_markdown,
    sync_open_questions,
    transaction_label,
    write_plan,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--plan",
        required=True,
        type=Path,
    )

    return parser


def ask_status(
    label: str,
) -> int:
    print()
    print(
        "Hay un dato funcional pendiente antes "
        "de poder ejecutar la prueba."
    )
    print()
    print(
        f"Operación: {label}"
    )
    print(
        "El input original no indicó qué código "
        "HTTP debe considerarse exitoso."
    )
    print()
    print(
        "Definirlo permitirá validar las respuestas "
        "durante la prueba."
    )
    print(
        "Esto todavía NO ejecutará carga y NO cambiará "
        "el workload ni el target."
    )
    print()

    while True:
        raw = input(
            "¿Qué código HTTP esperas recibir? "
        ).strip()

        try:
            status = int(
                raw
            )
        except ValueError:
            print(
                "Ingresa un código HTTP numérico "
                "entre 100 y 599."
            )
            continue

        if 100 <= status <= 599:
            return status

        print(
            "El código debe estar entre "
            "100 y 599."
        )


def main() -> int:
    args = build_parser().parse_args()

    plan_path = (
        args.plan
        .expanduser()
        .resolve()
    )

    try:
        plan = load_plan(
            plan_path
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

        unresolved = [
            index
            for index, transaction
            in enumerate(
                transactions
            )
            if isinstance(
                transaction,
                dict,
            )
            and is_unresolved(
                transaction.get(
                    "expected_status"
                )
            )
        ]

        if not unresolved:
            print(
                "HTTP response contract: RESOLVED"
            )
            return 0

        for index in unresolved:
            transaction = transactions[
                index
            ]

            status = ask_status(
                transaction_label(
                    transaction
                )
            )

            set_transaction_status(
                plan,
                index=index,
                expected_status=status,
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

    except (
        ContractNormalizationError,
        OSError,
        yaml.YAMLError,
    ) as exc:
        print(
            f"No se pudo resolver el contrato HTTP: {exc}"
        )
        return 2

    print()
    print(
        "Contrato HTTP actualizado correctamente."
    )
    print(
        "No se ejecutó carga."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
