"""Scorecard engine: loads dimension rubrics and computes weighted scores."""
from __future__ import annotations
import pathlib
from dataclasses import dataclass, field
from importlib import resources

import yaml


@dataclass
class Finding:
    """A single issue detected by a scanner or assessment."""
    code: str          # e.g. AP-C01
    title: str
    severity: str      # critical | high | medium | low
    dimension: str     # cost | architecture | governance | quality | ...
    evidence: str = ""
    fix: str = ""      # runbook or short remediation

    def render(self) -> str:
        icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}.get(self.severity, "⚪")
        out = f"{icon} [{self.code}] {self.title}"
        if self.evidence:
            out += f"\n     evidencia: {self.evidence}"
        if self.fix:
            out += f"\n     fix: {self.fix}"
        return out


@dataclass
class Scorecard:
    scores: dict[str, float] = field(default_factory=dict)   # dimension -> 0..100
    findings: list[Finding] = field(default_factory=list)

    @staticmethod
    def load_definition(path: pathlib.Path | None = None) -> dict:
        if path is not None:
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        ref = resources.files("datanomad_review").joinpath("framework/scorecard.yaml")
        return yaml.safe_load(ref.read_text(encoding="utf-8"))

    def overall(self, definition: dict | None = None) -> float:
        definition = definition or self.load_definition()
        dims = definition["dimensions"]
        total, wsum = 0.0, 0.0
        for key, dim in dims.items():
            if key in self.scores:
                total += self.scores[key] * dim.get("weight", 0)
                wsum += dim.get("weight", 0)
        return round(total / wsum, 1) if wsum else 0.0

    def render(self, definition: dict | None = None) -> str:
        definition = definition or self.load_definition()
        dims = definition["dimensions"]
        lines = ["", "═══ DATANOMAD REVIEW · SCORECARD ═══", ""]
        for key, dim in dims.items():
            score = self.scores.get(key)
            if score is None:
                continue
            bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
            lines.append(f"  {dim['name']:<16} {bar} {score:5.1f}/100")
        if self.scores:
            lines += ["", f"  {'GLOBAL':<16} {self.overall(definition):5.1f}/100"]
        if self.findings:
            lines += ["", f"─── Hallazgos ({len(self.findings)}) ───", ""]
            order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            for f in sorted(self.findings, key=lambda x: order.get(x.severity, 9)):
                lines.append("  " + f.render().replace("\n", "\n  "))
        lines.append("")
        return "\n".join(lines)
