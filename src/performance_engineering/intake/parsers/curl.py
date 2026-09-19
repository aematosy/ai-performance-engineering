#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class CurlParseError(RuntimeError):
    pass


DATA_OPTIONS = {
    "-d",
    "--data",
    "--data-raw",
    "--data-binary",
    "--data-ascii",
}

HEADER_OPTIONS = {
    "-H",
    "--header",
}

REQUEST_OPTIONS = {
    "-X",
    "--request",
}

URL_OPTIONS = {
    "--url",
}

SAFE_FLAG_OPTIONS = {
    "-s",
    "--silent",
    "-S",
    "--show-error",
    "-L",
    "--location",
    "--compressed",
    "--fail",
    "--fail-with-body",
}

UNSUPPORTED_SEMANTIC_OPTIONS = {
    "-u",
    "--user",
    "-b",
    "--cookie",
    "-c",
    "--cookie-jar",
    "-F",
    "--form",
    "--form-string",
    "--data-urlencode",
    "--get",
    "-G",
    "--upload-file",
    "-T",
    "--proxy",
    "-x",
}


def read_source(
    path: Path,
) -> str:
    if not path.is_file():
        raise CurlParseError(
            f"cURL input not found: {path}"
        )

    try:
        text = path.read_text(
            encoding="utf-8"
        )
    except OSError as exc:
        raise CurlParseError(
            f"Unable to read cURL input: {exc}"
        ) from exc

    if not text.strip():
        raise CurlParseError(
            "cURL input is empty."
        )

    return text


def tokenize(
    text: str,
) -> list[str]:
    # A .curl file commonly uses POSIX shell line continuation:
    #
    # curl --request POST \
    #   --url https://example.test \
    #   --header 'Accept: application/json'
    #
    # A real shell removes the backslash + newline before tokenization.
    # shlex.split() does not provide the complete interactive-shell
    # preprocessing behavior, so normalize continuations explicitly.
    normalized = (
        text
        .replace("\\\r\n", " ")
        .replace("\\\n", " ")
    )

    try:
        tokens = shlex.split(
            normalized,
            posix=True,
            comments=False,
        )
    except ValueError as exc:
        raise CurlParseError(
            f"Invalid cURL quoting: {exc}"
        ) from exc

    if not tokens:
        raise CurlParseError(
            "cURL command contains no tokens."
        )

    executable = Path(
        tokens[0]
    ).name.lower()

    if executable != "curl":
        raise CurlParseError(
            "Input must contain exactly one cURL command."
        )

    if tokens.count("curl") > 1:
        raise CurlParseError(
            "Multiple cURL commands are not supported "
            "in a single .curl input."
        )

    return tokens


def parse_header(
    value: str,
) -> tuple[str, str]:
    if ":" not in value:
        raise CurlParseError(
            f"Invalid header declaration: {value}"
        )

    name, header_value = value.split(
        ":",
        1,
    )

    name = name.strip()
    header_value = header_value.strip()

    if not name:
        raise CurlParseError(
            "Header name must not be empty."
        )

    if (
        "\n" in name
        or "\r" in name
        or "\n" in header_value
        or "\r" in header_value
    ):
        raise CurlParseError(
            f"Invalid newline in header: {name}"
        )

    return (
        name,
        header_value,
    )


def validate_target(
    value: str,
) -> str:
    target = value.strip()

    parsed = urlparse(
        target
    )

    if parsed.scheme.lower() not in {
        "http",
        "https",
    }:
        raise CurlParseError(
            "cURL target must use http or https."
        )

    if not parsed.hostname:
        raise CurlParseError(
            "cURL target does not contain a valid host."
        )

    if (
        parsed.username
        or parsed.password
    ):
        raise CurlParseError(
            "Credentials embedded in URLs are not supported."
        )

    try:
        port = parsed.port
    except ValueError as exc:
        raise CurlParseError(
            "cURL target contains an invalid port."
        ) from exc

    if (
        port is not None
        and not 1 <= port <= 65535
    ):
        raise CurlParseError(
            "cURL target port must be between 1 and 65535."
        )

    return target


