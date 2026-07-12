"""Tests del scanner estático de proyectos dbt."""
import pathlib

from datanomad_review.checks import dbt_project

EXAMPLE = pathlib.Path(__file__).resolve().parents[1] / "examples" / "sample-dbt-project"


def test_scan_sample_project_detects_seeded_antipatterns():
    findings = dbt_project.scan(str(EXAMPLE))

    codes = {f.code for f in findings}
    assert codes == {"AP-G02", "AP-G02b", "AP-AI01", "AP-C02"}


def test_scan_reports_test_coverage_evidence():
    findings = dbt_project.scan(str(EXAMPLE))

    g02 = next(f for f in findings if f.code == "AP-G02")
    assert g02.severity in ("high", "medium")
    assert g02.dimension == "quality"
    assert "fct_orders" in g02.evidence


def test_scan_missing_project_returns_dbt00(tmp_path: pathlib.Path):
    findings = dbt_project.scan(str(tmp_path / "no-existe"))

    assert len(findings) == 1
    assert findings[0].code == "DBT-00"
    assert findings[0].severity == "high"


def test_select_star_in_staging_is_allowed(tmp_path: pathlib.Path):
    # Arrange: proyecto mínimo con SELECT * solo en staging
    (tmp_path / "models" / "staging").mkdir(parents=True)
    (tmp_path / "dbt_project.yml").write_text("name: t\n")
    (tmp_path / "models" / "staging" / "stg_x.sql").write_text("select * from source_x")

    # Act
    findings = dbt_project.scan(str(tmp_path))

    # Assert: staging puede usar SELECT *; no debe aparecer AP-C02
    assert "AP-C02" not in {f.code for f in findings}
