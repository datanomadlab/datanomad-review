"""Read-only AWS cost scanner via Cost Explorer (requires: pip install .[aws]).

Detects: month-over-month cost spikes, untagged spend (AP-C04),
and top services driving the bill. Uses only ce:GetCostAndUsage.
"""
from __future__ import annotations
import datetime as dt

from ..scorecard import Finding


def scan(profile: str | None = None) -> list[Finding]:
    try:
        import boto3  # type: ignore
    except ImportError:
        return [Finding("ENV-01", "boto3 no instalado. Usa: pip install 'datanomad-review[aws]'",
                        "low", "cost")]
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    ce = session.client("ce")
    findings: list[Finding] = []

    today = dt.date.today()
    start_prev = (today.replace(day=1) - dt.timedelta(days=1)).replace(day=1)
    start_curr = today.replace(day=1)

    def month_cost(start: dt.date, end: dt.date, group_tags: bool = False):
        kwargs = dict(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="MONTHLY", Metrics=["UnblendedCost"],
        )
        if group_tags:
            kwargs["GroupBy"] = [{"Type": "TAG", "Key": "team"}]
        else:
            kwargs["GroupBy"] = [{"Type": "DIMENSION", "Key": "SERVICE"}]
        return ce.get_cost_and_usage(**kwargs)["ResultsByTime"]

    prev = month_cost(start_prev, start_curr)
    curr = month_cost(start_curr, today if today > start_curr else start_curr + dt.timedelta(days=1))

    def total(results):
        return sum(float(g["Metrics"]["UnblendedCost"]["Amount"])
                   for r in results for g in r.get("Groups", []))

    prev_total, curr_total = total(prev), total(curr)
    if prev_total > 0:
        # projected current month vs previous
        elapsed = max((today - start_curr).days, 1)
        days_in_month = 30
        projected = curr_total / elapsed * days_in_month
        growth = (projected - prev_total) / prev_total * 100
        if growth > 20:
            findings.append(Finding(
                "COS-SPIKE", f"Costo proyectado del mes crece {growth:.0f}% vs mes anterior "
                             f"(${prev_total:,.0f} → ~${projected:,.0f})",
                "high", "cost", evidence="Cost Explorer, UnblendedCost",
                fix="Identificar servicio driver y correr diagnóstico FIND."))

    # AP-C04: spend without team tag
    tagged = month_cost(start_prev, start_curr, group_tags=True)
    untagged = sum(float(g["Metrics"]["UnblendedCost"]["Amount"])
                   for r in tagged for g in r.get("Groups", [])
                   if g["Keys"][0] in ("team$", "team$__missing__", ""))
    if prev_total > 0 and untagged / prev_total > 0.4:
        findings.append(Finding(
            "AP-C04", f"{untagged/prev_total*100:.0f}% del gasto del mes anterior no tiene tag 'team'",
            "medium", "cost",
            fix="Política de etiquetado + showback mensual por equipo."))

    # top services (informative finding)
    groups = [(g["Keys"][0], float(g["Metrics"]["UnblendedCost"]["Amount"]))
              for r in prev for g in r.get("Groups", [])]
    for svc, amount in sorted(groups, key=lambda x: -x[1])[:3]:
        findings.append(Finding("COS-TOP", f"Top servicio mes anterior: {svc} → ${amount:,.0f}",
                                "low", "cost"))
    return findings
