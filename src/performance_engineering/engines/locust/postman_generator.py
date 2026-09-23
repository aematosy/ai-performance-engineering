from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml


class PostmanLocustGenerationError(
    RuntimeError
):
    pass


_SIMPLE_JSON_PATH = re.compile(
    r"^\$(?:\.[A-Za-z_][A-Za-z0-9_-]*|\[[0-9]+\])*$"
)


def _load_json(
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
        raise PostmanLocustGenerationError(
            f"Unable to read JSON: {path}: {exc}"
        ) from exc

    if not isinstance(
        value,
        dict,
    ):
        raise PostmanLocustGenerationError(
            f"JSON root must be an object: {path}"
        )

    return value


def _load_yaml(
    path: Path,
) -> dict[str, Any]:
    try:
        value = yaml.safe_load(
            path.read_text(
                encoding="utf-8"
            )
        )
    except OSError as exc:
        raise PostmanLocustGenerationError(
            f"Unable to read YAML: {path}: {exc}"
        ) from exc

    if not isinstance(
        value,
        dict,
    ):
        raise PostmanLocustGenerationError(
            f"YAML root must be an object: {path}"
        )

    return value


def _canonical_scenario(
    model_path: Path,
) -> str:
    scenario = (
        model_path
        .resolve()
        .parent
        .name
        .strip()
    )

    if not scenario:
        raise PostmanLocustGenerationError(
            "Unable to resolve canonical scenario "
            "from executable model path."
        )

    return scenario


def _normalize_statuses(
    value: Any,
) -> list[int]:
    if (
        value is None
        or (
            isinstance(
                value,
                str,
            )
            and value.strip().upper()
            == "UNRESOLVED"
        )
    ):
        raise PostmanLocustGenerationError(
            "Locust generation requires an explicit "
            "HTTP response contract."
        )

    if isinstance(
        value,
        (list, tuple),
    ):
        raw = list(
            value
        )
    else:
        raw = [
            value
        ]

    if not raw:
        raise PostmanLocustGenerationError(
            "Expected HTTP status cannot be empty."
        )

    result = [
        int(item)
        for item in raw
    ]

    for status in result:
        if not 100 <= status <= 599:
            raise PostmanLocustGenerationError(
                f"Invalid HTTP status: {status}"
            )

    return result


def _transaction_contracts(
    plan: dict[str, Any],
) -> list[dict[str, Any]]:
    transactions = plan.get(
        "transactions",
        []
    )

    if not isinstance(
        transactions,
        list,
    ):
        raise PostmanLocustGenerationError(
            "Plan transactions must be a list."
        )

    result = []

    for transaction in transactions:
        if not isinstance(
            transaction,
            dict,
        ):
            continue

        result.append(
            {
                "name": str(
                    transaction.get(
                        "name",
                        "",
                    )
                    or ""
                ),
                "method": str(
                    transaction.get(
                        "method",
                        "",
                    )
                    or ""
                ).upper(),
                "path": str(
                    transaction.get(
                        "path",
                        "",
                    )
                    or ""
                ),
                "expected_status": (
                    _normalize_statuses(
                        transaction.get(
                            "expected_status"
                        )
                    )
                ),
            }
        )

    return result


def _expected_statuses_for_request(
    *,
    request: dict[str, Any],
    contracts: list[dict[str, Any]],
) -> list[int]:
    request_id = str(
        request.get(
            "id",
            "",
        )
        or ""
    )

    method = str(
        request.get(
            "method",
            "",
        )
        or ""
    ).upper()

    path = str(
        request.get(
            "path",
            "",
        )
        or ""
    )

    for contract in contracts:
        if (
            contract["name"]
            == request_id
        ):
            return list(
                contract[
                    "expected_status"
                ]
            )

    for contract in contracts:
        if (
            contract["method"]
            == method
            and contract["path"]
            == path
        ):
            return list(
                contract[
                    "expected_status"
                ]
            )

    raise PostmanLocustGenerationError(
        "No HTTP response contract found for "
        f"request: {request_id or method + ' ' + path}"
    )


def _validate_extractors(
    requests: list[dict[str, Any]],
) -> None:
    for request in requests:
        request_id = str(
            request.get(
                "id",
                "",
            )
        )

        extractors = request.get(
            "extractors",
            []
        ) or []

        if not isinstance(
            extractors,
            list,
        ):
            raise PostmanLocustGenerationError(
                f"Extractors must be a list: {request_id}"
            )

        for extractor in extractors:
            if not isinstance(
                extractor,
                dict,
            ):
                raise PostmanLocustGenerationError(
                    f"Invalid extractor: {request_id}"
                )

            variable = str(
                extractor.get(
                    "variable",
                    "",
                )
                or ""
            ).strip()

            json_path = str(
                extractor.get(
                    "json_path",
                    "",
                )
                or ""
            ).strip()

            if not variable:
                raise PostmanLocustGenerationError(
                    f"Extractor without variable: {request_id}"
                )

            if not _SIMPLE_JSON_PATH.fullmatch(
                json_path
            ):
                raise PostmanLocustGenerationError(
                    "Unsupported JSONPath for Locust "
                    f"correlation: {json_path!r} "
                    f"in {request_id}"
                )


def _validate_model(
    model: dict[str, Any],
) -> list[dict[str, Any]]:
    source = model.get(
        "source",
        {}
    )

    source_type = str(
        source.get(
            "type",
            "",
        )
        if isinstance(
            source,
            dict,
        )
        else ""
    ).upper()

    if source_type != "POSTMAN":
        raise PostmanLocustGenerationError(
            "Postman Locust generator received "
            f"source type {source_type or 'UNKNOWN'}."
        )

    requests = model.get(
        "requests",
        []
    )

    if (
        not isinstance(
            requests,
            list,
        )
        or not requests
    ):
        raise PostmanLocustGenerationError(
            "Executable Postman model contains "
            "no requests."
        )

    normalized = []

    for request in requests:
        if not isinstance(
            request,
            dict,
        ):
            raise PostmanLocustGenerationError(
                "Executable request must be an object."
            )

        required = (
            "id",
            "method",
            "protocol",
            "host",
            "path",
        )

        missing = [
            key
            for key in required
            if not str(
                request.get(
                    key,
                    "",
                )
                or ""
            ).strip()
        ]

        if missing:
            raise PostmanLocustGenerationError(
                "Executable request is missing fields "
                f"{missing}: {request}"
            )

        normalized.append(
            dict(
                request
            )
        )

    _validate_extractors(
        normalized
    )

    return normalized


def generate_postman_locust(
    *,
    project_root: Path,
    model_path: Path,
    profile_path: Path,
    output: Path,
) -> Path:
    root = project_root.resolve()
    model_path = model_path.resolve()
    profile_path = profile_path.resolve()
    output = output.resolve()

    model = _load_json(
        model_path
    )

    profile = _load_yaml(
        profile_path
    )

    requests = _validate_model(
        model
    )

    scenario = _canonical_scenario(
        model_path
    )

    plan_path = (
        root
        / "tests"
        / "plans"
        / scenario
        / "test-plan.yaml"
    )

    if not plan_path.is_file():
        raise PostmanLocustGenerationError(
            f"Canonical test plan not found: {plan_path}"
        )

    plan = _load_yaml(
        plan_path
    )

    contracts = _transaction_contracts(
        plan
    )

    for request in requests:
        request[
            "expected_status"
        ] = _expected_statuses_for_request(
            request=request,
            contracts=contracts,
        )

    origins = {
        (
            str(
                request[
                    "protocol"
                ]
            ),
            str(
                request[
                    "host"
                ]
            ),
            request.get(
                "port"
            ),
        )
        for request in requests
    }

    if len(
        origins
    ) != 1:
        raise PostmanLocustGenerationError(
            "Postman Locust v1 requires all requests "
            "in one E2E scenario to share the same origin."
        )

    protocol, host, port = next(
        iter(
            origins
        )
    )

    base_url = (
        f"{protocol}://{host}"
        + (
            f":{port}"
            if port
            else ""
        )
    )

    execution = profile.get(
        "execution",
        {}
    )

    if (
        str(
            execution.get(
                "mode",
                "",
            )
        ).upper()
        != "DURATION"
    ):
        raise PostmanLocustGenerationError(
            "Postman Locust execution currently "
            "supports DURATION mode only."
        )

    pacing = float(
        execution.get(
            "pacing_seconds",
            0,
        )
        or 0
    )

    csv_columns = (
        model.get(
            "csv",
            {}
        ).get(
            "columns",
            []
        )
        or []
    )

    csv_path = (
        root
        / "data"
        / scenario
        / "test-data.csv"
    )

    if csv_columns and not csv_path.is_file():
        raise PostmanLocustGenerationError(
            f"Scenario CSV not found: {csv_path}"
        )

    secret_names = (
        model.get(
            "secrets",
            {}
        ).get(
            "jmeter_properties",
            []
        )
        or []
    )

    properties_path = (
        root
        / "data"
        / scenario
        / "secrets.properties"
    )

    if (
        secret_names
        and not properties_path.is_file()
    ):
        raise PostmanLocustGenerationError(
            "Required runtime properties are missing: "
            f"{properties_path}"
        )

    requests_json = json.dumps(
        requests,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    required_secrets_json = json.dumps(
        [
            str(name)
            for name in secret_names
        ],
        ensure_ascii=False,
    )

    source = f'''from __future__ import annotations

import csv
import itertools
import json
import re
from pathlib import Path
from typing import Any

from locust import HttpUser, constant_pacing, task


BASE_URL = {base_url!r}
CSV_PATH = Path({str(csv_path)!r})
PROPERTIES_PATH = Path({str(properties_path)!r})
REQUIRED_PROPERTIES = json.loads({required_secrets_json!r})
REQUESTS = json.loads({requests_json!r})

_RUNTIME_PATTERN = re.compile(
    r"\\$\\{{([A-Za-z_][A-Za-z0-9_]*)\\}}"
)

_PROPERTY_PATTERN = re.compile(
    r"\\$\\{{__P\\(([^,\\)]+),[^\\)]*\\)\\}}"
)


def _load_properties() -> dict[str, str]:
    if not REQUIRED_PROPERTIES:
        return {{}}

    if not PROPERTIES_PATH.is_file():
        raise RuntimeError(
            f"Runtime properties file not found: "
            f"{{PROPERTIES_PATH}}"
        )

    result: dict[str, str] = {{}}

    for raw in PROPERTIES_PATH.read_text(
        encoding="utf-8"
    ).splitlines():
        line = raw.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        key, value = line.split(
            "=",
            1,
        )

        result[
            key.strip()
        ] = value.strip()

    missing = [
        name
        for name in REQUIRED_PROPERTIES
        if not result.get(
            name,
            ""
        )
    ]

    if missing:
        raise RuntimeError(
            "Missing required runtime properties: "
            + ", ".join(
                missing
            )
        )

    return result


def _load_rows() -> list[dict[str, str]]:
    if not CSV_PATH.is_file():
        return [{{}}]

    with CSV_PATH.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(
            csv.DictReader(
                handle
            )
        )

    if not rows:
        raise RuntimeError(
            f"Scenario CSV contains no data rows: "
            f"{{CSV_PATH}}"
        )

    return rows


PROPERTIES = _load_properties()
DATA_ROWS = _load_rows()
DATA_CYCLE = itertools.cycle(
    DATA_ROWS
)


def _typed_value(
    raw: str,
    json_type: str,
) -> Any:
    kind = str(
        json_type
    ).upper()

    if kind == "STRING":
        return raw

    if kind == "INTEGER":
        return int(
            raw
        )

    if kind == "NUMBER":
        return float(
            raw
        )

    if kind == "BOOLEAN":
        normalized = raw.strip().lower()

        if normalized == "true":
            return True

        if normalized == "false":
            return False

        raise RuntimeError(
            f"Invalid BOOLEAN runtime value: {{raw!r}}"
        )

    if kind == "NULL":
        return None

    raise RuntimeError(
        f"Unsupported JSON runtime type: {{json_type}}"
    )


def _render_string(
    value: str,
    runtime: dict[str, Any],
) -> str:
    def property_replacement(
        match: re.Match[str],
    ) -> str:
        name = match.group(
            1
        ).strip()

        if name not in PROPERTIES:
            raise RuntimeError(
                f"Runtime property not configured: {{name}}"
            )

        return PROPERTIES[
            name
        ]

    rendered = _PROPERTY_PATTERN.sub(
        property_replacement,
        value,
    )

    def runtime_replacement(
        match: re.Match[str],
    ) -> str:
        name = match.group(
            1
        )

        if name not in runtime:
            raise RuntimeError(
                f"Runtime correlation not available: {{name}}"
            )

        return str(
            runtime[
                name
            ]
        )

    return _RUNTIME_PATTERN.sub(
        runtime_replacement,
        rendered,
    )


def _render_json(
    value: Any,
    row: dict[str, str],
    runtime: dict[str, Any],
) -> Any:
    if isinstance(
        value,
        dict,
    ):
        parameter = value.get(
            "__runtime_parameter__"
        )

        if parameter is not None:
            name = str(
                parameter
            )

            if name not in row:
                raise RuntimeError(
                    f"CSV runtime parameter not found: {{name}}"
                )

            return _typed_value(
                row[
                    name
                ],
                str(
                    value.get(
                        "__json_type__",
                        "STRING",
                    )
                ),
            )

        return {{
            key: _render_json(
                child,
                row,
                runtime,
            )
            for key, child
            in value.items()
        }}

    if isinstance(
        value,
        list,
    ):
        return [
            _render_json(
                child,
                row,
                runtime,
            )
            for child in value
        ]

    if isinstance(
        value,
        str,
    ):
        return _render_string(
            value,
            runtime,
        )

    return value


def _json_path(
    payload: Any,
    path: str,
) -> Any:
    if path == "$":
        return payload

    if not path.startswith(
        "$"
    ):
        raise RuntimeError(
            f"Unsupported JSONPath: {{path}}"
        )

    current = payload

    tokens = re.findall(
        r"\\.([A-Za-z_][A-Za-z0-9_-]*)|\\[([0-9]+)\\]",
        path[1:],
    )

    consumed = "$"

    for key, index in tokens:
        if key:
            consumed += (
                "."
                + key
            )

            if not isinstance(
                current,
                dict,
            ):
                raise RuntimeError(
                    f"JSONPath cannot resolve {{consumed}}"
                )

            if key not in current:
                raise RuntimeError(
                    f"JSONPath value missing: {{consumed}}"
                )

            current = current[
                key
            ]

        else:
            consumed += (
                "["
                + index
                + "]"
            )

            if not isinstance(
                current,
                list,
            ):
                raise RuntimeError(
                    f"JSONPath cannot resolve {{consumed}}"
                )

            position = int(
                index
            )

            if position >= len(
                current
            ):
                raise RuntimeError(
                    f"JSONPath index missing: {{consumed}}"
                )

            current = current[
                position
            ]

    return current


class PerformanceUser(HttpUser):
    host = BASE_URL
    wait_time = constant_pacing(
        {pacing!r}
    )

    @task
    def execute_scenario(
        self,
    ) -> None:
        row = next(
            DATA_CYCLE
        )

        runtime: dict[
            str,
            Any,
        ] = {{}}

        for request in REQUESTS:
            request_id = str(
                request["id"]
            )

            try:
                path = _render_string(
                    str(
                        request.get(
                            "path",
                            "/",
                        )
                    ),
                    runtime,
                )

                query = str(
                    request.get(
                        "query",
                        "",
                    )
                    or ""
                )

                if query:
                    query = _render_string(
                        query,
                        runtime,
                    )

                    path += (
                        "?"
                        + query
                    )

                headers = {{
                    str(
                        header.get(
                            "name",
                            "",
                        )
                    ): _render_string(
                        str(
                            header.get(
                                "value",
                                "",
                            )
                        ),
                        runtime,
                    )
                    for header in (
                        request.get(
                            "headers",
                            []
                        )
                        or []
                    )
                    if str(
                        header.get(
                            "name",
                            "",
                        )
                    ).strip()
                }}

                body = _render_json(
                    request.get(
                        "json_body"
                    ),
                    row,
                    runtime,
                )

            except Exception as exc:
                raise RuntimeError(
                    f"Unable to materialize request "
                    f"{{request_id}}: {{exc}}"
                ) from exc

            kwargs: dict[
                str,
                Any,
            ] = {{
                "method": str(
                    request.get(
                        "method",
                        "GET",
                    )
                ).upper(),
                "url": path,
                "headers": headers,
                "name": request_id,
                "catch_response": True,
            }}

            if body is not None:
                kwargs[
                    "json"
                ] = body

            with self.client.request(
                **kwargs
            ) as response:
                expected = [
                    int(
                        value
                    )
                    for value
                    in request[
                        "expected_status"
                    ]
                ]

                if response.status_code not in expected:
                    response.failure(
                        f"Expected {{expected}}, "
                        f"received {{response.status_code}}"
                    )

                    return

                extractors = (
                    request.get(
                        "extractors",
                        []
                    )
                    or []
                )

                if not extractors:
                    continue

                try:
                    payload = response.json()
                except Exception:
                    response.failure(
                        "Correlation response is not valid JSON"
                    )

                    return

                for extractor in extractors:
                    variable = str(
                        extractor[
                            "variable"
                        ]
                    )

                    try:
                        extracted = _json_path(
                            payload,
                            str(
                                extractor[
                                    "json_path"
                                ]
                            ),
                        )
                    except Exception as exc:
                        response.failure(
                            f"Missing correlation "
                            f"{{variable}}: {{exc}}"
                        )

                        return

                    if (
                        extracted is None
                        or extracted == ""
                    ):
                        response.failure(
                            f"Missing correlation: {{variable}}"
                        )

                        return

                    runtime[
                        variable
                    ] = extracted
'''

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        source,
        encoding="utf-8",
    )

    return output
