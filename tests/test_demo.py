"""Tests del comando demo (autocontenido, sin red ni credenciales)."""
from datanomad_review import demo
from datanomad_review.cli import main


def test_run_demo_finds_seeded_antipatterns(capsys):
    collected = []

    findings = demo.run_demo(collected.extend)

    codes = {f.code for f in findings}
    assert codes == {"AP-G02", "AP-G02b", "AP-AI01", "AP-C02"}
    assert [f.code for f in collected] == [f.code for f in findings]
    out = capsys.readouterr().out
    assert "DEMO" in out
    assert "scan dbt" in out
    assert "datanomadlab.com" in out


def test_cli_demo_exits_zero_and_prints_findings(capsys):
    rc = main(["demo"])

    assert rc == 0
    out = capsys.readouterr().out
    for code in ("AP-G02", "AP-C02"):
        assert code in out


def test_example_resolves_from_package_resources():
    # El ejemplo debe venir del paquete instalado, no del árbol del repo
    from importlib import resources

    root = resources.files("datanomad_review").joinpath(demo.EXAMPLE_PKG_PATH)
    assert root.joinpath("dbt_project.yml").is_file()
    assert root.joinpath("models/marts/fct_orders.sql").is_file()
