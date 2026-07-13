"""Plugin registry: descubre extensiones instaladas vía entry points.

Un plugin es un paquete que declara:

    [project.entry-points."datanomad_review.plugins"]
    nombre = "mi_paquete.plugin:register"

donde ``register(registry: PluginRegistry) -> None`` puebla los hooks:

- ``quantifiers``: enriquecen findings (p.ej. rellenan ``Finding.impact_usd``).
- ``renderers``: formatos de salida extra (``"html" -> fn(payload, context) -> str``).
- ``subcommands``: agregan subcomandos al CLI (``hook(subparsers) -> None``).
- ``teardown_templates``: plantillas alternativas para el comando ``teardown``.

La edición open source funciona completa sin plugins; los hooks solo amplían.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable

from .scorecard import Finding

GROUP = "datanomad_review.plugins"

PRO_HINT = ("→ Cuantificación en USD, interpretación y roadmap priorizado: "
            "Data Platform Health Check · datanomadlab.com")

Quantifier = Callable[[list], list]
Renderer = Callable[..., str]
SubcommandHook = Callable[..., None]
TeardownTemplate = Callable[..., str]


@dataclass
class PluginRegistry:
    quantifiers: list[Quantifier] = field(default_factory=list)
    renderers: dict[str, Renderer] = field(default_factory=dict)
    subcommands: list[SubcommandHook] = field(default_factory=list)
    teardown_templates: dict[str, TeardownTemplate] = field(default_factory=dict)
    plugin_names: list[str] = field(default_factory=list)


_registry: PluginRegistry | None = None
_hint_shown = False


def _iter_entry_points():
    from importlib.metadata import entry_points
    eps = entry_points()
    if hasattr(eps, "select"):  # Python 3.10+
        return eps.select(group=GROUP)
    return eps.get(GROUP, [])  # Python 3.9


def load_registry(refresh: bool = False) -> PluginRegistry:
    """Singleton perezoso: carga los plugins instalados una sola vez."""
    global _registry
    if _registry is not None and not refresh:
        return _registry
    registry = PluginRegistry()
    for ep in _iter_entry_points():
        try:
            register = ep.load()
            register(registry)
            registry.plugin_names.append(ep.name)
        except Exception as exc:  # un plugin roto no debe tumbar el CLI
            print(f"⚠  plugin '{ep.name}' no se pudo cargar: {exc}", file=sys.stderr)
    _registry = registry
    return registry


def apply_quantifiers(findings: list[Finding]) -> list[Finding]:
    """Pasa los findings por cada quantifier instalado (devuelven lista nueva)."""
    for quantify in load_registry().quantifiers:
        findings = quantify(findings)
    return findings


def pro_hint() -> str | None:
    """Una línea sobria de siguiente paso; solo sin plugins y una vez por proceso."""
    global _hint_shown
    if load_registry().plugin_names or _hint_shown:
        return None
    _hint_shown = True
    return PRO_HINT


def _reset() -> None:
    """Limpia el estado del módulo (para tests)."""
    global _registry, _hint_shown
    _registry = None
    _hint_shown = False
