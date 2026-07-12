"""Static, credential-free review of a dbt project.

Detects: models without tests (AP-G02), models without descriptions,
sources without freshness config (AP-AI01), SELECT * in models (AP-C02).
"""
from __future__ import annotations
import pathlib
import re

import yaml

from ..scorecard import Finding


def scan(project_dir: str) -> list[Finding]:
    root = pathlib.Path(project_dir)
    findings: list[Finding] = []
    if not (root / "dbt_project.yml").exists():
        findings.append(Finding("DBT-00", f"No se encontró dbt_project.yml en {root}",
                                "high", "architecture",
                                evidence=str(root)))
        return findings

    sql_models = list(root.glob("models/**/*.sql"))
    documented: set[str] = set()
    tested: set[str] = set()
    fresh_sources = 0
    total_sources = 0

    for schema in root.glob("models/**/*.yml"):
        try:
            doc = yaml.safe_load(schema.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        for model in doc.get("models", []) or []:
            name = model.get("name", "")
            if model.get("description"):
                documented.add(name)
            cols = model.get("columns", []) or []
            has_tests = bool(model.get("tests")) or any(c.get("tests") for c in cols)
            if has_tests:
                tested.add(name)
        for src in doc.get("sources", []) or []:
            for table in src.get("tables", []) or []:
                total_sources += 1
                if table.get("freshness") or src.get("freshness"):
                    fresh_sources += 1

    names = {p.stem for p in sql_models}
    untested = sorted(names - tested)
    undocumented = sorted(names - documented)

    if names:
        cov = 100 * (len(names) - len(untested)) / len(names)
        if cov < 60:
            findings.append(Finding(
                "AP-G02", f"Solo {cov:.0f}% de los modelos tiene tests ({len(untested)}/{len(names)} sin tests)",
                "high" if cov < 30 else "medium", "quality",
                evidence="ej: " + ", ".join(untested[:5]),
                fix="Política de PR: ningún modelo sin tests mínimos (unique/not_null)."))
        if len(undocumented) / len(names) > 0.5:
            findings.append(Finding(
                "AP-G02b", f"{len(undocumented)}/{len(names)} modelos sin descripción",
                "medium", "governance",
                evidence="ej: " + ", ".join(undocumented[:5]),
                fix="Documentar modelos críticos primero (los que alimentan dashboards/IA)."))

    if total_sources and fresh_sources / total_sources < 0.5:
        findings.append(Finding(
            "AP-AI01", f"Solo {fresh_sources}/{total_sources} sources con freshness configurado",
            "medium", "ai_readiness",
            fix="Definir freshness SLAs; alimenta la fase WATCH."))

    star = [p for p in sql_models
            if re.search(r"select\s+\*\s+from", p.read_text(encoding="utf-8", errors="ignore"), re.I)
            and "staging" not in str(p)]
    if star:
        findings.append(Finding(
            "AP-C02", f"{len(star)} modelos (fuera de staging) usan SELECT *",
            "medium", "cost",
            evidence="ej: " + ", ".join(p.stem for p in star[:5]),
            fix="Proyección explícita de columnas en capas curated/marts."))
    return findings
