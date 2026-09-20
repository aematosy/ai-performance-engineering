#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "scripts" / "performance_workflow.py"


class NaturalExecutionError(RuntimeError):
    pass


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise NaturalExecutionError(
            f"No se encontró el archivo requerido: {path}"
        )

    payload = yaml.safe_load(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(payload, dict):
        raise NaturalExecutionError(
            f"El archivo no contiene un objeto YAML válido: {path}"
        )

    return payload


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def run_workflow(
    operation: str,
    *arguments: str,
    input_text: str | None = None,
) -> None:
    command = [
        sys.executable,
        str(WORKFLOW),
        operation,
        *arguments,
    ]

    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        input=input_text,
        check=False,
    )

    if completed.returncode != 0:
        raise NaturalExecutionError(
            f"La etapa {operation} terminó con código "
            f"{completed.returncode}."
        )


def plan_status(plan: Path) -> tuple[str, str, str]:
    payload = load_yaml(plan)

    status = str(
        payload.get(
            "status",
            "",
        )
    ).upper()

    workload = str(
        payload.get(
            "workload",
            {},
        ).get(
            "status",
            "",
        )
    ).upper()

    authorization = str(
        payload.get(
            "authorization",
            {},
        ).get(
            "status",
            "",
        )
    ).upper()

    return (
        status,
        workload,
        authorization,
    )


def profile_engine(profile: Path) -> str:
    payload = load_yaml(profile)

    return str(
        payload.get(
            "engine",
            "",
        )
    ).strip().lower()


def artifact_for(
    scenario: str,
    engine: str,
) -> Path:
    if engine == "jmeter":
        return (
            ROOT
            / "tests"
            / "generated"
            / f"{scenario}.jmx"
        )

    if engine == "locust":
        return (
            ROOT
            / "tests"
            / "generated"
            / "locust"
            / scenario
            / "locustfile.py"
        )

    raise NaturalExecutionError(
        f"Motor no soportado: {engine or 'NO DEFINIDO'}"
    )


def manifest_is_current(
    manifest_path: Path,
    plan: Path,
    profile: Path,
    artifact: Path,
    engine: str,
) -> bool:
    if (
        not manifest_path.is_file()
        or not artifact.is_file()
    ):
        return False

    try:
        manifest = json.loads(
            manifest_path.read_text(
                encoding="utf-8"
            )
        )

        if (
            manifest.get("schema_version")
            != "3.0"
        ):
            return False

        if (
            manifest.get("status")
            != "PRE_EXECUTION_READY"
        ):
            return False

        if (
            manifest.get("execution_performed")
            is not False
        ):
            return False

        if (
            str(
                manifest.get(
                    "engine",
                    "",
                )
            ).lower()
            != engine
        ):
            return False

        inputs = manifest["inputs"]

        expected = {
            "plan": plan.resolve(),
            "profile": profile.resolve(),
            "engine_artifact": artifact.resolve(),
        }

        for key, expected_path in expected.items():
            record = inputs[key]

            actual_path = Path(
                record["path"]
            ).resolve()

            if actual_path != expected_path:
                return False

            if (
                record["sha256"]
                != sha256(expected_path)
            ):
                return False

    except (
        OSError,
        KeyError,
        ValueError,
        json.JSONDecodeError,
    ):
        return False

    return True


