"""Narrativa en español del billing diff: por qué cambió la cuenta este mes.

Los montos son datos del propio usuario (su factura), por eso se muestran
completos en la edición open source. La interpretación contra benchmarks
y el roadmap de remediación son terreno del Health Check.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Optional

from ..scorecard import Finding
from .diff import BillingDiff, DeltaLine

SPIKE_THRESHOLD_PCT = 25          # BILL-01: subida alta entre periodos
NEW_SERVICE_THRESHOLD_PCT = 10    # BILL-02: servicio nuevo con peso en el delta
PROJECT_CONCENTRATION_PCT = 60    # BILL-03: un proyecto concentra el delta


def _money(x: float) -> str:
    return f"${x:,.0f}".replace(",", ".")  # punto de miles (convención de marca LATAM)


def _signed(x: float) -> str:
    sign = "+" if x >= 0 else "-"
    return f"{sign}${abs(x):,.0f}".replace(",", ".")


def _direction(delta: float) -> str:
    return "aumento" if delta >= 0 else "baja"


def _headline(d: BillingDiff) -> str:
    if d.growth_pct is None:
        return (f"Sin base de comparación en el primer archivo (total $0): "
                f"el periodo actual suma {_money(d.total_after)}.")
    verb = "subió" if d.delta > 0 else ("bajó" if d.delta < 0 else "se mantuvo")
    if d.delta == 0:
        return f"Tu cuenta se mantuvo en {_money(d.total_after)}."
    return (f"Tu cuenta pasó de {_money(d.total_before)} a {_money(d.total_after)}: "
            f"{verb} {abs(d.growth_pct):.1f}% ({_signed(d.delta)}).")


def _split_drivers(d: BillingDiff, top: int):
    """Separa las líneas que empujan en la dirección del delta de las contrarias."""
    same_sign = [l for l in d.by_service if l.delta * d.delta > 0]
    counter = [l for l in d.by_service if l.delta * d.delta < 0]
    return same_sign[:top], counter


def _driver_detail(line: DeltaLine) -> str:
    if line.is_new:
        return "no existía en el periodo anterior"
    if line.is_gone:
        return "ya no aparece en el periodo actual"
    return f"{_money(line.before)} → {_money(line.after)}"


def _label(line: DeltaLine) -> str:
    if line.is_new:
        return f"{line.key} [nuevo]"
    if line.is_gone:
        return f"{line.key} [eliminado]"
    return line.key


def _top_project(d: BillingDiff) -> Optional[DeltaLine]:
    candidates = [l for l in d.by_project if l.delta * d.delta > 0]
    return candidates[0] if candidates else None


def render_text(d: BillingDiff, top: int = 3) -> str:
    lines = ["", "═══ BILLING DIFF · datanomad-review ═══", "", _headline(d)]
    if d.growth_pct is None or d.delta == 0:
        lines.append("")
        return "\n".join(lines)

    drivers, counter = _split_drivers(d, top)
    if drivers:
        coverage = sum(l.pct_of_total_delta for l in drivers)
        label = "razón explica" if len(drivers) == 1 else "razones explican"
        lines += ["", f"{len(drivers)} {label} el {coverage:.0f}% del {_direction(d.delta)}:"]
        for i, line in enumerate(drivers, 1):
            lines.append(f"  {i}. {_label(line):<24} {_signed(line.delta):>10}   "
                         f"({line.pct_of_total_delta:.0f}% del delta)   {_driver_detail(line)}")
    if counter:
        counter_verb = "bajó" if d.delta > 0 else "subió"
        lines += ["", f"También {counter_verb}:"]
        for line in counter:
            lines.append(f"  · {line.key:<24} {_signed(line.delta):>10}")

    project = _top_project(d)
    if project and abs(project.pct_of_total_delta) >= 40:
        lines += ["", f"Por proyecto: {project.key} concentra el "
                      f"{project.pct_of_total_delta:.0f}% del {_direction(d.delta)}."]
    lines.append("")
    return "\n".join(lines)


def render_markdown(d: BillingDiff, top: int = 5) -> str:
    lines = ["## Billing diff", "", f"**{_headline(d)}**", ""]
    if d.growth_pct is not None and d.delta != 0:
        lines += ["| Servicio | Antes | Después | Δ | % del delta |",
                  "|---|---:|---:|---:|---:|"]
        for line in d.by_service[:top]:
            lines.append(f"| {_label(line)} | {_money(line.before)} | {_money(line.after)} "
                         f"| {_signed(line.delta)} | {line.pct_of_total_delta:.0f}% |")
        project = _top_project(d)
        if project and abs(project.pct_of_total_delta) >= 40:
            lines += ["", f"Por proyecto: **{project.key}** concentra el "
                          f"{project.pct_of_total_delta:.0f}% del {_direction(d.delta)}."]
    lines += ["", "_Generado con datanomad-review (open source, MIT)._", ""]
    return "\n".join(lines)


def render_json(d: BillingDiff) -> str:
    return json.dumps(asdict(d), ensure_ascii=False, indent=2)


def findings_from_diff(d: BillingDiff) -> list:
    """Detección de primer nivel sobre el diff (enganchable por quantifiers pro)."""
    findings = []
    if d.growth_pct is not None and d.growth_pct > SPIKE_THRESHOLD_PCT:
        top_driver = d.by_service[0] if d.by_service else None
        findings.append(Finding(
            "BILL-01",
            f"La cuenta subió {d.growth_pct:.0f}% entre periodos "
            f"({_money(d.total_before)} → {_money(d.total_after)})",
            "high", "cost",
            evidence=(f"driver principal: {top_driver.key} {_signed(top_driver.delta)}"
                      if top_driver else ""),
            fix="Identificar el servicio driver y correr el scanner correspondiente (fase FIND)."))
    if d.delta > 0:
        for line in d.by_service:
            if line.is_new and line.pct_of_total_delta > NEW_SERVICE_THRESHOLD_PCT:
                findings.append(Finding(
                    "BILL-02",
                    f"Servicio nuevo: {line.key} aporta {line.pct_of_total_delta:.0f}% "
                    f"del aumento ({_signed(line.delta)})",
                    "medium", "cost",
                    fix="Confirmar que el servicio fue aprobado y tiene presupuesto asignado."))
        project = _top_project(d)
        if project and project.pct_of_total_delta > PROJECT_CONCENTRATION_PCT:
            findings.append(Finding(
                "BILL-03",
                f"Un solo proyecto ({project.key}) concentra "
                f"{project.pct_of_total_delta:.0f}% del aumento",
                "medium", "cost",
                fix="Atribución de costos por equipo + showback mensual."))
    return findings
