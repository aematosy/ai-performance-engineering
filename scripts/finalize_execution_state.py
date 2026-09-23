#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RESULTS_ROOT = (
    ROOT
    / "results"
)

REPORTS_ROOT = (
    ROOT
    / "reports"
)

STATE_ROOT = (
    RESULTS_ROOT
    / ".state"
)

EXECUTION_POINTER = (
    STATE_ROOT
    / "last-execution.json"
)

REPORT_POINTER = (
    STATE_ROOT
    / "last-report.json"
)


def parse_scenario(
    values: list[str],
) -> str:
    for index, value in enumerate(values):
        if value == "--scenario":
            if index + 1 >= len(values):
                break

            return values[
                index + 1
            ].strip()

    for value in values:
        if not value.startswith("-"):
            return value.strip()

    raise RuntimeError(
        "No se pudo resolver el scenario "
        "desde la invocación natural."
    )


def execution_directory_activity_mtime(
    path: Path,
) -> float:
    latest = 0.0

    try:
        latest = path.stat().st_mtime
    except OSError:
        return latest

    for child in path.rglob("*"):
        if not child.is_file():
            continue

        try:
            latest = max(
                latest,
                child.stat().st_mtime,
            )
        except OSError:
            continue

    return latest


def candidate_result_dirs(
    scenario: str,
) -> list[Path]:
    if not RESULTS_ROOT.is_dir():
        return []

    candidates = []

    for path in RESULTS_ROOT.iterdir():
        if not path.is_dir():
            continue

        if path.name == ".state":
            continue

        if scenario not in path.name:
            continue

        candidates.append(
            path.resolve()
        )

    # Result directories can be reused (Locust) or newly created
    # (JMeter). Directory mtime alone is therefore not a reliable
    # execution identity. Rank by the most recent activity inside
    # the directory so the pointer follows the engine that actually
    # produced files during the just-completed execution.
    candidates.sort(
        key=execution_directory_activity_mtime,
        reverse=True,
    )

    return candidates


def resolve_engine(
    result_dir: Path,
) -> str:
    name = result_dir.name.lower()

    if "locust" in name:
        return "LOCUST"

    if "jmeter" in name:
        return "JMETER"

    if list(
        result_dir.glob(
            "*_stats.csv"
        )
    ):
        return "LOCUST"

    if list(
        result_dir.rglob(
            "*.jtl"
        )
    ):
        return "JMETER"

    return "UNKNOWN"


def write_execution(
    scenario: str,
    result_dir: Path,
) -> dict:
    engine = resolve_engine(
        result_dir
    )

    execution_id = None
    metadata_path = result_dir / "metadata.json"

    if metadata_path.is_file():
        try:
            metadata = json.loads(
                metadata_path.read_text(encoding="utf-8")
            )
            if isinstance(metadata, dict):
                execution_id = metadata.get("execution_id")
        except (OSError, json.JSONDecodeError):
            execution_id = None

    payload = {
        "scenario": scenario,
        "engine": engine,
        "results": str(
            result_dir
        ),
        "completed_at": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
    }

    if execution_id:
        payload["execution_id"] = str(execution_id)

    STATE_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    EXECUTION_POINTER.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return payload


def report_matches_scenario(
    directory: Path,
    scenario: str,
) -> bool:
    if scenario in directory.name:
        return True

    html = (
        directory
        / "executive-report.html"
    )

    if not html.is_file():
        return False

    try:
        text = html.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except OSError:
        return False

    return scenario in text


def report_matches_execution_id(
    directory: Path,
    execution_id: str | None,
) -> bool:
    if not execution_id:
        return True

    metadata_path = directory / "report-metadata.json"

    if not metadata_path.is_file():
        return False

    try:
        payload = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return False

    if not isinstance(payload, dict):
        return False

    return str(payload.get("execution_id") or "") == execution_id


