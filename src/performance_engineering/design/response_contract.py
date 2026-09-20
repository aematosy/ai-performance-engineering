from __future__ import annotations

from typing import Any


class ResponseContractError(ValueError):
    """Raised when an executable HTTP response contract is ambiguous."""


def normalize_expected_status(
    raw: Any,
    *,
    context: str,
) -> list[int]:
    """
    Normalize an explicitly declared HTTP response contract.

    Important:
    - We NEVER infer 200 from the HTTP method.
    - We NEVER infer 201 from POST.
    - Absence of a contract is an error before executable generation.
    """

    if raw is None:
        raise ResponseContractError(
            f"{context}: expected HTTP status is not declared. "
            "Declare the expected response status explicitly."
        )

    if isinstance(raw, int):
        values = [raw]

    elif isinstance(raw, str):
        value = raw.strip()

        if not value:
            raise ResponseContractError(
                f"{context}: expected HTTP status is empty."
            )

        try:
            values = [int(value)]
        except ValueError as exc:
            raise ResponseContractError(
                f"{context}: invalid expected HTTP status: {raw!r}"
            ) from exc

    elif isinstance(raw, (list, tuple)):
        if not raw:
            raise ResponseContractError(
                f"{context}: expected HTTP status is not declared."
            )

        values = []

        for item in raw:
            try:
                values.append(int(item))
            except (TypeError, ValueError) as exc:
                raise ResponseContractError(
                    f"{context}: invalid expected HTTP status: {item!r}"
                ) from exc

    else:
        raise ResponseContractError(
            f"{context}: unsupported expected_status contract: "
            f"{type(raw).__name__}"
        )

    for status in values:
        if status < 100 or status > 599:
            raise ResponseContractError(
                f"{context}: HTTP status out of range: {status}"
            )

    return values