def normalize_body(
    raw_body: str | None,
    headers: dict[str, str],
) -> Any | None:
    if raw_body is None:
        return None

    body = raw_body.strip()

    if not body:
        raise CurlParseError(
            "cURL body must not be empty."
        )

    content_type = ""

    for name, value in headers.items():
        if name.lower() == "content-type":
            content_type = value.lower()
            break

    looks_json = (
        "json" in content_type
        or body.startswith("{")
        or body.startswith("[")
    )

    if looks_json:
        try:
            parsed = json.loads(
                body
            )
        except json.JSONDecodeError as exc:
            raise CurlParseError(
                "cURL request body appears to be JSON "
                f"but is invalid: {exc.msg}"
            ) from exc

        if not isinstance(
            parsed,
            (
                dict,
                list,
            ),
        ):
            raise CurlParseError(
                "JSON request body must be an object or array."
            )

        return parsed

    raise CurlParseError(
        "This governed cURL intake currently supports "
        "JSON request bodies only. "
        "Use structured CLI input for another body format."
    )


def parse_curl(
    tokens: list[str],
) -> dict[str, Any]:
    method: str | None = None
    target: str | None = None
    headers: dict[str, str] = {}
    body_parts: list[str] = []

    index = 1

    while index < len(tokens):
        token = tokens[index]

        if token in REQUEST_OPTIONS:
            index += 1

            if index >= len(tokens):
                raise CurlParseError(
                    f"{token} requires a value."
                )

            method = (
                tokens[index]
                .strip()
                .upper()
            )

        elif token.startswith("--request="):
            method = (
                token.split(
                    "=",
                    1,
                )[1]
                .strip()
                .upper()
            )

        elif token in URL_OPTIONS:
            index += 1

            if index >= len(tokens):
                raise CurlParseError(
                    f"{token} requires a value."
                )

            if target is not None:
                raise CurlParseError(
                    "Multiple target URLs are not supported."
                )

            target = validate_target(
                tokens[index]
            )

        elif token.startswith("--url="):
            if target is not None:
                raise CurlParseError(
                    "Multiple target URLs are not supported."
                )

            target = validate_target(
                token.split(
                    "=",
                    1,
                )[1]
            )

        elif token in HEADER_OPTIONS:
            index += 1

            if index >= len(tokens):
                raise CurlParseError(
                    f"{token} requires a value."
                )

            name, value = parse_header(
                tokens[index]
            )

            headers[
                name
            ] = value

        elif token.startswith("--header="):
            name, value = parse_header(
                token.split(
                    "=",
                    1,
                )[1]
            )

            headers[
                name
            ] = value

        elif token in DATA_OPTIONS:
            index += 1

            if index >= len(tokens):
                raise CurlParseError(
                    f"{token} requires a value."
                )

            body_parts.append(
                tokens[index]
            )

        elif any(
            token.startswith(
                option + "="
            )
            for option in DATA_OPTIONS
            if option.startswith("--")
        ):
            body_parts.append(
                token.split(
                    "=",
                    1,
                )[1]
            )

        elif token in SAFE_FLAG_OPTIONS:
            pass

        elif token in UNSUPPORTED_SEMANTIC_OPTIONS:
            raise CurlParseError(
                f"Unsupported cURL option '{token}'. "
                "It changes request semantics and must "
                "be represented explicitly by the governed model."
            )

        elif token.startswith("-"):
            raise CurlParseError(
                f"Unsupported cURL option: {token}"
            )

        else:
            if target is not None:
                raise CurlParseError(
                    "Multiple positional values/URLs detected. "
                    "A .curl input must describe one transaction."
                )

            target = validate_target(
                token
            )

        index += 1

    if target is None:
        raise CurlParseError(
            "cURL command does not contain a URL."
        )

    raw_body = (
        "".join(
            body_parts
        )
        if body_parts
        else None
    )

    if method is None:
        method = (
            "POST"
            if raw_body is not None
            else "GET"
        )

    allowed_methods = {
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "HEAD",
        "OPTIONS",
    }

    if method not in allowed_methods:
        raise CurlParseError(
            f"Unsupported HTTP method: {method}"
        )

    body = normalize_body(
        raw_body,
        headers,
    )

    return {
        "method": method,
        "target": target,
        "headers": headers,
        "body": body,
    }


