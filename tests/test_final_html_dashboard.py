from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source() -> str:
    return (
        ROOT
        / "scripts"
        / "generate_report.py"
    ).read_text(
        encoding="utf-8"
    )


def test_primary_row_contains_six_useful_kpis():
    text = source()

    start = text.index(
        '<section class="cards pe-kpi-grid pe-kpi-primary">'
    )

    end = text.index(
        "</section>",
        start,
    )

    primary = text[start:end]

    expected = (
        "Resultado SLA",
        "Motor de ejecución",
        "Tasa de éxito",
        "Throughput",
        "p95",
        "p99",
    )

    for label in expected:
        assert label in primary

    assert "Errores de ejecución" not in primary
    assert "Clasificación" not in primary
    assert "Baseline" not in primary


def test_secondary_row_contains_non_redundant_kpis():
    text = source()

    start = text.index(
        '<section class="cards pe-kpi-grid pe-kpi-secondary">'
    )

    end = text.index(
        "</section>",
        start,
    )

    secondary = text[start:end]

    expected = (
        "Solicitudes totales",
        "Solicitudes exitosas",
        "Solicitudes fallidas",
        "Latencia promedio",
        "Latencia máxima",
        "p90",
    )

    for label in expected:
        assert label in secondary

    assert (
        '<div class="card-label">Transacciones</div>'
        not in secondary
    )


def test_status_color_is_dynamic():
    text = source()

    assert "sla_state_class" in text
    assert "failed_state_class" in text

    assert '"pe-status-pass"' in text
    assert '"pe-status-fail"' in text

    assert (
        'if verdict == "PASS"'
        in text
    )

    assert (
        'if error_count > 0'
        in text
    )


def test_engine_is_present():
    text = source()

    assert "engine_label" in text
    assert "LOCUST" in text
    assert "JMETER" in text
    assert "Motor de ejecución" in text


def test_long_values_are_protected_from_overflow():
    text = source()

    assert "overflow-wrap: anywhere" in text
    assert "font-size: clamp(" in text


def test_old_error_kpi_does_not_exist():
    text = source()

    assert (
        '<div class="card-label">Errores de ejecución</div>'
        not in text
    )
