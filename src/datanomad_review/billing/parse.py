"""Parsers de exports de facturación (GCP/AWS) a un modelo común.

Formatos soportados (auto-detección por header) — ver docs/billing-formats.md:

- ``gcp-cost-table``: descarga "Cost table" de la consola de GCP Billing.
- ``aws-cur``: AWS Cost and Usage Report (columnas ``lineItem/*``).
- ``aws-ce``: CSV de AWS Cost Explorer agrupado por servicio.
- ``generic``: ``service,cost[,project]`` — escape hatch para cualquier fuente.

Solo se conservan servicio, costo y proyecto/cuenta; IDs de línea, emails
y cualquier otro campo se descartan en el parse (nunca llegan a un reporte).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import Callable, Iterable, Optional


class BillingFormatError(ValueError):
    """El CSV no coincide con ningún formato de facturación soportado."""


@dataclass(frozen=True)
class BillingRecord:
    service: str
    cost: float
    project: str = ""  # GCP project name / AWS account id


@dataclass(frozen=True)
class BillingSnapshot:
    records: tuple  # tuple[BillingRecord, ...]
    source_format: str
    path: str = ""

    @property
    def total(self) -> float:
        return sum(r.cost for r in self.records)

    def by_service(self) -> dict:
        return _aggregate(self.records, lambda r: r.service)

    def by_project(self) -> dict:
        return _aggregate((r for r in self.records if r.project), lambda r: r.project)


def _aggregate(records: Iterable[BillingRecord], key: Callable) -> dict:
    totals: dict = {}
    for record in records:
        totals[key(record)] = totals.get(key(record), 0.0) + record.cost
    return totals


def detect_format(header: list) -> Optional[str]:
    lowered = [h.strip().lower() for h in header]
    if "service description" in lowered:
        return "gcp-cost-table"
    if "lineitem/unblendedcost" in lowered:
        return "aws-cur"
    if lowered in (["service", "cost"], ["service", "cost", "project"]):
        return "generic"
    if lowered and lowered[0] == "service":
        return "aws-ce"
    return None


def load_billing_csv(path: str) -> BillingSnapshot:
    """Carga un export de facturación; lanza BillingFormatError si no lo reconoce."""
    with open(path, newline="", encoding="utf-8-sig") as fh:  # utf-8-sig: BOM-safe
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            raise BillingFormatError(f"{path}: el archivo está vacío") from None
        source_format = detect_format(header)
        if source_format is None:
            raise BillingFormatError(
                f"{path}: no reconozco las columnas {header[:6]}. Formatos soportados: "
                "gcp-cost-table (columna 'Service description'), "
                "aws-cur (columna 'lineItem/UnblendedCost'), "
                "aws-ce (primera columna 'Service'), "
                "generic (columnas exactas 'service,cost[,project]'). "
                "Detalle: docs/billing-formats.md"
            )
        rows = list(reader)
    records = _PARSERS[source_format](header, rows)
    return BillingSnapshot(records=tuple(records), source_format=source_format, path=path)


TOTAL_LABELS = {"total", "total costs ($)", "total cost ($)"}


def _parse_cost(raw: str) -> Optional[float]:
    cleaned = raw.strip().replace("$", "").replace(",", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _column_index(header: list, name: str) -> Optional[int]:
    lowered = [h.strip().lower() for h in header]
    return lowered.index(name) if name in lowered else None


def _is_total_row(service: str) -> bool:
    return not service or service.strip().lower() in TOTAL_LABELS


def _parse_gcp_cost_table(header: list, rows: list) -> list:
    service_idx = _column_index(header, "service description")
    cost_idx = _column_index(header, "subtotal ($)")
    if cost_idx is None:  # exports sin descuentos no traen Subtotal
        cost_idx = next(i for i, h in enumerate(header)
                        if h.strip().lower().startswith("cost"))
    project_idx = _column_index(header, "project name")
    if project_idx is None:
        project_idx = _column_index(header, "project id")

    records = []
    for row in rows:
        if len(row) <= max(service_idx, cost_idx):
            continue
        service = row[service_idx].strip()
        cost = _parse_cost(row[cost_idx])
        if _is_total_row(service) or cost is None:
            continue
        project = row[project_idx].strip() if project_idx is not None else ""
        records.append(BillingRecord(service=service, cost=cost, project=project))
    return records


def _parse_aws_cur(header: list, rows: list) -> list:
    service_idx = _column_index(header, "lineitem/productcode")
    cost_idx = _column_index(header, "lineitem/unblendedcost")
    account_idx = _column_index(header, "lineitem/usageaccountid")

    records = []
    for row in rows:
        if len(row) <= max(i for i in (service_idx, cost_idx) if i is not None):
            continue
        service = row[service_idx].strip() if service_idx is not None else ""
        cost = _parse_cost(row[cost_idx])
        if _is_total_row(service) or cost is None:
            continue
        account = row[account_idx].strip() if account_idx is not None else ""
        records.append(BillingRecord(service=service, cost=cost, project=account))
    return records


def _parse_aws_ce(header: list, rows: list) -> list:
    records = []
    for row in rows:
        if not row:
            continue
        service = row[0].strip()
        if _is_total_row(service):
            continue
        cost = next((c for c in (_parse_cost(cell) for cell in reversed(row[1:]))
                     if c is not None), None)
        if cost is None:
            continue
        records.append(BillingRecord(service=service, cost=cost))
    return records


def _parse_generic(header: list, rows: list) -> list:
    has_project = len(header) >= 3
    records = []
    for row in rows:
        if len(row) < 2:
            continue
        service = row[0].strip()
        cost = _parse_cost(row[1])
        if _is_total_row(service) or cost is None:
            continue
        project = row[2].strip() if has_project and len(row) > 2 else ""
        records.append(BillingRecord(service=service, cost=cost, project=project))
    return records


_PARSERS = {
    "gcp-cost-table": _parse_gcp_cost_table,
    "aws-cur": _parse_aws_cur,
    "aws-ce": _parse_aws_ce,
    "generic": _parse_generic,
}
