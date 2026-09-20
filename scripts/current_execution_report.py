#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

STATE_DIR = (
    ROOT
    / "results"
    / ".state"
)

EXECUTION_POINTER = (
    STATE_DIR
    / "last-execution.json"
)

REPORT_POINTER = (
    STATE_DIR
    / "last-report.json"
)


def read_json(
    path: Path,
) -> dict:
    if not path.is_file():
        raise RuntimeError(
            f"No existe el puntero requerido: {path}"
        )

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(payload, dict):
        raise RuntimeError(
            f"Puntero inválido: {path}"
        )

    return payload


def resolve_report_dir(
    execution: dict,
) -> Path:
    scenario = str(
        execution.get(
            "scenario",
            ""
        )
    ).strip()

    if not scenario:
        raise RuntimeError(
            "El execution pointer no contiene scenario."
        )

    reports_root = (
        ROOT
        / "reports"
    )

    if not reports_root.is_dir():
        raise RuntimeError(
            "No existe reports/."
        )

    candidates = []

    for directory in reports_root.iterdir():
        if not directory.is_dir():
            continue

        html = (
            directory
            / "executive-report.html"
        )

        pdf = (
            directory
            / "executive-report.pdf"
        )

        if not html.is_file() \
            and not pdf.is_file():
            continue

        matched = False

        for artifact in (
            html,
            pdf,
        ):
            if not artifact.is_file():
                continue

            try:
                if artifact.suffix == ".html":
                    text = artifact.read_text(
                        encoding="utf-8",
                        errors="ignore",
                    )

                    if scenario in text:
                        matched = True
                        break
            except Exception:
                pass

        if scenario in directory.name:
            matched = True

        if matched:
            candidates.append(
                directory
            )

    if not candidates:
        raise RuntimeError(
            "No existe un reporte profesional para "
            f"la ejecución actual: {scenario}"
        )

    candidates.sort(
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )

    return candidates[0].resolve()


def command_current() -> int:
    execution = read_json(
        EXECUTION_POINTER
    )

    report_dir = resolve_report_dir(
        execution
    )

    print(
        report_dir
    )

    return 0


def command_write(
    report_dir_value: str,
) -> int:
    execution = read_json(
        EXECUTION_POINTER
    )

    report_dir = Path(
        report_dir_value
    )

    if not report_dir.is_absolute():
        report_dir = (
            ROOT
            / report_dir
        )

    report_dir = report_dir.resolve()

    if not report_dir.is_dir():
        raise RuntimeError(
            f"Report directory does not exist: {report_dir}"
        )

    STATE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "scenario": execution.get(
            "scenario"
        ),
        "engine": execution.get(
            "engine"
        ),
        "results": execution.get(
            "results"
        ),
        "report_dir": str(
            report_dir
        ),
    }

    REPORT_POINTER.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        report_dir
    )

    return 0


def command_read() -> int:
    payload = read_json(
        REPORT_POINTER
    )

    report_dir = payload.get(
        "report_dir"
    )

    if not report_dir:
        raise RuntimeError(
            "last-report.json no contiene report_dir."
        )

    path = Path(
        str(report_dir)
    )

    if not path.is_dir():
        raise RuntimeError(
            "El reporte apuntado ya no existe: "
            f"{path}"
        )

    print(
        path
    )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()

    sub = parser.add_subparsers(
        dest="operation",
        required=True,
    )

    sub.add_parser(
        "current"
    )

    sub.add_parser(
        "read"
    )

    write = sub.add_parser(
        "write"
    )

    write.add_argument(
        "--report-dir",
        required=True,
    )

    args = parser.parse_args()

    if args.operation == "current":
        return command_current()

    if args.operation == "read":
        return command_read()

    return command_write(
        args.report_dir
    )


if __name__ == "__main__":
    try:
        raise SystemExit(
            main()
        )
    except Exception as exc:
        print(
            f"REPORT POINTER ERROR: {exc}",
            file=__import__("sys").stderr,
        )

        raise SystemExit(
            2
        )
