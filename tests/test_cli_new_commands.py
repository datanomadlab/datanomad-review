"""Tests de los subcomandos nuevos del CLI (billing-diff, teardown, query-cost)."""
import pathlib
import sys

import pytest

from datanomad_review import cli, costguard, plugins

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
BEFORE = str(FIXTURES / "gcp_before.csv")
AFTER = str(FIXTURES / "gcp_after.csv")


@pytest.fixture(autouse=True)
def clean_plugins(monkeypatch):
    plugins._reset()
    monkeypatch.setattr(plugins, "_iter_entry_points", lambda: [])
    yield
    plugins._reset()


def test_billing_diff_text(capsys):
    code = cli.main(["billing-diff", BEFORE, AFTER])

    out = capsys.readouterr().out
    assert code == 0
    assert "BILLING DIFF" in out
    assert "subió 35.7%" in out
    assert plugins.PRO_HINT in out  # hint sobrio al final del output exitoso


def test_billing_diff_json_is_clean(capsys):
    import json

    code = cli.main(["billing-diff", BEFORE, AFTER, "--format", "json"])

    out = capsys.readouterr().out
    assert code == 0
    json.loads(out)  # sin hint que ensucie el JSON


def test_billing_diff_html_without_pro(capsys):
    code = cli.main(["billing-diff", BEFORE, AFTER, "--format", "html"])

    err = capsys.readouterr().err
    assert code == 2
    assert "no disponible en la edición open source" in err
    assert "Health Check" in err


def test_billing_diff_bad_file(capsys, tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n")

    code = cli.main(["billing-diff", str(bad), AFTER])

    assert code == 2
    assert "no reconozco las columnas" in capsys.readouterr().err


def test_teardown_single_file(capsys):
    code = cli.main(["teardown", BEFORE])

    out = capsys.readouterr().out
    assert code == 0
    assert "## Teardown" in out


def test_teardown_writes_output_file(tmp_path, capsys):
    target = tmp_path / "teardown.md"

    code = cli.main(["teardown", BEFORE, AFTER, "-o", str(target)])

    assert code == 0
    assert "## Teardown" in target.read_text(encoding="utf-8")


def test_teardown_unknown_template(capsys):
    code = cli.main(["teardown", BEFORE, AFTER, "--template", "nope"])

    assert code == 2
    assert "Plantilla 'nope' no disponible" in capsys.readouterr().err


def test_query_cost_exit_1_over_threshold(monkeypatch, capsys):
    fake = [costguard.QueryCost("a.sql", 0, 26.25)]
    monkeypatch.setattr(costguard, "scan", lambda *a, **k: fake)

    code = cli.main(["query-cost", "a.sql", "--project", "demo",
                     "--fail-over-usd", "25"])

    assert code == 1
    assert "excedido" in capsys.readouterr().out


def test_query_cost_exit_0_under_threshold(monkeypatch, capsys):
    fake = [costguard.QueryCost("a.sql", 0, 1.10)]
    monkeypatch.setattr(costguard, "scan", lambda *a, **k: fake)

    code = cli.main(["query-cost", "a.sql", "--project", "demo",
                     "--fail-over-usd", "25"])

    assert code == 0


def test_query_cost_missing_dependency(monkeypatch, capsys):
    def raise_missing(*args, **kwargs):
        raise costguard.MissingDependencyError("google-cloud-bigquery no instalado. "
                                               "Usa: pip install 'datanomad-review[gcp]'")
    monkeypatch.setattr(costguard, "scan", raise_missing)

    code = cli.main(["query-cost", "a.sql", "--project", "demo"])

    assert code == 2
    assert "datanomad-review[gcp]" in capsys.readouterr().err


def test_standalone_billing_diff_entry(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["datanomad-billing-diff", BEFORE, AFTER])

    code = cli.billing_diff_entry()

    assert code == 0
    assert "BILLING DIFF" in capsys.readouterr().out
