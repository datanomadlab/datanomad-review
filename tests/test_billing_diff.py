"""Tests del diff entre dos snapshots de facturación."""
import pathlib

import pytest

from datanomad_review.billing import diff_snapshots, load_billing_csv

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture()
def gcp_diff():
    before = load_billing_csv(str(FIXTURES / "gcp_before.csv"))
    after = load_billing_csv(str(FIXTURES / "gcp_after.csv"))
    return diff_snapshots(before, after)


def test_totals_and_growth(gcp_diff):
    assert gcp_diff.total_before == pytest.approx(12450.0)
    assert gcp_diff.total_after == pytest.approx(16890.0)
    assert gcp_diff.delta == pytest.approx(4440.0)
    assert gcp_diff.growth_pct == pytest.approx(35.66, abs=0.01)


def test_services_sorted_by_abs_delta(gcp_diff):
    keys = [line.key for line in gcp_diff.by_service]

    assert keys[0] == "BigQuery"          # +2,610
    assert keys[1] == "Cloud Storage"     # +980
    assert keys[-1] == "Compute Engine"   # -120 (menor delta absoluto)


def test_new_service_flagged(gcp_diff):
    vertex = next(l for l in gcp_diff.by_service if l.key == "Vertex AI")

    assert vertex.is_new is True
    assert vertex.before == 0.0
    assert vertex.delta == pytest.approx(490.0)


def test_pct_of_total_delta(gcp_diff):
    bigquery = next(l for l in gcp_diff.by_service if l.key == "BigQuery")

    assert bigquery.pct_of_total_delta == pytest.approx(58.78, abs=0.01)


def test_negative_delta_line(gcp_diff):
    compute = next(l for l in gcp_diff.by_service if l.key == "Compute Engine")

    assert compute.delta == pytest.approx(-120.0)
    assert compute.is_gone is False


def test_by_project_delta(gcp_diff):
    analytics = next(l for l in gcp_diff.by_project if l.key == "analytics-prod")

    assert analytics.delta == pytest.approx(4080.0)
    assert analytics.pct_of_total_delta == pytest.approx(91.89, abs=0.01)


def test_gone_service():
    before = load_billing_csv(str(FIXTURES / "generic.csv"))
    after_records = [l for l in before.records if l.service != "Cloud Storage"]
    after = type(before)(records=tuple(after_records), source_format="generic")

    diff = diff_snapshots(before, after)

    storage = next(l for l in diff.by_service if l.key == "Cloud Storage")
    assert storage.is_gone is True
    assert storage.after == 0.0


def test_growth_pct_none_when_no_base():
    from datanomad_review.billing import BillingSnapshot

    before = BillingSnapshot(records=(), source_format="generic")
    after = load_billing_csv(str(FIXTURES / "generic.csv"))

    diff = diff_snapshots(before, after)

    assert diff.growth_pct is None
    assert diff.delta == pytest.approx(after.total)
