# Formatos de billing soportados

`billing-diff` y `teardown` trabajan sobre exports CSV de facturación. El formato se detecta automáticamente por las columnas del header (case-insensitive, tolera BOM). Solo se usan tres campos: **servicio**, **costo** y **proyecto/cuenta** — cualquier otra columna (IDs de línea, emails, SKUs) se descarta al parsear y nunca llega a un reporte.

## `gcp-cost-table` — Cost table de la consola GCP

Descarga: consola de GCP → **Billing → Reports → Cost table → Download CSV** (agrupado por servicio y proyecto, un periodo por archivo).

| Campo | Columna |
|---|---|
| Detección | header contiene `Service description` |
| Servicio | `Service description` |
| Costo | `Subtotal ($)` si existe (incluye descuentos); si no, la primera columna que empiece con `Cost` |
| Proyecto | `Project name` (fallback: `Project ID`) |

## `aws-cur` — Cost and Usage Report

Descarga: export CUR estándar (CSV). Al ser line items, las filas del mismo servicio se agregan automáticamente.

| Campo | Columna |
|---|---|
| Detección | header contiene `lineItem/UnblendedCost` |
| Servicio | `lineItem/ProductCode` |
| Costo | `lineItem/UnblendedCost` |
| Cuenta | `lineItem/UsageAccountId` |

## `aws-ce` — CSV de Cost Explorer

Descarga: consola AWS → **Cost Explorer → agrupar por Service → Download CSV**.

| Campo | Columna |
|---|---|
| Detección | primera columna es `Service` |
| Servicio | `Service` |
| Costo | la última columna con valor numérico de cada fila |

## `generic` — escape hatch

Si tu fuente no calza con ninguno de los anteriores (FinOps tooling propio, otra nube, un spreadsheet), expórtala con exactamente estas columnas:

```csv
service,cost,project
BigQuery,4120.00,analytics-prod
Cloud Storage,2100.00,analytics-prod
```

La columna `project` es opcional (`service,cost` también es válido).

## Reglas de robustez

- Filas de totales (`Total`, `Total costs ($)`) se ignoran.
- Montos con símbolo `$` o coma de miles (`"4,350.00"`) se normalizan.
- Filas con costo no numérico se saltan sin abortar.
- Si el header no calza con ningún formato, el error lista los formatos soportados.

## Uso

```bash
# ¿Por qué subió la cuenta este mes?
datanomad-review billing-diff enero.csv febrero.csv

# Lo mismo, instalado como comando standalone
datanomad-billing-diff enero.csv febrero.csv

# Teardown anonimizado listo para publicar
datanomad-review teardown enero.csv febrero.csv --sector retail -o teardown.md
```
