"""Diff entre dos snapshots de facturación: qué cambió y cuánto pesa cada cambio."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .parse import BillingSnapshot


@dataclass(frozen=True)
class DeltaLine:
    key: str                   # servicio o proyecto
    before: float
    after: float
    delta: float
    pct_of_total_delta: float  # puede ser negativo si va contra la tendencia
    is_new: bool
    is_gone: bool


@dataclass(frozen=True)
class BillingDiff:
    total_before: float
    total_after: float
    delta: float
    growth_pct: Optional[float]  # None si no hay base de comparación
    by_service: tuple            # tuple[DeltaLine, ...] orden abs(delta) desc
    by_project: tuple


def diff_snapshots(before: BillingSnapshot, after: BillingSnapshot) -> BillingDiff:
    total_before, total_after = before.total, after.total
    delta = total_after - total_before
    growth_pct = (delta / total_before * 100) if total_before > 0 else None
    return BillingDiff(
        total_before=total_before,
        total_after=total_after,
        delta=delta,
        growth_pct=round(growth_pct, 2) if growth_pct is not None else None,
        by_service=_delta_lines(before.by_service(), after.by_service(), delta),
        by_project=_delta_lines(before.by_project(), after.by_project(), delta),
    )


def _delta_lines(before: dict, after: dict, total_delta: float) -> tuple:
    lines = []
    for key in set(before) | set(after):
        b, a = before.get(key, 0.0), after.get(key, 0.0)
        d = a - b
        pct = (d / total_delta * 100) if total_delta else 0.0
        lines.append(DeltaLine(
            key=key, before=b, after=a, delta=d,
            pct_of_total_delta=round(pct, 2),
            is_new=key not in before, is_gone=key not in after,
        ))
    return tuple(sorted(lines, key=lambda line: -abs(line.delta)))
