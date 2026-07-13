"""Tests del registry de plugins (entry points datanomad_review.plugins)."""
import pytest

from datanomad_review import plugins
from datanomad_review.scorecard import Finding


@pytest.fixture(autouse=True)
def clean_registry():
    plugins._reset()
    yield
    plugins._reset()


class FakeEntryPoint:
    def __init__(self, register, name="pro"):
        self.name = name
        self._register = register

    def load(self):
        return self._register


def test_registry_empty_without_plugins(monkeypatch):
    # Arrange
    monkeypatch.setattr(plugins, "_iter_entry_points", lambda: [])

    # Act
    reg = plugins.load_registry(refresh=True)

    # Assert
    assert reg.quantifiers == []
    assert reg.renderers == {}
    assert reg.subcommands == []
    assert reg.teardown_templates == {}
    assert reg.plugin_names == []


def test_plugin_registers_hooks(monkeypatch):
    def register(reg):
        reg.quantifiers.append(lambda findings: findings)
        reg.renderers["html"] = lambda findings, context: "<html></html>"

    monkeypatch.setattr(plugins, "_iter_entry_points",
                        lambda: [FakeEntryPoint(register)])

    reg = plugins.load_registry(refresh=True)

    assert len(reg.quantifiers) == 1
    assert "html" in reg.renderers
    assert reg.plugin_names == ["pro"]


def test_apply_quantifiers_enriches_findings(monkeypatch):
    def quantify(findings):
        return [Finding(f.code, f.title, f.severity, f.dimension,
                        f.evidence, f.fix, impact_usd="$800-1,400/mes")
                for f in findings]

    monkeypatch.setattr(plugins, "_iter_entry_points",
                        lambda: [FakeEntryPoint(lambda reg: reg.quantifiers.append(quantify))])
    plugins.load_registry(refresh=True)

    out = plugins.apply_quantifiers([Finding("AP-C01", "Tabla grande", "high", "cost")])

    assert out[0].impact_usd == "$800-1,400/mes"


def test_finding_render_includes_impact_usd():
    finding = Finding("AP-C01", "Tabla grande sin particionar", "high", "cost",
                      impact_usd="$800-1,400/mes")

    assert "impacto: $800-1,400/mes" in finding.render()


def test_finding_render_omits_empty_impact():
    finding = Finding("AP-C01", "Tabla grande sin particionar", "high", "cost")

    assert "impacto" not in finding.render()


def test_pro_hint_shows_once_without_plugins(monkeypatch):
    monkeypatch.setattr(plugins, "_iter_entry_points", lambda: [])
    plugins.load_registry(refresh=True)

    assert plugins.pro_hint() == plugins.PRO_HINT
    assert plugins.pro_hint() is None


def test_pro_hint_silent_with_plugin_installed(monkeypatch):
    monkeypatch.setattr(plugins, "_iter_entry_points",
                        lambda: [FakeEntryPoint(lambda reg: None)])
    plugins.load_registry(refresh=True)

    assert plugins.pro_hint() is None


def test_broken_plugin_does_not_crash(monkeypatch, capsys):
    class BrokenEntryPoint:
        name = "broken"

        def load(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(plugins, "_iter_entry_points", lambda: [BrokenEntryPoint()])

    reg = plugins.load_registry(refresh=True)

    assert reg.plugin_names == []
    assert "broken" in capsys.readouterr().err
