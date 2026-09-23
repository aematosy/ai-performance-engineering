from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SKILL = (
    ROOT
    / ".gemini"
    / "skills"
    / "performance-test-designer"
    / "SKILL.md"
)

CONTRACT = (
    ROOT
    / ".gemini"
    / "skills"
    / "performance-test-designer"
    / "references"
    / "command-contract.md"
)

FRONT_DOOR = (
    ROOT
    / "scripts"
    / "natural_performance_design_request.sh"
)

HTTP_FRONT_DOOR = (
    ROOT
    / "scripts"
    / "natural_performance_design_http.sh"
)


def test_skill_documents_real_curl_public_contract():
    text = SKILL.read_text(encoding="utf-8")

    assert "natural_performance_design_request.sh" in text
    assert '--method "<METHOD>"' in text
    assert '--url "<URL>"' in text
    assert '--header "<Header-Name: value>"' in text
    assert "--input-type` NO" in text
    assert "--curl` NO" in text


def test_reference_documents_real_curl_public_contract():
    text = CONTRACT.read_text(encoding="utf-8")

    assert '--method "<METHOD>"' in text
    assert '--url "<URL>"' in text

    assert (
        "`--input-type` NO pertenece al contrato público."
        in text
    )

    assert (
        "`--curl` NO pertenece al contrato público."
        in text
    )


def test_request_router_preserves_arguments_for_http_front_door():
    text = FRONT_DOOR.read_text(encoding="utf-8")

    assert "ORIGINAL_ARGS=(\"$@\")" in text
    assert "natural_performance_design_http.sh" in text
    assert '"${ORIGINAL_ARGS[@]}"' in text


def test_http_front_door_supports_structured_api_contract():
    text = HTTP_FRONT_DOOR.read_text(encoding="utf-8")

    for option in (
        "--scenario)",
        "--method)",
        "--url)",
        "--header)",
        "--body)",
        "--users)",
        "--ramp-time-seconds)",
        "--duration-seconds)",
        "--pacing-seconds)",
    ):
        assert option in text


def test_http_front_door_routes_internally_to_cli_design():
    text = HTTP_FRONT_DOOR.read_text(encoding="utf-8")

    assert "natural_performance_design.sh" in text
    assert '--input "${INPUT}"' in text
