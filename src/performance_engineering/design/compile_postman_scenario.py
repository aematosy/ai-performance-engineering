#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


SECRET_NAMES = {
    "password",
    "passwd",
    "secret",
    "client_secret",
    "api_key",
    "apikey",
    "token",
    "access_token",
    "authorization",
}


class CompileError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CompileError(
            f"File not found: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise CompileError(
            f"Invalid JSON in {path}: "
            f"line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(data, dict):
        raise CompileError(
            f"JSON root must be an object: {path}"
        )

    return data


def walk_items(
    items: list[dict[str, Any]],
    prefix: str = "",
):
    for item in items:
        name = str(item.get("name", "")).strip()
        current = (
            f"{prefix}/{name}"
            if prefix
            else name
        )

        if isinstance(
            item.get("request"),
            dict,
        ):
            yield current, item

        children = item.get("item")
        if isinstance(children, list):
            yield from walk_items(
                children,
                current,
            )


def environment_values(
    environment: dict[str, Any] | None,
) -> dict[str, str]:
    values: dict[str, str] = {}

    if not environment:
        return values

    for item in environment.get(
        "values",
        [],
    ) or []:
        if not isinstance(item, dict):
            continue

        if item.get("enabled", True) is False:
            continue

        key = item.get("key")
        value = item.get("value")

        if (
            isinstance(key, str)
            and key
            and value is not None
        ):
            values[key] = str(value)

    return values


def substitute_postman_variables(
    value: str,
    variables: dict[str, str],
) -> str:
    def repl(
        match: re.Match[str],
    ) -> str:
        key = match.group(1).strip()

        if key in variables:
            return variables[key]

        return match.group(0)

    return re.sub(
        r"\{\{([^{}]+)\}\}",
        repl,
        value,
    )


def is_secret_name(name: str) -> bool:
    lowered = name.strip().lower()

    return (
        lowered in SECRET_NAMES
        or "password" in lowered
        or lowered.endswith("_secret")
        or lowered.endswith("_token")
    )


def secret_property_name(
    request_id: str,
    field_name: str,
) -> str:
    request_slug = re.sub(
        r"[^a-z0-9]+",
        "_",
        request_id.lower(),
    ).strip("_")

    field_slug = re.sub(
        r"[^a-z0-9]+",
        "_",
        field_name.lower(),
    ).strip("_")

    return (
        f"secret_{request_slug}_{field_slug}"
    )


def parameter_name(
    request_id: str,
    field_path: list[str],
    seen_leafs: dict[str, int],
) -> str:
    leaf = field_path[-1]
    seen_leafs[leaf] = (
        seen_leafs.get(leaf, 0) + 1
    )

    request_slug = re.sub(
        r"[^a-z0-9]+",
        "_",
        request_id.lower(),
    ).strip("_")

    field_slug = "_".join(
        re.sub(
            r"[^a-z0-9]+",
            "_",
            piece.lower(),
        ).strip("_")
        for piece in field_path
    )

    return (
        f"{request_slug}_{field_slug}"
    )


def parameterize_json_body(
    *,
    request_id: str,
    body: Any,
    seen_leafs: dict[str, int],
    csv_columns: dict[str, Any],
    secret_properties: set[str],
) -> Any:
    def recurse(
        value: Any,
        path: list[str],
    ) -> Any:
        if isinstance(value, dict):
            return {
                key: recurse(
                    child,
                    path + [key],
                )
                for key, child in value.items()
            }

        if isinstance(value, list):
            return [
                recurse(
                    child,
                    path + [str(index)],
                )
                for index, child in enumerate(
                    value
                )
            ]

        if not path:
            return value

        field_name = path[-1]

        if is_secret_name(field_name):
            prop = secret_property_name(
                request_id,
                field_name,
            )
            secret_properties.add(prop)
            return f"${{__P({prop},)}}"

        column = parameter_name(
            request_id,
            path,
            seen_leafs,
        )

        csv_columns.setdefault(
            column,
            {
                "example_value": value,
                "json_type": (
                    "BOOLEAN"
                    if isinstance(value, bool)
                    else "INTEGER"
                    if isinstance(value, int)
                    and not isinstance(value, bool)
                    else "NUMBER"
                    if isinstance(value, float)
                    else "NULL"
                    if value is None
                    else "STRING"
                ),
            },
        )

        return {
            "__runtime_parameter__": column,
            "__json_type__": (
                "BOOLEAN"
                if isinstance(value, bool)
                else "INTEGER"
                if isinstance(value, int)
                and not isinstance(value, bool)
                else "NUMBER"
                if isinstance(value, float)
                else "NULL"
                if value is None
                else "STRING"
            ),
        }

    return recurse(
        body,
        [],
    )


def candidate_by_id(
    candidates: dict[str, Any],
    candidate_id: str,
) -> dict[str, Any]:
    for item in candidates.get(
        "candidates",
        [],
    ) or []:
        if (
            isinstance(item, dict)
            and item.get("id") == candidate_id
        ):
            return item

    raise CompileError(
        f"Candidate not found: {candidate_id}"
    )


def correlation_maps(
    correlations: dict[str, Any],
):
    by_producer: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    consumers: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for item in correlations.get(
        "correlations",
        [],
    ) or []:
        if not isinstance(item, dict):
            continue

        producer = item.get("producer")

        if producer:
            by_producer.setdefault(
                producer,
                [],
            ).append(item)

        for consumer in item.get(
            "consumers",
            [],
        ) or []:
            consumers.setdefault(
                consumer,
                [],
            ).append(item)

    return by_producer, consumers


def apply_resource_id(
    path: str,
    correlations: list[dict[str, Any]],
) -> str:
    for item in correlations:
        if (
            item.get("source")
            != "INFERRED_RESOURCE_LIFECYCLE"
        ):
            continue

        runtime_variable = item.get(
            "runtime_variable"
        )

        if not runtime_variable:
            continue

        # Replace a static numeric or UUID-like final path segment.
        path = re.sub(
            r"/(?:\d+|[0-9a-fA-F-]{16,})$",
            f"/${{{runtime_variable}}}",
            path,
        )

    return path


def apply_runtime_vars(
    value: str,
    correlations: list[dict[str, Any]],
) -> str:
    output = value

    for item in correlations:
        variable = item.get(
            "runtime_variable"
        )

        if not variable:
            continue

        output = output.replace(
            "{{" + variable + "}}",
            "${" + variable + "}",
        )

    return output


def normalize_header(
    header: dict[str, Any],
    correlations: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if header.get("disabled") is True:
        return None

    key = str(
        header.get("key", "")
    ).strip()

    value = str(
        header.get("value", "")
    )

    if not key:
        return None

    value = apply_runtime_vars(
        value,
        correlations,
    )

    return {
        "name": key,
        "value": value,
    }


def request_url_string(
    request: dict[str, Any],
) -> str:
    url = request.get("url")

    if isinstance(url, str):
        return url

    if not isinstance(url, dict):
        return ""

    raw = url.get("raw")

    if isinstance(raw, str):
        return raw

    protocol = str(
        url.get("protocol", "")
    )
    host = url.get("host")

    if isinstance(host, list):
        host = ".".join(
            str(x)
            for x in host
        )

    path = url.get("path")

    if isinstance(path, list):
        path = "/" + "/".join(
            str(x)
            for x in path
        )

    return (
        f"{protocol}://{host}"
        f"{path or ''}"
    )


def compile_scenario(
    *,
    collection: dict[str, Any],
    environment: dict[str, Any] | None,
    candidates: dict[str, Any],
    correlations: dict[str, Any],
    candidate_id: str,
) -> dict[str, Any]:
    candidate = candidate_by_id(
        candidates,
        candidate_id,
    )

    selected = candidate.get(
        "requests",
        [],
    ) or []

    item_map = {
        request_id: item
        for request_id, item in walk_items(
            collection.get(
                "item",
                [],
            ) or []
        )
    }

    missing = [
        request_id
        for request_id in selected
        if request_id not in item_map
    ]

    if missing:
        raise CompileError(
            "Requests missing from collection: "
            + ", ".join(missing)
        )

    env = environment_values(
        environment
    )

    by_producer, by_consumer = (
        correlation_maps(
            correlations
        )
    )

    csv_columns: dict[str, Any] = {}
    secret_properties: set[str] = set()
    seen_leafs: dict[str, int] = {}
    compiled_requests = []

    for request_id in selected:
        item = item_map[request_id]
        request = item["request"]

        raw_url = request_url_string(
            request
        )

        resolved_url = (
            substitute_postman_variables(
                raw_url,
                env,
            )
        )

        from urllib.parse import urlsplit

        split = urlsplit(
            resolved_url
        )

        if not split.scheme or not split.hostname:
            raise CompileError(
                f"Unable to resolve request URL: "
                f"{request_id} -> {resolved_url}"
            )

        consumer_correlations = (
            by_consumer.get(
                request_id,
                [],
            )
        )

        path = (
            split.path
            or "/"
        )

        path = apply_resource_id(
            path,
            consumer_correlations,
        )

        query = split.query

        headers = []

        for header in request.get(
            "header",
            [],
        ) or []:
            if not isinstance(
                header,
                dict,
            ):
                continue

            normalized_header = (
                normalize_header(
                    header,
                    consumer_correlations,
                )
            )

            if normalized_header:
                headers.append(
                    normalized_header
                )

        body_obj = None
        body = request.get("body")

        if isinstance(body, dict):
            if body.get("mode") == "raw":
                raw = body.get("raw")

                if isinstance(raw, str) and raw.strip():
                    try:
                        parsed = json.loads(
                            raw
                        )
                    except json.JSONDecodeError:
                        parsed = None

                    if parsed is not None:
                        body_obj = (
                            parameterize_json_body(
                                request_id=request_id,
                                body=parsed,
                                seen_leafs=seen_leafs,
                                csv_columns=csv_columns,
                                secret_properties=secret_properties,
                            )
                        )

        extractors = []

        for correlation in by_producer.get(
            request_id,
            [],
        ):
            extractors.append(
                {
                    "variable": (
                        correlation[
                            "runtime_variable"
                        ]
                    ),
                    "json_path": (
                        correlation[
                            "json_path"
                        ]
                    ),
                    "source": (
                        correlation[
                            "source"
                        ]
                    ),
                    "confidence": (
                        correlation[
                            "confidence"
                        ]
                    ),
                }
            )

        compiled_requests.append(
            {
                "id": request_id,
                "method": str(
                    request.get(
                        "method",
                        "GET",
                    )
                ).upper(),
                "protocol": split.scheme,
                "host": split.hostname,
                "port": split.port,
                "path": path,
                "query": query,
                "headers": headers,
                "json_body": body_obj,
                "extractors": extractors,
            }
        )

    return {
        "schema_version": "1.0",
        "source": {
            "type": "POSTMAN",
            "collection_name": (
                collection.get(
                    "info",
                    {},
                ).get(
                    "name",
                    "UNKNOWN",
                )
            ),
            "environment_name": (
                environment.get("name")
                if environment
                else None
            ),
        },
        "scenario_candidate": {
            "id": candidate.get("id"),
            "type": candidate.get("type"),
        },
        "requests": compiled_requests,
        "csv": {
            "columns": [
                {
                    "name": name,
                    "example_value": metadata["example_value"],
                    "json_type": metadata["json_type"],
                }
                for name, metadata
                in csv_columns.items()
            ]
        },
        "secrets": {
            "jmeter_properties": sorted(
                secret_properties
            ),
            "persist_values": False,
        },
        "correlations": correlations.get(
            "correlations",
            [],
        ),
        "readiness": {
            "ready_for_jmx": True,
            "request_count": len(
                compiled_requests
            ),
            "csv_column_count": len(
                csv_columns
            ),
            "secret_property_count": len(
                secret_properties
            ),
        },
    }


def write_csv_template(
    model: dict[str, Any],
    path: Path,
) -> None:
    columns = model.get(
        "csv",
        {},
    ).get(
        "columns",
        [],
    )

    names = [
        item["name"]
        for item in columns
    ]

    examples = [
        (
            "true"
            if item.get("json_type") == "BOOLEAN"
            and item.get("example_value") is True
            else "false"
            if item.get("json_type") == "BOOLEAN"
            and item.get("example_value") is False
            else item.get("example_value")
        )
        for item in columns
    ]

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as fh:
        writer = csv.writer(fh)
        writer.writerow(names)
        writer.writerow(examples)


def write_secrets_template(
    model: dict[str, Any],
    path: Path,
) -> None:
    properties = model.get(
        "secrets",
        {},
    ).get(
        "jmeter_properties",
        [],
    )

    lines = [
        "# Local-only JMeter properties.",
        "# Do not commit this file.",
        "# Fill values before execution.",
    ]

    lines.extend(
        f"{name}="
        for name in properties
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compile one Postman scenario candidate "
            "into an executable, secret-safe model."
        )
    )

    parser.add_argument(
        "--collection",
        required=True,
    )
    parser.add_argument(
        "--environment",
    )
    parser.add_argument(
        "--candidates",
        required=True,
    )
    parser.add_argument(
        "--correlations",
        required=True,
    )
    parser.add_argument(
        "--candidate-id",
        required=True,
    )
    parser.add_argument(
        "--output",
        required=True,
    )
    parser.add_argument(
        "--csv",
        required=True,
    )
    parser.add_argument(
        "--secrets-template",
        required=True,
    )

    args = parser.parse_args()

    try:
        collection = load_json(
            Path(
                args.collection
            ).expanduser().resolve()
        )
        environment = (
            load_json(
                Path(
                    args.environment
                ).expanduser().resolve()
            )
            if args.environment
            else None
        )
        candidates = load_json(
            Path(
                args.candidates
            ).expanduser().resolve()
        )
        correlations = load_json(
            Path(
                args.correlations
            ).expanduser().resolve()
        )

        model = compile_scenario(
            collection=collection,
            environment=environment,
            candidates=candidates,
            correlations=correlations,
            candidate_id=args.candidate_id,
        )

        output = Path(
            args.output
        ).expanduser().resolve()
        csv_path = Path(
            args.csv
        ).expanduser().resolve()
        secrets_path = Path(
            args.secrets_template
        ).expanduser().resolve()

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        output.write_text(
            json.dumps(
                model,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        write_csv_template(
            model,
            csv_path,
        )
        write_secrets_template(
            model,
            secrets_path,
        )

    except CompileError as exc:
        print(
            f"POSTMAN COMPILE ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print("=" * 72)
    print("POSTMAN EXECUTABLE SCENARIO COMPILATION")
    print("=" * 72)
    print(
        f"Candidate      : {args.candidate_id}"
    )
    print(
        f"Requests       : "
        f"{model['readiness']['request_count']}"
    )
    print(
        f"CSV columns    : "
        f"{model['readiness']['csv_column_count']}"
    )
    print(
        f"Secret props   : "
        f"{model['readiness']['secret_property_count']}"
    )
    print(f"Model          : {output}")
    print(f"CSV            : {csv_path}")
    print(f"Secrets tmpl   : {secrets_path}")
    print("=" * 72)
    print("SCENARIO READY FOR JMX GENERATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
