"""Tests del generador de teardowns anonimizados."""
import pathlib

from datanomad_review import teardown
from datanomad_review.billing import diff_snapshots, load_billing_csv

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _gcp_diff():
    before = load_billing_csv(str(FIXTURES / "gcp_before.csv"))
    after = load_billing_csv(str(FIXTURES / "gcp_after.csv"))
    return diff_snapshots(before, after)


def test_anonymize_amount_two_significant_figures():
    assert teardown.anonymize_amount(4437) == "4.400"
    assert teardown.anonymize_amount(12450) == "12.000"
    assert teardown.anonymize_amount(16890) == "17.000"
    assert teardown.anonymize_amount(490) == "490"
    assert teardown.anonymize_amount(0) == "0"


def test_anonymize_projects_stable_labels():
    mapping = teardown.anonymize_projects(["analytics-prod", "core-infra"])

    assert mapping == {"analytics-prod": "proyecto A", "core-infra": "proyecto B"}


def test_teardown_hides_real_project_names():
    out = teardown.generate_teardown(_gcp_diff(), teardown.TeardownOptions())

    assert "analytics-prod" not in out
    assert "core-infra" not in out
    assert "proyecto A" in out


def test_teardown_uses_rounded_amounts_and_hook():
    out = teardown.generate_teardown(_gcp_diff(), teardown.TeardownOptions())

    assert "~$12.000" in out
    assert "~$17.000" in out
    assert "36%" in out
    assert "BigQuery" in out
    assert "(nuevo)" in out
    assert "datanomad-review" in out  # atribución open source


def test_teardown_injects_alias_and_sector():
    opts = teardown.TeardownOptions(alias="una fintech mediana", sector="retail")

    out = teardown.generate_teardown(_gcp_diff(), opts)

    assert "una fintech mediana" in out
    assert "(retail)" in out


def test_breakdown_single_file_mode():
    snapshot = load_billing_csv(str(FIXTURES / "gcp_before.csv"))

    out = teardown.generate_breakdown(snapshot, teardown.TeardownOptions())

    assert "~$12.000" in out
    assert "Compute Engine" in out
    assert "% del total" in out
    assert "analytics-prod" not in out
