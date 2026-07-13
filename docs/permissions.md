# Permisos requeridos por scanner

Todos los scanners son **read-only**: no crean, modifican ni borran nada. Estos son los permisos mínimos exactos, derivados de las llamadas que hace cada scanner.

## `scan dbt <path>` — sin credenciales

Análisis estático de archivos locales (`dbt_project.yml`, `models/**`). No toca ninguna nube.

## `scan bigquery --project <id>` — GCP

Qué hace: lista datasets/tablas y lee su metadata (`num_bytes`, particionamiento), y ejecuta **una** consulta sobre `INFORMATION_SCHEMA.JOBS_BY_PROJECT` (últimos 30 días de jobs). No lee datos de tus tablas.

Roles mínimos para la Service Account (a nivel de proyecto):

| Rol | Para qué |
|---|---|
| `roles/bigquery.metadataViewer` | Listar datasets/tablas y leer su metadata (AP-C01, AP-C05) |
| `roles/bigquery.jobUser` | Poder ejecutar la consulta a INFORMATION_SCHEMA (AP-C02) |
| `roles/bigquery.resourceViewer` | Leer `JOBS_BY_PROJECT` (historial de jobs de todo el proyecto) |

Ninguno permite leer el contenido de tablas ni modificar nada. Costo: la consulta a INFORMATION_SCHEMA escanea solo metadata (centavos o gratis).

Setup:

```bash
gcloud iam service-accounts create datanomad-review-ro
for ROLE in bigquery.metadataViewer bigquery.jobUser bigquery.resourceViewer; do
  gcloud projects add-iam-policy-binding MI_PROYECTO \
    --member serviceAccount:datanomad-review-ro@MI_PROYECTO.iam.gserviceaccount.com \
    --role roles/$ROLE
done
gcloud iam service-accounts keys create key.json \
  --iam-account datanomad-review-ro@MI_PROYECTO.iam.gserviceaccount.com
export GOOGLE_APPLICATION_CREDENTIALS=key.json

datanomad-review scan bigquery --project MI_PROYECTO
```

También funciona con tu propia identidad (`gcloud auth application-default login`) si tienes esos permisos.

Nota: `JOBS_BY_PROJECT` se consulta por región (`--region region-us` por defecto; usa `--region region-southamerica-east1`, etc. según dónde corran tus jobs).

## `scan aws-cost [--profile <name>]` — AWS

Qué hace: llama **únicamente** a `ce:GetCostAndUsage` (Cost Explorer) para comparar mes anterior vs proyección del mes actual, gasto sin tag `team`, y top servicios. No toca recursos.

Política IAM mínima para el usuario/rol de la Access Key:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ce:GetCostAndUsage",
      "Resource": "*"
    }
  ]
}
```

Requisitos: Cost Explorer habilitado en la cuenta (Billing → Cost Explorer → Enable; tarda ~24h la primera vez). La API de Cost Explorer cobra USD 0.01 por request (el scan hace 3).

Credenciales: perfil estándar de `~/.aws/credentials` (`--profile mi-perfil`) o variables `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`.

## `assess --interactive` — sin credenciales

Autoevaluación guiada por los checklists; genera el scorecard sin conectarse a nada.

## `billing-diff` y `teardown` — sin credenciales

Trabajan sobre exports CSV locales que tú descargas de la consola ([formatos soportados](billing-formats.md)). No se conectan a ninguna nube; los IDs de cuenta y emails del export se descartan al parsear.

## `query-cost <paths...> --project <id>` — GCP

Qué hace: por cada archivo `.sql` ejecuta un **dry-run** de BigQuery (`dry_run=True`). Un dry-run no ejecuta la query, no lee datos y **no factura**: BigQuery solo responde cuántos bytes escanearía.

Permiso mínimo: `bigquery.jobs.create` sobre el proyecto — incluido en `roles/bigquery.jobUser` (el mismo rol que ya usa `scan bigquery`).

En CI, autentica antes con [google-github-actions/auth](https://github.com/google-github-actions/auth) (Workload Identity); el action de query-cost no maneja credenciales.

## Multi-cloud

Cada scanner se corre por separado y suma hallazgos al mismo marco (los códigos AP-* son transversales):

```bash
datanomad-review scan dbt ./mi-proyecto-dbt
datanomad-review scan bigquery --project mi-gcp
datanomad-review scan aws-cost --profile mi-aws
```

Un scorecard consolidado multi-fuente está en el [roadmap](../README.md#roadmap-del-proyecto).
