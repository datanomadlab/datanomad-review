"""datanomad-review CLI.

Commands:
    demo                              Self-contained demo (no credentials, no network)
    scan dbt <path>                   Static dbt project review (no credentials)
    scan bigquery --project <id>      Read-only BigQuery cost/architecture scan
    scan aws-cost [--profile <name>]  Read-only AWS Cost Explorer scan
    assess --interactive              Guided self-assessment -> scorecard
    billing-diff <before> <after>     Explain why the cloud bill changed (CSV exports)
    teardown <before> [<after>]       Anonymized billing teardown in markdown
    query-cost <paths...>             BigQuery dry-run cost estimate for .sql files
"""
from __future__ import annotations
import argparse
import sys

from . import plugins
from .scorecard import Scorecard


def _print_findings(findings) -> None:
    findings = plugins.apply_quantifiers(list(findings))
    card = Scorecard(findings=findings)
    print(card.render())
    sev = [f for f in findings if f.severity in ("critical", "high")]
    if sev:
        label = "hallazgo" if len(sev) == 1 else "hallazgos"
        print(f"⚠  {len(sev)} {label} de severidad alta. "
              f"Prioriza con la matriz impacto×esfuerzo (fase LOCK).")
    hint = plugins.pro_hint()
    if hint:
        print(hint)


def _unknown_format(fmt: str, free_formats: tuple) -> int:
    available = ", ".join(list(free_formats) + sorted(plugins.load_registry().renderers))
    print(f"Formato '{fmt}' no disponible en la edición open source. "
          f"Formatos: {available}.", file=sys.stderr)
    print(plugins.PRO_HINT, file=sys.stderr)
    return 2


def cmd_billing_diff(args: argparse.Namespace) -> int:
    from .billing import BillingFormatError, diff_snapshots, load_billing_csv, narrative
    try:
        before = load_billing_csv(args.before)
        after = load_billing_csv(args.after)
    except (OSError, BillingFormatError) as exc:
        print(exc, file=sys.stderr)
        return 2
    diff = diff_snapshots(before, after)
    renderers = plugins.load_registry().renderers
    if args.format == "text":
        print(narrative.render_text(diff, top=args.top))
        hint = plugins.pro_hint()
        if hint:
            print(hint)
    elif args.format == "json":
        print(narrative.render_json(diff))
    elif args.format == "md":
        print(narrative.render_markdown(diff, top=args.top))
    elif args.format in renderers:
        print(renderers[args.format](narrative.findings_from_diff(diff), {"diff": diff}))
    else:
        return _unknown_format(args.format, ("text", "json", "md"))
    return 0


def cmd_teardown(args: argparse.Namespace) -> int:
    from . import teardown
    from .billing import BillingFormatError, diff_snapshots, load_billing_csv
    try:
        first = load_billing_csv(args.before)
        second = load_billing_csv(args.after) if args.after else None
    except (OSError, BillingFormatError) as exc:
        print(exc, file=sys.stderr)
        return 2

    opts = teardown.TeardownOptions(alias=args.alias, sector=args.sector,
                                    template=args.template)
    templates = plugins.load_registry().teardown_templates
    template_name = opts.template
    if template_name == "default" and len(templates) == 1:
        template_name = next(iter(templates))  # con una sola plantilla instalada, úsala

    if second is not None:
        diff = diff_snapshots(first, second)
        if template_name in templates:
            output = templates[template_name](diff=diff, options=opts)
        elif template_name != "default":
            print(f"Plantilla '{template_name}' no disponible. "
                  f"Plantillas: default{''.join(', ' + t for t in sorted(templates))}.",
                  file=sys.stderr)
            return 2
        else:
            output = teardown.generate_teardown(diff, opts)
    else:
        output = teardown.generate_breakdown(first, opts)

    if args.output:
        import pathlib
        pathlib.Path(args.output).write_text(output, encoding="utf-8")
        print(f"Teardown escrito en {args.output}")
    else:
        print(output)
    return 0