def normalize_scenario(
    value: str,
) -> str:
    allowed = set(
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789-_."
    )

    result = "".join(
        char
        if char in allowed
        else "-"
        for char in value.strip()
    ).strip("-._")

    if not result:
        raise CurlParseError(
            "Scenario name becomes empty after normalization."
        )

    return result


def build_model(
    request: dict[str, Any],
    source: Path,
    scenario: str,
) -> dict[str, Any]:
    parsed = urlparse(
        request["target"]
    )

    transaction: dict[str, Any] = {
        "name": (
            f"{request['method']} "
            f"{parsed.path or '/'}"
        ),
        "method": request[
            "method"
        ],
        "target": request[
            "target"
        ],
        "path": (
            parsed.path
            or "/"
        ),
        "headers": request[
            "headers"
        ],
        "expected_status": [
            200
        ],
    }

    if request[
        "body"
    ] is not None:
        transaction[
            "body"
        ] = request[
            "body"
        ]

    return {
        "schema_version": "1.0",
        "source": {
            "type": "CLI",
            "artifact": str(
                source
            ),
            "format": "CURL",
        },
        "system": {
            "type": "API",
            "base_url": (
                f"{parsed.scheme}://"
                f"{parsed.hostname}"
                + (
                    f":{parsed.port}"
                    if parsed.port is not None
                    else ""
                )
            ),
        },
        "scenarios": [
            {
                "name": scenario,
                "transactions": [
                    transaction
                ],
            }
        ],
        "data": {
            "strategy": "NONE",
            "csv_data_sets": [],
            "parameters": [],
        },
        "runtime": {
            "correlations": [],
        },
        "workload": {
            "source": "EXECUTION_PROFILE",
            "thread_groups": [],
        },
        "assertions": [],
        "observability": [],
        "risks": [],
        "findings": [],
        "summary": {
            "transaction_count": 1,
            "correlation_count": 0,
            "parameter_count": 0,
        },
    }


def write_json_atomic(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    try:
        temporary.write_text(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        json.loads(
            temporary.read_text(
                encoding="utf-8"
            )
        )

        temporary.replace(
            path
        )

    except Exception:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass

        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Parse one cURL request into the governed "
            "normalized CLI performance model."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--scenario",
        required=True,
    )

    args = parser.parse_args()

    source = (
        args.input
        .expanduser()
        .resolve()
    )

    output = (
        args.output
        .expanduser()
        .resolve()
    )

    try:
        scenario = normalize_scenario(
            args.scenario
        )

        text = read_source(
            source
        )

        tokens = tokenize(
            text
        )

        request = parse_curl(
            tokens
        )

        model = build_model(
            request,
            source,
            scenario,
        )

        write_json_atomic(
            output,
            model,
        )

    except (
        CurlParseError,
        OSError,
    ) as exc:
        print(
            f"CURL PARSE ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print("=" * 72)
    print("CURL -> NORMALIZED PERFORMANCE MODEL")
    print("=" * 72)
    print(
        f"Input    : {source}"
    )
    print(
        f"Scenario : {scenario}"
    )
    print(
        f"Method   : {request['method']}"
    )
    print(
        f"Target   : {request['target']}"
    )
    print(
        f"Headers  : {len(request['headers'])}"
    )
    print(
        "Body     : "
        + (
            "JSON"
            if request["body"] is not None
            else "NONE"
        )
    )
    print(
        f"Output   : {output}"
    )
    print("=" * 72)
    print("NORMALIZED MODEL READY")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
