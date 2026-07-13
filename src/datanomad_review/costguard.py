"""Estimación de costo de queries BigQuery vía dry-run (read-only).

Un dry-run no ejecuta la query ni factura: BigQuery devuelve cuántos bytes
escanearía. El costo estimado usa el precio de lista público on-demand.
Pensado para CI (GitHub Action) y pre-commit: bloquear el desperdicio antes
de que ocurra.
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass
from typing import Callable, Optional, Sequence

ON_DEMAND_USD_PER_TIB = 6.25  # precio de lista público BigQuery on-demand (USD/TiB)
_TIB = 1024 ** 4

JINJA_NOTE = "Jinja sin compilar: corre `dbt compile` y apunta a target/compiled/"


class MissingDependencyError(RuntimeError):
    """Falta el SDK de BigQuery para hacer el dry-run."""


@dataclass(frozen=True)
class QueryCost:
    path: str
    bytes_processed: int
    usd: float
    skipped: str = ""   # "jinja" si el archivo tiene templating sin compilar
    error: str = ""     # SQL inválido según el dry-run


def collect_sql_files(paths: Sequence[str]) -> list:
    files = []
    for raw in paths:
        path = pathlib.Path(raw)
        if path.is_dir():
            files.extend(path.rglob("*.sql"))
        elif path.suffix == ".sql":
            files.append(path)
    return sorted(set(files))


def scan(paths: Sequence[str], project: str,
         price_per_tib: float = ON_DEMAND_USD_PER_TIB,
         client_factory: Optional[Callable] = None) -> list:
    """Dry-run de cada .sql encontrado; nunca ejecuta las queries."""
    if client_factory is not None:
        client, job_config = client_factory(), None
    else:
        try:
            from google.cloud import bigquery  # type: ignore
        except ImportError:
            raise MissingDependencyError(
                "google-cloud-bigquery no instalado. "
                "Usa: pip install 'datanomad-review[gcp]'") from None
        client = bigquery.Client(project=project)
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)

    results = []
    for path in collect_sql_files(paths):
        sql = path.read_text(encoding="utf-8")
        if "{{" in sql or "{%" in sql:
            results.append(QueryCost(str(path), 0, 0.0, skipped="jinja"))
            continue
        try:
            job = client.query(sql, job_config=job_config)
            bytes_processed = job.total_bytes_processed or 0
        except Exception as exc:
            results.append(QueryCost(str(path), 0, 0.0, error=str(exc)))
            continue
        usd = round(bytes_processed / _TIB * price_per_tib, 2)
        results.append(QueryCost(str(path), bytes_processed, usd))
    return results


def total_usd(costs: Sequence[QueryCost]) -> float:
    return round(sum(c.usd for c in costs), 2)


def exceeded(costs: Sequence[QueryCost], fail_over_usd: Optional[float]) -> bool:
    return fail_over_usd is not None and total_usd(costs) > fail_over_usd


def _fmt_scanned(cost: QueryCost) -> str:
    if cost.skipped == "jinja":
        return f"— ({JINJA_NOTE})"
    if cost.error:
        return f"error: {cost.error}"
    return f"{cost.bytes_processed / _TIB:.2f} TiB"


def _fmt_usd(cost: QueryCost, fail_over_usd: Optional[float]) -> str:
    if cost.skipped or cost.error:
        return "—"
    label = f"${cost.usd:,.2f}"
    if fail_over_usd is not None and cost.usd > fail_over_usd:
        return f"**{label}**"
    return label


def _threshold_line(costs: Sequence[QueryCost], fail_over_usd: Optional[float]) -> str:
    line = f"Total por ejecución: ${total_usd(costs):,.2f}"
    if fail_over_usd is not None:
        state = "excedido" if exceeded(costs, fail_over_usd) else "ok"
        line += f" · umbral: ${fail_over_usd:,.2f} → {state}"
    return line


FOOTNOTE = (f"Precio on-demand ${ON_DEMAND_USD_PER_TIB}/TiB (BigQuery, lista pública). "
            "Dry-run read-only, no ejecuta las queries.")


def render_text(costs: Sequence[QueryCost], fail_over_usd: Optional[float]) -> str:
    lines = ["", "═══ QUERY COST · datanomad-review ═══", ""]
    for cost in costs:
        usd = _fmt_usd(cost, fail_over_usd).strip("*")
        lines.append(f"  {cost.path:<48} {_fmt_scanned(cost):<14} {usd:>10}")
    lines += ["", f"  {_threshold_line(costs, fail_over_usd)}", f"  {FOOTNOTE}", ""]
    return "\n".join(lines)


def render_github(costs: Sequence[QueryCost], fail_over_usd: Optional[float]) -> str:
    lines = ["### query-cost · datanomad-review", "",
             "| Query | Escaneará | Costo estimado/run |", "|---|---:|---:|"]
    for cost in costs:
        lines.append(f"| {cost.path} | {_fmt_scanned(cost)} | {_fmt_usd(cost, fail_over_usd)} |")
    lines += ["", f"{_threshold_line(costs, fail_over_usd)}", f"_{FOOTNOTE}_", ""]
    return "\n".join(lines)


def render_json(costs: Sequence[QueryCost]) -> str:
    return json.dumps([asdict(c) for c in costs], ensure_ascii=False, indent=2)