def cmd_query_cost(args: argparse.Namespace) -> int:
    from . import costguard
    try:
        costs = costguard.scan(args.paths, project=args.project,
                               price_per_tib=args.price_per_tib)
    except costguard.MissingDependencyError as exc:
        print(exc, file=sys.stderr)
        return 2
    if not costs:
        print("No encontré archivos .sql en las rutas dadas.", file=sys.stderr)
        return 2
    if args.format == "text":
        print(costguard.render_text(costs, args.fail_over_usd))
    elif args.format == "github":
        print(costguard.render_github(costs, args.fail_over_usd))
    elif args.format == "json":
        print(costguard.render_json(costs))
    else:
        return _unknown_format(args.format, ("text", "github", "json"))
    return 1 if costguard.exceeded(costs, args.fail_over_usd) else 0


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


def cmd_demo(args: argparse.Namespace) -> int:
    from .demo import run_demo
    run_demo(_print_findings)
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

    p_demo = sub.add_parser("demo", help="Self-contained demo on a bundled sample project")
    p_demo.set_defaults(func=cmd_demo)

    p_assess = sub.add_parser("assess", help="Guided self-assessment -> scorecard")
    p_assess.add_argument("--interactive", action="store_true", default=True)
    p_assess.set_defaults(func=cmd_assess)

    p_bdiff = sub.add_parser(
        "billing-diff",
        help="Explica por qué cambió tu cuenta entre dos exports de facturación (CSV)")
    p_bdiff.add_argument("before", help="Export CSV del periodo anterior")
    p_bdiff.add_argument("after", help="Export CSV del periodo actual")
    p_bdiff.add_argument("--top", type=int, default=3,
                         help="Cuántos drivers mostrar (default 3)")
    p_bdiff.add_argument("--format", default="text",
                         help="text | json | md (más formatos vía plugins)")
    p_bdiff.set_defaults(func=cmd_billing_diff)

    p_teardown = sub.add_parser(
        "teardown",
        help="Genera un teardown anonimizado (markdown) desde exports de facturación")
    p_teardown.add_argument("before", help="Export CSV del periodo (o del periodo anterior)")
    p_teardown.add_argument("after", nargs="?",
                            help="Export CSV del periodo actual (modo diff, recomendado)")
    p_teardown.add_argument("--alias", default="una empresa mediana de LATAM",
                            help="Cómo referirse a la empresa en el teardown")
    p_teardown.add_argument("--sector", default="", help="Sector para dar contexto (ej. retail)")
    p_teardown.add_argument("--template", default="default",
                            help="Plantilla a usar (más plantillas vía plugins)")
    p_teardown.add_argument("-o", "--output", help="Archivo de salida (default: stdout)")
    p_teardown.set_defaults(func=cmd_teardown)

    p_qcost = sub.add_parser(
        "query-cost",
        help="Estima el costo de queries BigQuery vía dry-run (no las ejecuta)")
    p_qcost.add_argument("paths", nargs="+", help="Archivos .sql o directorios")
    p_qcost.add_argument("--project", required=True, help="GCP project id para el dry-run")
    p_qcost.add_argument("--fail-over-usd", type=float, default=None,
                         help="Exit code 1 si el total estimado supera este monto (gating de CI)")
    p_qcost.add_argument("--price-per-tib", type=float, default=6.25,
                         help="Precio USD/TiB a usar (default: lista pública on-demand)")
    p_qcost.add_argument("--format", default="text", help="text | github | json")
    p_qcost.set_defaults(func=cmd_query_cost)

    for hook in plugins.load_registry().subcommands:
        hook(sub)

    args = parser.parse_args(argv)
    return args.func(args)


def billing_diff_entry() -> int:
    """Entry point standalone: datanomad-billing-diff ≡ datanomad-review billing-diff."""
    return main(["billing-diff", *sys.argv[1:]])


def query_cost_entry() -> int:
    """Entry point standalone: datanomad-query-cost ≡ datanomad-review query-cost."""
    return main(["query-cost", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
