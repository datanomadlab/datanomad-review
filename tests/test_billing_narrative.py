"""Tests de la narrativa en español del billing diff."""
import json
import pathlib

import pytest

from datanomad_review.billing import (
    BillingSnapshot,
    diff_snapshots,
    load_billing_csv,
)
from datanomad_review.billing import narrative

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture()
def gcp_diff():
    before = load_billing_csv(str(FIXTURES / "gcp_before.csv"))
    after = load_billing_csv(str(FIXTURES / "gcp_after.csv"))
    return diff_snapshots(before, after)


def test_text_narrative_explains_increase(gcp_diff):
    out = narrative.render_text(gcp_diff, top=3)

    assert "pasó de $12.450 a $16.890" in out  # punto de miles (marca)
    assert "subió 35.7%" in out
    assert "razones explican el 92% del aumento" in out
    assert "BigQuery" in out
    assert "[nuevo]" in out            # Vertex AI apareció este periodo
    assert "También bajó" in out       # Compute Engine fue a la baja
    assert "analytics-prod" in out     # concentración por proyecto


def test_text_narrative_decrease():
    before = load_billing_csv(str(FIXTURES / "gcp_after.csv"))
    after = load_billing_csv(str(FIXTURES / "gcp_before.csv"))

    out = narrative.render_text(diff_snapshots(before, after))

    assert "bajó" in out


def test_text_narrative_without_base():
    before = BillingSnapshot(records=(), source_format="generic")
    after = load_billing_csv(str(FIXTURES / "generic.csv"))

    out = narrative.render_text(diff_snapshots(before, after))

    assert "base de comparación" in out.lower()


def test_markdown_contains_table(gcp_diff):
    out = narrative.render_markdown(gcp_diff)

    assert "| Servicio |" in out
    assert "| BigQuery |" in out
    assert "datanomad-review" in out


def test_json_round_trip(gcp_diff):
    payload = json.loads(narrative.render_json(gcp_diff))

    assert payload["total_before"] == pytest.approx(12450.0)
    assert payload["total_after"] == pytest.approx(16890.0)
    services = {line["key"]: line for line in payload["by_service"]}
    assert services["Vertex AI"]["is_new"] is True


def test_findings_bill_01_02_03(gcp_diff):
    findings = {f.code: f for f in narrative.findings_from_diff(gcp_diff)}

    assert findings["BILL-01"].severity == "high"      # spike > 25%
    assert findings["BILL-02"].severity == "medium"    # servicio nuevo > 10% del delta
    assert "Vertex AI" in findings["BILL-02"].title
    assert findings["BILL-03"].severity == "medium"    # proyecto concentra > 60%
    assert "analytics-prod" in findings["BILL-03"].title
    assert all(f.dimension == "cost" for f in findings.values())


def test_no_findings_on_small_change():
    before = load_billing_csv(str(FIXTURES / "generic.csv"))

    findings = narrative.findings_from_diff(diff_snapshots(before, before))

    assert findings == []
