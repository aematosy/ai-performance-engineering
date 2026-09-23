from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_report_uses_pass_fail_language():
    interpreter = (
        ROOT
        / ".gemini"
        / "skills"
        / "performance-report-interpreter"
        / "scripts"
        / "interpret_results.py"
    ).read_text(encoding="utf-8")

    pdf = (
        ROOT
        / ".gemini"
        / "skills"
        / "performance-report-interpreter"
        / "scripts"
        / "generate_professional_pdf.py"
    ).read_text(encoding="utf-8")

    assert '"PASS": "Cumple"' not in interpreter
    assert '"FAIL": "No cumple"' not in interpreter
    assert 'status_text = "Cumple"' not in pdf
    assert '"RESULTADO SLA"' in pdf
    assert '"ERRORES DE EJECUCIÓN"' in pdf
    assert '"ESTADO FUNCIONAL"' in pdf


def test_html_exposes_execution_semantics():
    source = (
        ROOT
        / "scripts"
        / "generate_report.py"
    ).read_text(encoding="utf-8")

    assert "Resultado SLA" in source
    assert "Motor de ejecución" in source
    assert "Solicitudes fallidas" in source
    assert "Estado funcional" in source
    assert "Con incidencias" in source
    assert "Sin incidencias" in source

    # El KPI redundante fue eliminado deliberadamente.
    assert (
        '<div class="card-label">Errores de ejecución</div>'
        not in source
    )

    assert (
        "El escenario cumple los SLA configurados."
        not in source
    )

    assert (
        "No aumentar concurrencia o duración"
        in source
    )


def test_recommendations_are_error_aware():
    source = (
        ROOT
        / ".gemini"
        / "skills"
        / "performance-report-interpreter"
        / "scripts"
        / "interpret_results.py"
    ).read_text(encoding="utf-8")

    assert "Aunque el resultado SLA global sea PASS" in source
    assert "No aumentar la carga" in source