def transaction_summary(
    plan: Path,
    profile: Path,
) -> None:
    plan_data = load_yaml(plan)
    profile_data = load_yaml(profile)

    metadata = plan_data.get(
        "metadata",
        {},
    )

    target = plan_data.get(
        "target",
        {},
    )

    workload = plan_data.get(
        "workload",
        {},
    )

    params = workload.get(
        "parameters",
        {},
    )

    transactions = plan_data.get(
        "transactions",
        [],
    )

    transaction = (
        transactions[0]
        if transactions
        else {}
    )

    sla = plan_data.get(
        "sla",
        {},
    )

    protocol = target.get(
        "protocol",
        "https",
    )

    host = target.get(
        "host",
        "",
    )

    method = transaction.get(
        "method",
        "",
    )

    path = transaction.get(
        "path",
        "",
    )

    print()
    print("=" * 70)
    print("PRUEBA LISTA PARA EJECUTAR")
    print("=" * 70)
    print(
        f"Scenario       : "
        f"{metadata.get('name', '')}"
    )
    print(
        f"Target         : "
        f"{method} {protocol}://{host}{path}"
    )
    print(
        f"HTTP esperado  : "
        f"{transaction.get('expected_status', '')}"
    )
    print(
        f"Motor          : "
        f"{str(profile_data.get('engine', '')).upper()}"
    )
    print(
        f"Usuarios       : "
        f"{params.get('threads')}"
    )
    print(
        f"Ramp-up        : "
        f"{params.get('ramp_time_seconds')} s"
    )
    print(
        f"Duración       : "
        f"{params.get('duration_seconds')} s"
    )
    print(
        f"Pacing         : "
        f"{params.get('pacing_seconds')} s"
    )
    print(
        f"Error rate SLA : <= "
        f"{sla.get('error_rate_threshold_pct')}%"
    )
    print(
        f"p95 SLA        : <= "
        f"{sla.get('p95_threshold_ms')} ms"
    )
    print(
        f"p99 SLA        : <= "
        f"{sla.get('p99_threshold_ms')} ms"
    )
    print(
        "Estado         : PRE_EXECUTION_READY"
    )
    print("=" * 70)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Natural governed performance execution."
        )
    )

    parser.add_argument(
        "scenario_positional",
        nargs="?",
    )

    parser.add_argument(
        "run_positional",
        nargs="?",
    )

    parser.add_argument(
        "--scenario",
    )

    parser.add_argument(
        "--run",
        action="store_true",
    )

    parser.add_argument(
        "--check-only",
        action="store_true",
        help=(
            "Validate resumability without executing load."
        ),
    )

    args = parser.parse_args()

    scenario = (
        args.scenario
        or args.scenario_positional
        or ""
    ).strip()

    if not scenario:
        parser.error(
            "scenario is required"
        )

    if (
        args.run_positional
        and args.run_positional != "RUN"
    ):
        parser.error(
            "second positional argument must be RUN"
        )

    args.scenario = scenario

    args.run_confirmed = bool(
        args.run
        or args.run_positional == "RUN"
    )

    return args


