from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

from performance_engineering.application.engine_runtime import (
    EngineResolutionError,
    normalize_engine_name,
    persist_engine_in_profile,
    read_engine_from_profile,
)


OPTIONS = (
    ("jmeter", "JMeter"),
    ("locust", "Locust"),
)


class EngineSelectionError(RuntimeError):
    """Raised when engine selection cannot be completed safely."""


def _interactive_supported() -> bool:
    return (
        sys.stdin.isatty()
        and sys.stdout.isatty()
        and os.name == "posix"
    )


def _render(
    selected: int,
) -> None:
    print(
        "\033[2J\033[H",
        end="",
    )

    print("=" * 64)
    print("PERFORMANCE ENGINE SELECTION")
    print("=" * 64)
    print()
    print(
        "Selecciona el motor que ejecutará "
        "esta prueba:"
    )
    print()

    for index, (_, label) in enumerate(OPTIONS):
        prefix = "❯" if index == selected else " "

        if index == selected:
            print(
                f"\033[1;36m{prefix} {label}\033[0m"
            )
        else:
            print(
                f"{prefix} {label}"
            )

    print()
    print(
        "↑/↓ seleccionar  •  Enter confirmar  •  q cancelar"
    )


def _interactive_select() -> str:
    if not _interactive_supported():
        raise EngineSelectionError(
            "Interactive engine selection requires a TTY. "
            "Use --engine jmeter or --engine locust."
        )

    import termios
    import tty

    selected = 0

    stdin_fd = sys.stdin.fileno()
    previous = termios.tcgetattr(
        stdin_fd
    )

    try:
        tty.setcbreak(
            stdin_fd
        )

        while True:
            _render(
                selected
            )

            char = sys.stdin.read(1)

            if char in (
                "\r",
                "\n",
            ):
                return OPTIONS[
                    selected
                ][0]

            if char.lower() == "q":
                raise EngineSelectionError(
                    "Engine selection cancelled."
                )

            if char == "\x1b":
                sequence = (
                    sys.stdin.read(2)
                )

                if sequence == "[A":
                    selected = (
                        selected - 1
                    ) % len(OPTIONS)

                elif sequence == "[B":
                    selected = (
                        selected + 1
                    ) % len(OPTIONS)

    finally:
        termios.tcsetattr(
            stdin_fd,
            termios.TCSADRAIN,
            previous,
        )

        print(
            "\033[2J\033[H",
            end="",
        )


def select_engine(
    *,
    profile_path: Path,
    requested_engine: str | None,
    allow_change: bool = False,
) -> str:
    profile_path = (
        profile_path
        .expanduser()
        .resolve()
    )

    if not profile_path.is_file():
        raise EngineSelectionError(
            "Execution profile not found: "
            f"{profile_path}"
        )

    if requested_engine:
        selected = normalize_engine_name(
            requested_engine
        )
    else:
        selected = (
            _interactive_select()
        )

    try:
        persist_engine_in_profile(
            profile_path=profile_path,
            engine_name=selected,
            allow_change=allow_change,
        )
    except EngineResolutionError as exc:
        raise EngineSelectionError(
            str(exc)
        ) from exc

    persisted = read_engine_from_profile(
        profile_path
    )

    if persisted != selected:
        raise EngineSelectionError(
            "Persisted engine does not match "
            "the selected engine."
        )

    return persisted


def describe_selection(
    *,
    profile_path: Path,
    engine_name: str,
) -> None:
    print()
    print("=" * 64)
    print("PERFORMANCE ENGINE SELECTED")
    print("=" * 64)
    print(
        f"Engine  : {engine_name}"
    )
    print(
        f"Profile : {profile_path.resolve()}"
    )
    print(
        "Status  : PERSISTED"
    )
    print("=" * 64)
