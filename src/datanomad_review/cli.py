"""datanomad-review CLI.

Commands:
    scan dbt <path>                   Static dbt project review (no credentials)
    scan bigquery --project <id>      Read-only BigQuery cost/architecture scan
    scan aws-cost [--profile <name>]  Read-only AWS Cost Explorer scan
    assess --interactive              Guided self-assessment -> scorecard
"""
from __future__ import annotations
import argparse
import sys

from .scorecard import Scorecard


def _print_findings(findings) -> None:
    card = Scorecard(findings=list(findings))
    print(card.render())
    sev = [f for f in findings if f.severity in ("critical", "high")]
    if sev:
        label = "hallazgo" if len(sev) == 1 else "hallazgos"
        print(f"⚠  {len(sev)} {label} de severidad alta. "
              f"Prioriza con la matriz impacto×esfuerzo (fase LOCK).")


def cmd_scan(args: argparse.Namespace) -> int:
    if args.target == "dbt":
        from .checks import dbt_project
        _print_findings(dbt_project.scan(args.path or "."))
    elif args.target == "bigquery":
        if not args.project:
            print("Falta --project <gcp-project-id>", file=sys.stderr)
            return 2
        from .checks import bigquery
        _print_findings(bigquery.scan(args.project, region=args.region))
    elif args.target == "aws-cost":
        from .checks import aws_cost
        _print_findings(aws_cost.scan(profile=args.profile))
    else:
        print(f"Target desconocido: {args.target}", file=sys.stderr)
        return 2
    return 0


def cmd_assess(args: argparse.Namespace) -> int:
    definition = Scorecard.load_definition()
    card = Scorecard()
    print("\n═══ Autoevaluación datanomad-review ═══")
    print("Puntúa cada criterio: 0 = no existe · 1 = parcial/ad-hoc · 2 = sistemático\n")
    for key, dim in definition["dimensions"].items():
        print(f"\n── {dim['name']} " + "─" * (40 - len(dim['name'])))
        points, maxp = 0, 0
        for c in dim["criteria"]:
            maxp += 2
            while True:
                raw = input(f"  [{c['id']}] {c['text']} (0/1/2): ").strip()
                if raw in ("0", "1", "2"):
                    points += int(raw)
                    break
                print("    → responde 0, 1 o 2")
        card.scores[key] = round(points / maxp * 100, 1)
    print(card.render(definition))
    print("Siguiente paso: corre los scanners para validar con evidencia (fase FIND).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="datanomad-review",
                                     description="Review data platforms & cloud spend (GCP/AWS). Read-only.")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__import__('datanomad_review').__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="Run a read-only scanner")
    p_scan.add_argument("target", choices=["dbt", "bigquery", "aws-cost"])
    p_scan.add_argument("path", nargs="?", help="Path (for dbt)")
    p_scan.add_argument("--project", help="GCP project id (bigquery)")
    p_scan.add_argument("--region", default="region-us", help="BQ region for INFORMATION_SCHEMA (default region-us)")
    p_scan.add_argument("--profile", help="AWS profile name (aws-cost)")
    p_scan.set_defaults(func=cmd_scan)

    p_assess = sub.add_parser("assess", help="Guided self-assessment -> scorecard")
    p_assess.add_argument("--interactive", action="store_true", default=True)
    p_assess.set_defaults(func=cmd_assess)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