def main() -> int:
    args = parse_args()

    scenario = args.scenario

    plan = (
        ROOT
        / "tests"
        / "plans"
        / scenario
        / "test-plan.yaml"
    )

    workspace = (
        ROOT
        / "workspaces"
        / scenario
    )

    profile = (
        workspace
        / "execution-profile.yaml"
    )

    model = (
        workspace
        / "normalized-performance-model.json"
    )

    manifest = (
        ROOT
        / "results"
        / "preflight"
        / scenario
        / "controlled-engine-v3.json"
    )

    human = (
        os.getenv(
            "PERF_HUMAN_NAME"
        )
        or os.getenv(
            "USER"
        )
        or "human"
    )

    print()
    print("=" * 70)
    print("PREPARANDO LA PRUEBA")
    print("=" * 70)
    print()
    print(
        "Voy a reutilizar cualquier estado válido "
        "que ya exista."
    )
    print(
        "No repetiré aprobación, autorización o "
        "validaciones innecesariamente."
    )
    print(
        "No se iniciará carga antes de la "
        "confirmación RUN."
    )


    sync_command = [
        sys.executable,
        str(
            ROOT
            / "scripts"
            / "sync_execution_contract.py"
        ),
        "--plan",
        str(plan),
        "--workspace",
        str(workspace),
    ]

    sync_result = subprocess.run(
        sync_command,
        cwd=ROOT,
        text=True,
        check=False,
    )

    if sync_result.returncode != 0:
        raise NaturalExecutionError(
            "No se pudo sincronizar el contrato "
            "funcional con los artefactos de ejecución."
        )

    status, workload, authorization = (
        plan_status(
            plan
        )
    )

    if (
        status != "APPROVED"
        or workload != "APPROVED"
    ):
        print()
        print(
            "Registrando la aprobación del diseño "
            "y workload..."
        )

        run_workflow(
            "approve",
            "--plan",
            str(plan),
            "--approved-by",
            human,
        )

        status, workload, authorization = (
            plan_status(
                plan
            )
        )

    else:
        print()
        print(
            "[OK] Diseño y workload ya aprobados."
        )

    engine = profile_engine(
        profile
    )

    if engine not in {
        "jmeter",
        "locust",
    }:
        print()
        print(
            "Selecciona el motor que ejecutará "
            "esta prueba."
        )

        run_workflow(
            "select-engine",
            "--profile",
            str(profile),
        )

        engine = profile_engine(
            profile
        )

    artifact = artifact_for(
        scenario,
        engine,
    )

    ready = manifest_is_current(
        manifest,
        plan,
        profile,
        artifact,
        engine,
    )

    if ready:
        print()
        print(
            "[OK] PRE_EXECUTION_READY encontrado."
        )
        print(
            "[OK] Engine persistido: "
            f"{engine.upper()}."
        )
        print(
            "[OK] Hashes del plan, profile y "
            "artefacto verificados."
        )
        print(
            "[OK] No se repetirán prepare, "
            "authorize ni preflight."
        )

    else:
        print()
        print(
            "Completando únicamente las etapas "
            "que aún sean necesarias..."
        )

        if not model.is_file():
            raise NaturalExecutionError(
                "No existe el modelo normalizado "
                f"requerido: {model}"
            )

        run_workflow(
            "prepare",
            "--model",
            str(model),
            "--profile",
            str(profile),
        )

        artifact = artifact_for(
            scenario,
            engine,
        )

        if not artifact.is_file():
            raise NaturalExecutionError(
                "No se generó el artefacto esperado "
                f"para {engine}: {artifact}"
            )

        _, _, authorization = (
            plan_status(
                plan
            )
        )

        if authorization != "AUTHORIZED":
            print()
            print(
                "Registrando autorización de "
                "ejecución..."
            )

            run_workflow(
                "authorize",
                "--plan",
                str(plan),
                "--profile",
                str(profile),
                "--artifact",
                str(artifact),
                "--authorized-by",
                human,
                "--notes",
                (
                    "Authorized through the natural "
                    "Performance Engineering flow."
                ),
            )

        else:
            print()
            print(
                "[OK] La ejecución ya estaba "
                "autorizada."
            )

        print()
        print(
            "Validando que la prueba esté lista..."
        )

        run_workflow(
            "preflight",
            "--plan",
            str(plan),
            "--profile",
            str(profile),
            "--artifact",
            str(artifact),
            "--manifest",
            str(manifest),
        )

        ready = manifest_is_current(
            manifest,
            plan,
            profile,
            artifact,
            engine,
        )

        if not ready:
            raise NaturalExecutionError(
                "El preflight no produjo un estado "
                "PRE_EXECUTION_READY válido."
            )

    transaction_summary(
        plan,
        profile,
    )

    if args.check_only:
        print()
        print(
            "[CHECK ONLY] Estado resumible válido."
        )
        print(
            "[CHECK ONLY] No se ejecutó carga."
        )
        return 0

    if not args.run_confirmed:
        print()
        print(
            "Para iniciar la carga escribe "
            "exactamente:"
        )
        print()
        print("RUN")
        print()

        answer = input().strip()

        if answer != "RUN":
            print()
            print(
                "Ejecución cancelada. "
                "No se inició carga."
            )
            return 0

    # Final TOCTOU protection.
    if not manifest_is_current(
        manifest,
        plan,
        profile,
        artifact,
        engine,
    ):
        raise NaturalExecutionError(
            "El estado cambió después de la "
            "validación. No se iniciará carga."
        )

    print()
    print("=" * 70)
    print("INICIANDO PRUEBA DE RENDIMIENTO")
    print("=" * 70)
    print(
        f"Scenario : {scenario}"
    )
    print(
        f"Motor    : {engine.upper()}"
    )
    print(
        "Estado   : PRE_EXECUTION_READY validado"
    )
    print("=" * 70)
    print()

    run_workflow(
        "execute",
        "--plan",
        str(plan),
        "--profile",
        str(profile),
        "--artifact",
        str(artifact),
        "--manifest",
        str(manifest),
        input_text="RUN\n",
    )

    print()
    print("=" * 70)
    print("EJECUCIÓN FINALIZADA")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            main()
        )

    except NaturalExecutionError as error:
        print()
        print(
            f"ERROR: {error}",
            file=sys.stderr,
        )
        print(
            "No se inició una nueva carga "
            "después del error.",
            file=sys.stderr,
        )
        raise SystemExit(2)
