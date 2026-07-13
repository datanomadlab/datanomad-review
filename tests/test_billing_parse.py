"""Tests del parser de exports de facturación (GCP/AWS/generic)."""
import pathlib

import pytest

from datanomad_review.billing import (
    BillingFormatError,
    detect_format,
    load_billing_csv,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def test_detects_gcp_cost_table_with_bom():
    snapshot = load_billing_csv(str(FIXTURES / "gcp_before.csv"))

    assert snapshot.source_format == "gcp-cost-table"
    assert snapshot.total == pytest.approx(12450.0)


def test_gcp_prefers_subtotal_over_cost_column():
    # gcp_before: Cost($) de BigQuery es 4,350 pero Subtotal($) es 4,120
    snapshot = load_billing_csv(str(FIXTURES / "gcp_before.csv"))

    assert snapshot.by_service()["BigQuery"] == pytest.approx(4120.0)


def test_gcp_uses_project_name():
    snapshot = load_billing_csv(str(FIXTURES / "gcp_before.csv"))

    by_project = snapshot.by_project()
    assert by_project["analytics-prod"] == pytest.approx(6220.0)
    assert by_project["core-infra"] == pytest.approx(6230.0)


def test_gcp_skips_total_row():
    snapshot = load_billing_csv(str(FIXTURES / "gcp_after.csv"))

    assert "Total" not in snapshot.by_service()
    assert snapshot.total == pytest.approx(16890.0)


def test_detects_aws_cur_and_aggregates_line_items():
    snapshot = load_billing_csv(str(FIXTURES / "aws_cur.csv"))

    assert snapshot.source_format == "aws-cur"
    by_service = snapshot.by_service()
    assert by_service["AmazonEC2"] == pytest.approx(2000.0)
    # la fila con costo no numérico se salta, no revienta
    assert by_service["AmazonRDS"] == pytest.approx(1500.0)
    assert snapshot.by_project()["111122223333"] == pytest.approx(2500.0)


def test_detects_aws_cost_explorer_csv():
    snapshot = load_billing_csv(str(FIXTURES / "aws_ce.csv"))

    assert snapshot.source_format == "aws-ce"
    assert snapshot.total == pytest.approx(2620.75)
    assert "Total costs ($)" not in snapshot.by_service()


def test_detects_generic_format():
    snapshot = load_billing_csv(str(FIXTURES / "generic.csv"))

    assert snapshot.source_format == "generic"
    assert snapshot.by_service()["BigQuery"] == pytest.approx(125.0)
    assert snapshot.by_project()["proj-b"] == pytest.approx(75.5)


def test_unknown_format_raises_with_expected_columns():
    with pytest.raises(BillingFormatError) as excinfo:
        load_billing_csv(str(FIXTURES / "malformed.csv"))

    message = str(excinfo.value)
    assert "gcp-cost-table" in message
    assert "generic" in message


def test_empty_file_raises(tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_text("")

    with pytest.raises(BillingFormatError):
        load_billing_csv(str(empty))


def test_detect_format_is_case_insensitive():
    assert detect_format(["SERVICE DESCRIPTION", "Cost ($)"]) == "gcp-cost-table"
    assert detect_format(["service", "cost", "project"]) == "generic"
    assert detect_format(["lineItem/UnblendedCost"]) == "aws-cur"
    assert detect_format(["Service", "2026-06-01"]) == "aws-ce"
    assert detect_format(["fecha", "monto"]) is None
