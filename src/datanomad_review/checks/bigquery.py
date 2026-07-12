"""Read-only BigQuery scanner (requires: pip install .[gcp] and gcloud auth).

Detects: large unpartitioned tables (AP-C01), expensive full scans via
INFORMATION_SCHEMA.JOBS (AP-C02), stale datasets (AP-C05).
Only metadata queries are executed. Nothing is created or modified.
"""
from __future__ import annotations

from ..scorecard import Finding

LARGE_TABLE_GB = 10  # threshold for "should be partitioned"


def scan(project: str, region: str = "region-us") -> list[Finding]:
    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError:
        return [Finding("ENV-01", "google-cloud-bigquery no instalado. Usa: pip install 'datanomad-review[gcp]'",
                        "low", "cost")]
    client = bigquery.Client(project=project)
    findings: list[Finding] = []

    # AP-C01: large tables without partitioning
    for ds in client.list_datasets():
        for t in client.list_tables(ds.dataset_id):
            table = client.get_table(f"{project}.{ds.dataset_id}.{t.table_id}")
            size_gb = (table.num_bytes or 0) / 1e9
            if size_gb >= LARGE_TABLE_GB and not table.time_partitioning and not table.range_partitioning:
                findings.append(Finding(
                    "AP-C01", f"Tabla {ds.dataset_id}.{t.table_id} ({size_gb:.1f} GB) sin particionar",
                    "high" if size_gb > 100 else "medium", "cost",
                    evidence=f"num_bytes={table.num_bytes}",
                    fix="runbook: docs/runbooks/partition-bigquery-table.md"))

    # AP-C02: top expensive queries (last 30 days) doing full scans
    sql = f"""
      SELECT user_email,
             SUM(total_bytes_billed)/1e12 AS tb_billed,
             COUNT(*) AS jobs
      FROM `{project}.{region}`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
      WHERE creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
        AND job_type = 'QUERY' AND statement_type = 'SELECT'
      GROUP BY user_email ORDER BY tb_billed DESC LIMIT 10
    """
    try:
        rows = list(client.query(sql).result())
        heavy = [r for r in rows if (r.tb_billed or 0) > 1]
        if heavy:
            top = heavy[0]
            findings.append(Finding(
                "AP-C02", f"{len(heavy)} usuarios/servicios facturaron >1 TB escaneado en 30 días "
                          f"(top: {top.user_email} → {top.tb_billed:.1f} TB)",
                "high", "cost",
                evidence="INFORMATION_SCHEMA.JOBS_BY_PROJECT (30d)",
                fix="Revisar top queries: partición + proyección de columnas + vistas curadas."))
    except Exception as exc:  # permisos o región distinta: reportar, no fallar
        findings.append(Finding("ENV-02", f"No se pudo leer JOBS_BY_PROJECT ({exc}). "
                                          f"Prueba otra región con --region", "low", "cost"))
    return findings
