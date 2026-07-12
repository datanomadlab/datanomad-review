# Runbook: Particionar una tabla grande de BigQuery sin downtime

| Campo | Valor |
|---|---|
| Anti-patrón que corrige | AP-C01 |
| Riesgo | Bajo (crea tabla nueva; la original no se toca) |
| Downtime esperado | Ninguno (swap por nombre al final) |
| Reversible | Sí — la tabla original permanece hasta validar |
| Entorno de prueba | dataset dev primero |

## Precondiciones
- [ ] Baseline: bytes escaneados/mes por queries a la tabla (INFORMATION_SCHEMA.JOBS)
- [ ] Columna de partición identificada (fecha de evento, no de carga, salvo ingestion-time)
- [ ] Consumidores de la tabla mapeados (lineage)

## Pasos
1. Crear la tabla nueva particionada (y clusterizada si hay filtros frecuentes):
   ```sql
   CREATE TABLE `proj.dataset.tabla_v2`
   PARTITION BY DATE(event_ts)
   CLUSTER BY customer_id
   AS SELECT * FROM `proj.dataset.tabla`;
   ```
2. Validar paridad: counts totales y por día entre `tabla` y `tabla_v2`.
3. Redirigir escrituras del pipeline a `tabla_v2` (un solo cambio, ver safety #6).
4. Observar 1–2 ciclos de carga: freshness y counts OK.
5. Swap: renombrar `tabla` → `tabla_legacy`, `tabla_v2` → `tabla`
   (o actualizar la vista canónica que consumen los dashboards).
6. Mantener `tabla_legacy` congelada durante un ciclo de facturación.

## Verificación
- [ ] Bytes escaneados por las top queries caen (esperado: 60–95% en queries con filtro de fecha)
- [ ] Ningún consumidor roto (lineage + logs de errores)

## Rollback
1. Revertir escrituras a `tabla_legacy` y renombrar de vuelta. La data original nunca se modificó.
