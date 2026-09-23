#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


class SecretMaterializationError(RuntimeError):
    pass


def load_json(
    path: Path,
) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        raise SecretMaterializationError(
            f"Unable to read JSON: {path}: {exc}"
        ) from exc

    if not isinstance(value, dict):
        raise SecretMaterializationError(
            f"JSON root must be an object: {path}"
        )

    return value


def load_compiler():
    path = (
        ROOT
        / "scripts"
        / "compile_postman_scenario.py"
    )

    spec = importlib.util.spec_from_file_location(
        "_postman_compiler",
        path,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise SecretMaterializationError(
            f"Unable to load compiler: {path}"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(
        module
    )

    return module


def variable_values(
    collection: dict[str, Any],
    environment: dict[str, Any] | None,
) -> dict[str, str]:
    values: dict[str, str] = {}

    collection_variables = collection.get(
        "variable",
        []
    )

    if isinstance(
        collection_variables,
        list,
    ):
        for item in collection_variables:
            if not isinstance(
                item,
                dict,
            ):
                continue

            key = str(
                item.get(
                    "key",
                    "",
                )
                or ""
            ).strip()

            value = item.get(
                "value"
            )

            if (
                key
                and value is not None
            ):
                values[
                    key
                ] = str(
                    value
                )

    if environment:
        environment_values = environment.get(
            "values",
            []
        )

        if isinstance(
            environment_values,
            list,
        ):
            for item in environment_values:
                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                if item.get(
                    "enabled",
                    True,
                ) is False:
                    continue

                key = str(
                    item.get(
                        "key",
                        "",
                    )
                    or ""
                ).strip()

                value = item.get(
                    "value"
                )

                if (
                    key
                    and value is not None
                ):
                    values[
                        key
                    ] = str(
                        value
                    )

    return values


def resolve_value(
    value: Any,
    variables: dict[str, str],
) -> str | None:
    if value is None:
        return None

    text = str(
        value
    )

    pattern = re.compile(
        r"\{\{([^{}]+)\}\}"
    )

    for _ in range(10):
        matches = pattern.findall(
            text
        )

        if not matches:
            break

        changed = False

        for raw_name in matches:
            name = raw_name.strip()

            if name not in variables:
                continue

            token = (
                "{{"
                + raw_name
                + "}}"
            )

            text = text.replace(
                token,
                variables[name],
            )

            changed = True

        if not changed:
            break

    text = text.strip()

    if not text:
        return None

    if pattern.search(
        text
    ):
        return None

    return text


def walk_requests(
    items: list[Any],
    prefix: list[str] | None = None,
):
    prefix = prefix or []

    for item in items:
        if not isinstance(
            item,
            dict,
        ):
            continue

        name = str(
            item.get(
                "name",
                "",
            )
            or ""
        ).strip()

        next_prefix = (
            prefix
            + ([name] if name else [])
        )

        children = item.get(
            "item"
        )

        if isinstance(
            children,
            list,
        ):
            yield from walk_requests(
                children,
                next_prefix,
            )

        request = item.get(
            "request"
        )

        if isinstance(
            request,
            dict,
        ):
            request_id = "/".join(
                next_prefix
            )

            yield (
                request_id,
                request,
            )


def collect_secret_values(
    *,
    collection: dict[str, Any],
    environment: dict[str, Any] | None,
    model: dict[str, Any],
) -> tuple[
    tuple[str, ...],
    dict[str, str],
]:
    compiler = load_compiler()

    required = tuple(
        str(name)
        for name in (
            model.get(
                "secrets",
                {},
            ).get(
                "jmeter_properties",
                [],
            )
            or []
        )
        if str(name).strip()
    )

    if not required:
        return (
            (),
            {},
        )

    required_set = set(
        required
    )

    selected_requests = {
        str(
            item.get(
                "id",
                "",
            )
        )
        for item in (
            model.get(
                "requests",
                []
            )
            or []
        )
        if isinstance(
            item,
            dict,
        )
    }

    variables = variable_values(
        collection,
        environment,
    )

    discovered: dict[str, str] = {}

    def inspect(
        *,
        request_id: str,
        value: Any,
        path: list[str],
    ) -> None:
        if isinstance(
            value,
            dict,
        ):
            for key, child in value.items():
                inspect(
                    request_id=request_id,
                    value=child,
                    path=path + [str(key)],
                )

            return

        if isinstance(
            value,
            list,
        ):
            for index, child in enumerate(
                value
            ):
                inspect(
                    request_id=request_id,
                    value=child,
                    path=path + [str(index)],
                )

            return

        if not path:
            return

        field_name = path[-1]

        if not compiler.is_secret_name(
            field_name
        ):
            return

        property_name = (
            compiler.secret_property_name(
                request_id,
                field_name,
            )
        )

        if property_name not in required_set:
            return

        resolved = resolve_value(
            value,
            variables,
        )

        if resolved is None:
            return

        previous = discovered.get(
            property_name
        )

        if (
            previous is not None
            and previous != resolved
        ):
            raise SecretMaterializationError(
                "Conflicting source values found for "
                f"runtime property '{property_name}'."
            )

        discovered[
            property_name
        ] = resolved

    for (
        request_id,
        request,
    ) in walk_requests(
        collection.get(
            "item",
            [],
        )
        or []
    ):
        if request_id not in selected_requests:
            continue

        body = request.get(
            "body"
        )

        if not isinstance(
            body,
            dict,
        ):
            continue

        if body.get(
            "mode"
        ) != "raw":
            continue

        raw = body.get(
            "raw"
        )

        if (
            not isinstance(
                raw,
                str,
            )
            or not raw.strip()
        ):
            continue

        try:
            parsed = json.loads(
                raw
            )
        except json.JSONDecodeError:
            continue

        inspect(
            request_id=request_id,
            value=parsed,
            path=[],
        )

    return (
        required,
        discovered,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize JMeter runtime properties "
            "from the declared Postman source without "
            "interactive prompts."
        )
    )

    parser.add_argument(
        "--collection",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--environment",
        type=Path,
    )

    parser.add_argument(
        "--manifest",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    collection_path = (
        args.collection
        .expanduser()
        .resolve()
    )

    environment_path = (
        args.environment
        .expanduser()
        .resolve()
        if args.environment
        else None
    )

    manifest_path = (
        args.manifest
        .expanduser()
        .resolve()
    )

    collection = load_json(
        collection_path
    )

    environment = (
        load_json(
            environment_path
        )
        if environment_path
        else None
    )

    manifest = load_json(
        manifest_path
    )

    scenario = str(
        manifest.get(
            "scenario",
            "",
        )
        or ""
    ).strip()

    artifacts = (
        manifest.get(
            "artifacts"
        )
        or {}
    )

    model_value = str(
        artifacts.get(
            "executable_model",
            "",
        )
        or ""
    ).strip()

    if not scenario:
        raise SecretMaterializationError(
            "Design manifest has no canonical scenario."
        )

    if not model_value:
        raise SecretMaterializationError(
            "Design manifest has no executable model."
        )

    model_path = Path(
        model_value
    ).expanduser()

    if not model_path.is_absolute():
        model_path = (
            ROOT
            / model_path
        )

    model_path = model_path.resolve()

    if not model_path.is_file():
        raise SecretMaterializationError(
            f"Executable model does not exist: {model_path}"
        )

    model = load_json(
        model_path
    )

    (
        required,
        discovered,
    ) = collect_secret_values(
        collection=collection,
        environment=environment,
        model=model,
    )

    if not required:
        print(
            "POSTMAN RUNTIME SECRETS : NOT REQUIRED"
        )

        return 0

    missing = [
        name
        for name in required
        if not discovered.get(
            name,
            ""
        ).strip()
    ]

    if missing:
        raise SecretMaterializationError(
            "Required runtime secrets could not be "
            "resolved from the Postman collection/"
            "environment: "
            + ", ".join(
                missing
            )
            + ". Interactive secret prompting is forbidden."
        )

    output = (
        ROOT
        / "data"
        / scenario
        / "secrets.properties"
    ).resolve()

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    lines = [
        "# Auto-materialized from the declared Postman source.",
        "# Local-only runtime artifact. Do not commit.",
        "",
    ]

    for name in required:
        lines.append(
            f"{name}={discovered[name]}"
        )

    output.write_text(
        "\n".join(
            lines
        )
        + "\n",
        encoding="utf-8",
    )

    os.chmod(
        output,
        0o600,
    )

    print(
        "POSTMAN RUNTIME SECRETS : RESOLVED"
    )
    print(
        f"Scenario                : {scenario}"
    )
    print(
        f"Required properties     : {len(required)}"
    )
    print(
        f"Resolved properties     : {len(discovered)}"
    )
    print(
        f"Properties file         : {output}"
    )
    print(
        "Secret values           : NOT DISPLAYED"
    )
    print(
        "Interactive prompt      : NO"
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            main()
        )
    except SecretMaterializationError as exc:
        print(
            f"POSTMAN RUNTIME SECRET ERROR: {exc}",
            file=sys.stderr,
        )

        raise SystemExit(2)
