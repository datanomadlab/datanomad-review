"""Demo autocontenida: escanea el proyecto dbt de ejemplo empaquetado.

No requiere credenciales ni red. El ejemplo trae anti-patrones sembrados
a propósito (modelos sin tests, SELECT * en marts, sources sin freshness)
para mostrar el formato de hallazgos del scanner.
"""
from __future__ import annotations

import shutil
import tempfile
from importlib import resources
from pathlib import Path

from .checks import dbt_project
from .scorecard import Finding

EXAMPLE_PKG_PATH = "examples/sample-dbt-project"


def _materialize_example(dst: Path) -> Path:
    """Copia el proyecto de ejemplo empaquetado a un directorio real (zip-safe)."""
    root = resources.files("datanomad_review").joinpath(EXAMPLE_PKG_PATH)
    with resources.as_file(root) as src:
        target = dst / "sample-dbt-project"
        shutil.copytree(src, target)
    return target


def run_demo(printer) -> list[Finding]:
    """Ejecuta el demo y devuelve los hallazgos. `printer` recibe los findings."""
    print("═══ datanomad-review · DEMO ═══")
    print("Escaneando un proyecto dbt de ejemplo (incluido en el paquete) con")
    print("anti-patrones sembrados a propósito. 100% local, sin credenciales.\n")
    with tempfile.TemporaryDirectory() as tmp:
        project = _materialize_example(Path(tmp))
        print(f"$ datanomad-review scan dbt {project.name}")
        findings = dbt_project.scan(str(project))
        printer(findings)
    print("Siguiente paso — apúntalo a tu propio proyecto:")
    print("  datanomad-review scan dbt ./mi-proyecto-dbt")
    print("  datanomad-review scan bigquery --project mi-gcp   (read-only)")
    print("Más en https://www.datanomadlab.com")
    return findings
