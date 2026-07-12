# Catálogo de Anti-Patrones

Los modos de falla más comunes (y caros) en plataformas de datos.
Formato: síntoma → impacto → cómo detectarlo → fix (runbook si existe).

## Costo / FinOps

### AP-C01 · Tabla grande sin particionar
- **Síntoma:** queries que escanean la tabla completa aunque filtren por fecha.
- **Impacto:** en modelos on-demand (BigQuery) el costo escala lineal con bytes escaneados; es el desperdicio #1.
- **Detección:** `scan bigquery` marca tablas > umbral sin partición ni clustering.
- **Fix:** runbook `partition-bigquery-table.md`.

### AP-C02 · SELECT * en producción
- **Síntoma:** pipelines o dashboards que leen todas las columnas de tablas anchas.
- **Impacto:** columnar storage cobra por columna leída; multiplica el costo sin valor.
- **Detección:** análisis de INFORMATION_SCHEMA.JOBS / query logs.
- **Fix:** proyección explícita de columnas + vistas curadas por consumidor.

### AP-C03 · Recursos zombie
- **Síntoma:** clusters, warehouses, discos, snapshots o datasets sin lecturas en 30-90 días.
- **Impacto:** costo recurrente sin ningún valor.
- **Detección:** `scan aws-cost` + métricas de acceso.
- **Fix:** pausar → observar un ciclo → eliminar (safety pattern #4).

### AP-C04 · Sin atribución de costo
- **Síntoma:** una sola cuenta/proyecto para todo; nadie sabe qué equipo gasta qué.
- **Impacto:** el costo sin dueño solo crece; imposibilita FinOps.
- **Detección:** checklist de la dimensión Costo (labels/tags coverage).
- **Fix:** política de etiquetado + showback mensual por equipo.

### AP-C05 · Retención infinita
- **Síntoma:** datos crudos guardados "por si acaso" desde el inicio de los tiempos, en storage caliente.
- **Impacto:** storage crece monotónicamente; el 80% no se ha leído en meses.
- **Detección:** distribución de edad vs. último acceso.
- **Fix:** lifecycle policies por capa (hot → cold → archive → delete).

## Arquitectura

### AP-A01 · Pipeline duplicado
- **Síntoma:** dos o más pipelines calculando "lo mismo" con resultados distintos.
- **Impacto:** doble costo + números que no cuadran = pérdida de confianza.
- **Detección:** inventario FIND + lineage.
- **Fix:** consolidar en un pipeline canónico con dueño y contrato.

### AP-A02 · Data swamp
- **Síntoma:** lake sin zonas (raw/curated), sin catálogo, naming inconsistente.
- **Impacto:** cada consumo requiere arqueología; los proyectos de IA mueren aquí.
- **Detección:** checklist Arquitectura + Gobierno.
- **Fix:** arquitectura por capas (medallion o equivalente) + catálogo.

### AP-A03 · ETL espagueti sin orquestador
- **Síntoma:** crons, scripts y notebooks encadenados a mano.
- **Impacto:** fallas silenciosas, sin retries, sin observabilidad.
- **Detección:** inventario FIND.
- **Fix:** orquestación declarativa (Airflow/Composer/Step Functions) con SLAs.

## Gobierno / Calidad

### AP-G01 · Tablas sin dueño
- **Síntoma:** nadie responde "¿de quién es esta tabla?".
- **Impacto:** nada se puede deprecar, arreglar ni gobernar.
- **Detección:** % de datasets con owner declarado (checklist Gobierno).
- **Fix:** ownership por dominio + data contracts en el onboarding.

### AP-G02 · Modelos sin tests ni docs
- **Síntoma:** proyecto dbt (o equivalente) sin tests de unicidad/not-null ni descripciones.
- **Impacto:** regresiones silenciosas; nadie confía en los números.
- **Detección:** `scan dbt` reporta cobertura de tests y docs por modelo.
- **Fix:** política de PR: ningún modelo entra sin tests mínimos + descripción.

### AP-G03 · PII sin clasificar
- **Síntoma:** datos personales dispersos sin etiquetas ni control de acceso diferenciado.
- **Impacto:** riesgo regulatorio (y bloqueo instantáneo de casos de uso de IA).
- **Detección:** checklist Seguridad (clasificación + column-level access).
- **Fix:** clasificación, enmascaramiento por defecto y acceso por rol.

## AI-Readiness

### AP-AI01 · Entrenar con datos rancios
- **Síntoma:** features/modelos alimentados por tablas sin freshness SLA.
- **Impacto:** modelos que degradan en silencio; GenAI que responde con datos viejos.
- **Detección:** freshness checks + lineage hacia consumidores ML.
- **Fix:** SLAs de freshness + monitoreo en WATCH.

### AP-AI02 · Sin dataset canónico para IA
- **Síntoma:** cada experimento de IA re-extrae y re-limpia desde raw.
- **Impacto:** semanas perdidas por experimento; resultados irreproducibles.
- **Detección:** checklist AI-Readiness.
- **Fix:** capa curada y documentada como fuente única para ML/GenAI.
