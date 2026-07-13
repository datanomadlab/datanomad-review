"""Generador de teardowns anonimizados desde exports de facturación.

Produce markdown listo para publicar (LinkedIn/newsletter). La anonimización
vive en código, no en disciplina manual: montos redondeados a 2 cifras
significativas, porcentajes enteros y nombres de proyecto reemplazados por
"proyecto A/B/C". IDs de cuenta y emails nunca llegan aquí (se descartan
en el parse de billing).
"""
from __future__ import annotations

import string
from dataclasses import dataclass
from math import floor, log10
from typing import Optional, Sequence

from .billing import BillingDiff, BillingSnapshot, DeltaLine

TOP_DRIVERS = 3
SERVICE_MAJORITY_PCT = 50
NEW_SERVICE_PCT = 10
PROJECT_CONCENTRATION_PCT = 60

ATTRIBUTION = ("_Números redondeados y anonimizados. "
               "Generado con datanomad-review (open source, MIT)._")


@dataclass(frozen=True)
class TeardownOptions:
    alias: str = "una empresa mediana de LATAM"
    sector: str = ""
    template: str = "default"


def anonymize_amount(x: float) -> str:
    """Redondea a 2 cifras significativas y formatea con punto de miles."""
    magnitude = abs(x)
    if magnitude == 0:
        return "0"
    digits = 1 - int(floor(log10(magnitude)))
    rounded = round(magnitude, digits)
    return f"{rounded:,.0f}".replace(",", ".")


def anonymize_projects(names: Sequence[str]) -> dict:
    """Mapea nombres reales a 'proyecto A/B/C' estable según el orden dado."""
    letters = string.ascii_uppercase
    return {name: f"proyecto {letters[i % len(letters)]}"
            for i, name in enumerate(names)}


def _title(opts: TeardownOptions) -> str:
    sector = f" ({opts.sector})" if opts.sector else ""
    return f"## Teardown: la factura cloud de {opts.alias}{sector}"


def _service_label(line: DeltaLine) -> str:
    return f"**{line.key}** (nuevo)" if line.is_new else f"**{line.key}**"


def _top_project(d: BillingDiff) -> Optional[DeltaLine]:
    candidates = [l for l in d.by_project if l.delta * d.delta > 0]
    return candidates[0] if candidates else None


def _lessons(d: BillingDiff, project_alias: dict) -> list:
    lessons = []
    top = d.by_service[0] if d.by_service else None
    if top and top.pct_of_total_delta > SERVICE_MAJORITY_PCT:
        lessons.append(f"Un solo servicio ({top.key}) explica más de la mitad del delta "
                       "→ nadie está mirando su costo unitario.")
    for line in d.by_service:
        if line.is_new and line.pct_of_total_delta > NEW_SERVICE_PCT:
            lessons.append(f"Apareció {line.key} sin presupuesto visible "
                           "→ las altas de servicios no pasan por gobernanza.")
    project = _top_project(d)
    if project and project.pct_of_total_delta > PROJECT_CONCENTRATION_PCT:
        alias = project_alias.get(project.key, project.key)
        lessons.append(f"Un solo equipo ({alias}) concentra el "
                       f"{project.pct_of_total_delta:.0f}% del aumento "
                       "→ falta atribución de costos por equipo.")
    return lessons


def generate_teardown(d: BillingDiff, opts: TeardownOptions) -> str:
    """Modo estrella: dos periodos, narrativa de por qué cambió la cuenta."""
    project_alias = anonymize_projects([l.key for l in d.by_project])
    verb = "subió" if d.delta >= 0 else "bajó"
    pct = f"{abs(d.growth_pct):.0f}%" if d.growth_pct is not None else "—"

    lines = [_title(opts), "",
             f"**La cuenta {verb} {pct} en un mes: de ~${anonymize_amount(d.total_before)} "
             f"a ~${anonymize_amount(d.total_after)}.**", "",
             "Dónde se fue la plata:"]
    drivers = [l for l in d.by_service if l.delta * d.delta > 0][:TOP_DRIVERS]
    for i, line in enumerate(drivers, 1):
        sign = "+" if line.delta >= 0 else "-"
        lines.append(f"{i}. {_service_label(line)} {sign}${anonymize_amount(line.delta)} "
                     f"— {abs(line.pct_of_total_delta):.0f}% del {'aumento' if d.delta >= 0 else 'ahorro'}")

    lessons = _lessons(d, project_alias)
    if lessons:
        lines += ["", "Primer nivel de lectura:"]
        lines += [f"- {lesson}" for lesson in lessons]

    lines += ["", ATTRIBUTION, ""]
    return "\n".join(lines)


def generate_breakdown(snapshot: BillingSnapshot, opts: TeardownOptions) -> str:
    """Modo un archivo: radiografía de dónde está la plata en un periodo."""
    total = snapshot.total
    by_service = sorted(snapshot.by_service().items(), key=lambda kv: -kv[1])

    lines = [_title(opts), "",
             f"**La cuenta del periodo suma ~${anonymize_amount(total)}.**", "",
             "Dónde está la plata:"]
    for i, (service, cost) in enumerate(by_service[:TOP_DRIVERS], 1):
        share = cost / total * 100 if total else 0
        lines.append(f"{i}. **{service}** ~${anonymize_amount(cost)} — {share:.0f}% del total")

    lines += ["", ATTRIBUTION, ""]
    return "\n".join(lines)
