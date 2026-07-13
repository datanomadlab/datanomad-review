"""Tests del estimador de costo de queries BigQuery (dry-run)."""
import sys

import pytest

from datanomad_review import costguard

TIB = 1024 ** 4


class FakeJob:
    def __init__(self, bytes_processed):
        self.total_bytes_processed = bytes_processed


class FakeClient:
    def __init__(self, bytes_by_call=None, raises=None):
        self._bytes = bytes_by_call or TIB
        self._raises = raises

    def query(self, sql, job_config=None):
        if self._raises:
            raise self._raises
        return FakeJob(self._bytes)


def _write_sql(tmp_path, name, content="SELECT 1"):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_one_tib_costs_list_price(tmp_path):
    _write_sql(tmp_path, "query.sql")

    costs = costguard.scan([str(tmp_path)], project="demo",
                           client_factory=lambda: FakeClient(bytes_by_call=TIB))

    assert len(costs) == 1
    assert costs[0].usd == pytest.approx(costguard.ON_DEMAND_USD_PER_TIB)


def test_collect_sql_files_recurses_and_dedupes(tmp_path):
    _write_sql(tmp_path, "a.sql")
    nested = tmp_path / "models"
    nested.mkdir()
    _write_sql(nested, "b.sql")
    (tmp_path / "no.txt").write_text("x")

    files = costguard.collect_sql_files([str(tmp_path), str(tmp_path / "a.sql")])

    assert [f.name for f in files] == ["a.sql", "b.sql"]


def test_jinja_files_are_skipped(tmp_path):
    _write_sql(tmp_path, "model.sql", "SELECT * FROM {{ ref('orders') }}")

    costs = costguard.scan([str(tmp_path)], project="demo",
                           client_factory=lambda: FakeClient())

    assert costs[0].skipped == "jinja"
    assert costs[0].usd == 0.0


def test_invalid_sql_reports_error(tmp_path):
    _write_sql(tmp_path, "broken.sql", "SELEC oops")

    costs = costguard.scan([str(tmp_path)], project="demo",
                           client_factory=lambda: FakeClient(raises=ValueError("syntax")))

    assert "syntax" in costs[0].error


def test_missing_bigquery_dependency_raises(tmp_path, monkeypatch):
    _write_sql(tmp_path, "query.sql")
    monkeypatch.setitem(sys.modules, "google.cloud", None)
    monkeypatch.setitem(sys.modules, "google.cloud.bigquery", None)

    with pytest.raises(costguard.MissingDependencyError) as excinfo:
        costguard.scan([str(tmp_path)], project="demo")

    assert "datanomad-review[gcp]" in str(excinfo.value)


def test_exceeded_threshold():
    costs = [costguard.QueryCost("a.sql", 4 * TIB, 25.0),
             costguard.QueryCost("b.sql", TIB, 6.25)]

    assert costguard.exceeded(costs, fail_over_usd=25.0) is True
    assert costguard.exceeded(costs, fail_over_usd=100.0) is False
    assert costguard.exceeded(costs, fail_over_usd=None) is False


def test_render_github_table_and_threshold():
    costs = [costguard.QueryCost("models/fct_orders.sql", int(4.2 * TIB), 26.25),
             costguard.QueryCost("models/dim_customers.sql", int(0.1 * TIB), 0.63)]

    out = costguard.render_github(costs, fail_over_usd=25.0)

    assert "| Query |" in out
    assert "fct_orders.sql" in out
    assert "**$26.25**" in out        # sobre el umbral -> negrita
    assert "excedido" in out
    assert "dry-run" in out.lower()


def test_render_text_totals():
    costs = [costguard.QueryCost("a.sql", TIB, 6.25),
             costguard.QueryCost("b.sql", 0, 0.0, skipped="jinja")]

    out = costguard.render_text(costs, fail_over_usd=None)

    assert "$6.25" in out
    assert "jinja" in out.lower()
    assert "Total por ejecución" in out