def resolve_report(
    scenario: str,
) -> Path | None:
    if not REPORTS_ROOT.is_dir():
        return None

    # First resolve the report deterministically from the
    # execution result identity.
    #
    # JMeter:
    #   results/<timestamp>_<scenario>
    #   reports/<timestamp>_<scenario>
    #
    # Locust:
    #   results/locust-<scenario>
    #   reports/locust-<scenario>
    #
    # Do not select another engine's report merely because
    # its directory mtime is newer.
    if EXECUTION_POINTER.is_file():
        try:
            execution = json.loads(
                EXECUTION_POINTER.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            execution = {}

        if isinstance(
            execution,
            dict,
        ):
            execution_scenario = str(
                execution.get(
                    "scenario",
                    "",
                )
                or ""
            ).strip()

            results_value = str(
                execution.get(
                    "results",
                    "",
                )
                or ""
            ).strip()

            execution_id = str(
                execution.get(
                    "execution_id",
                    "",
                )
                or ""
            ).strip() or None

            if (
                execution_scenario == scenario
                and results_value
            ):
                result_name = Path(
                    results_value
                ).name

                preferred = (
                    REPORTS_ROOT
                    / result_name
                )

                if (
                    preferred.is_dir()
                    and (
                        preferred
                        / "executive-report.html"
                    ).is_file()
                    and report_matches_execution_id(
                        preferred,
                        execution_id,
                    )
                ):
                    return preferred.resolve()

    candidates = []
    current_execution_id = None

    if EXECUTION_POINTER.is_file():
        try:
            current_execution = json.loads(
                EXECUTION_POINTER.read_text(encoding="utf-8")
            )
            if isinstance(current_execution, dict):
                current_execution_id = str(
                    current_execution.get("execution_id") or ""
                ).strip() or None
        except (OSError, json.JSONDecodeError):
            current_execution_id = None

    for directory in REPORTS_ROOT.iterdir():
        if not directory.is_dir():
            continue

        if not (
            directory
            / "executive-report.html"
        ).is_file():
            continue

        if (
            report_matches_scenario(
                directory,
                scenario,
            )
            and report_matches_execution_id(
                directory,
                current_execution_id,
            )
        ):
            candidates.append(
                directory.resolve()
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )

    return candidates[0]


def write_report_pointer(
    execution: dict,
    report_dir: Path,
) -> None:
    payload = dict(
        execution
    )

    payload[
        "report_dir"
    ] = str(
        report_dir
    )

    REPORT_POINTER.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    # This utility receives the original natural-execution arguments.
    # Do not parse them as this script's own CLI contract.
    #
    # Supported examples:
    #
    #   finalize_execution_state.py -- --scenario demo
    #   finalize_execution_state.py --scenario demo
    #   finalize_execution_state.py demo
    #
    values = list(
        sys.argv[1:]
    )

    if (
        values
        and values[0] == "--"
    ):
        values = values[1:]

    scenario = parse_scenario(
        values
    )

    result_dirs = candidate_result_dirs(
        scenario
    )

    if not result_dirs:
        raise RuntimeError(
            "La ejecución terminó pero no se encontró "
            f"un results directory para {scenario}."
        )

    result_dir = result_dirs[0]

    execution = write_execution(
        scenario,
        result_dir,
    )

    print(
        "[OK] Execution pointer:",
        EXECUTION_POINTER,
    )

    print(
        "[OK] Scenario:",
        scenario,
    )

    print(
        "[OK] Engine:",
        execution["engine"],
    )

    print(
        "[OK] Results:",
        result_dir,
    )

    report_dir = resolve_report(
        scenario
    )

    if report_dir is None:
        REPORT_POINTER.unlink(
            missing_ok=True
        )

        print(
            "[INFO] Professional report bundle "
            "not generated yet."
        )

        return 0

    write_report_pointer(
        execution,
        report_dir,
    )

    print(
        "[OK] Report pointer:",
        REPORT_POINTER,
    )

    print(
        "[OK] Report:",
        report_dir,
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            main()
        )
    except Exception as exc:
        print(
            "EXECUTION FINALIZER ERROR:",
            exc,
            file=__import__(
                "sys"
            ).stderr,
        )

        raise SystemExit(
            2
        )
