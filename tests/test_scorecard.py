"""Tests del motor de scorecard y de la carga del framework empaquetado."""
import pathlib

import pytest

from datanomad_review.scorecard import Finding, Scorecard


def test_load_definition_from_package_resources():
    # Arrange / Act — sin path: debe resolver desde los datos del paquete,
    # no desde el directorio del repo (crítico para instalaciones con wheel)
    definition = Scorecard.load_definition()

    # Assert
    assert "dimensions" in definition
    assert set(definition["dimensions"]) >= {
        "architecture", "governance", "quality", "cost",
        "scalability", "security", "ai_readiness",
    }
    weights = [d.get("weight", 0) for d in definition["dimensions"].values()]
    assert pytest.approx(sum(weights), abs=0.01) == 1.0


def test_load_definition_from_explicit_path(tmp_path: pathlib.Path):
    yaml_file = tmp_path / "custom.yaml"
    yaml_file.write_text("dimensions:\n  cost:\n    name: Costo\n    weight: 1.0\n")

    definition = Scorecard.load_definition(yaml_file)

    assert definition["dimensions"]["cost"]["name"] == "Costo"


def test_overall_weights_scores_by_dimension():
    definition = {
        "dimensions": {
            "cost": {"name": "Costo", "weight": 0.75},
            "quality": {"name": "Calidad", "weight": 0.25},
        }
    }
    card = Scorecard(scores={"cost": 80.0, "quality": 40.0})

    assert card.overall(definition) == 70.0


def test_overall_ignores_missing_dimensions():
    definition = {
        "dimensions": {
            "cost": {"name": "Costo", "weight": 0.5},
            "quality": {"name": "Calidad", "weight": 0.5},
        }
    }
    card = Scorecard(scores={"cost": 60.0})

    assert card.overall(definition) == 60.0


def test_render_includes_findings_sorted_by_severity():
    card = Scorecard(findings=[
        Finding("AP-X2", "Medio", "medium", "cost"),
        Finding("AP-X1", "Crítico", "critical", "cost", evidence="tabla_x", fix="particionar"),
    ])

    out = card.render({"dimensions": {}})

    assert out.index("AP-X1") < out.index("AP-X2")
    assert "evidencia: tabla_x" in out
    assert "fix: particionar" in out
