# Metodología F.L.O.W.

Cuatro fases para llevar una plataforma de datos del caos al flujo.
Cada fase tiene entradas, actividades, salidas y una regla de oro.

## Fase 1 — FIND (Diagnóstico)

**Objetivo:** mapear el estado real, con evidencia, en las 7 dimensiones.

- Inventario: fuentes, pipelines, warehouses, consumidores, dueños.
- Ejecutar scanners read-only (`datanomad-review scan ...`).
- Completar checklists por dimensión con el equipo (no en solitario:
  el conocimiento tribal es parte del hallazgo).
- Cuantificar: costo/mes por componente, % de tablas sin dueño,
  % de modelos sin tests, top-10 queries por costo.

**Salida:** Scorecard 0–100 por dimensión + lista de hallazgos con evidencia.
**Regla de oro:** *sin evidencia no hay hallazgo.* Cada afirmación se sostiene
con un query, un export de billing o un screenshot.

## Fase 2 — LOCK (Asegurar)

**Objetivo:** cortar la sangría con quick-wins de alto impacto y bajo riesgo.

- Priorizar hallazgos en matriz impacto × esfuerzo.
- Ejecutar solo fixes reversibles y de bajo riesgo (ver safety-patterns.md):
  apagar recursos zombie confirmados, poner límites de query, activar
  alertas de presupuesto, congelar pipelines huérfanos (pausar ≠ borrar).
- Establecer el baseline de costo y calidad ANTES de optimizar
  (si no mides el antes, no puedes probar el después).

**Salida:** ahorro inmediato verificado + baseline documentado.
**Regla de oro:** *pausar antes que borrar; siempre reversible.*

## Fase 3 — OPTIMIZE (Rediseñar)

**Objetivo:** arquitectura eficiente, gobernada y lista para IA.

- Ejecutar los fixes estructurales vía runbooks (particionamiento,
  modelado, data contracts, lineage, capas de calidad).
- Introducir gobierno: dueños por dominio, catálogo, políticas de PII.
- Preparar AI-readiness: datasets documentados, features confiables,
  acceso gobernado para equipos de ML/GenAI.

**Salida:** plataforma rediseñada + deuda técnica priorizada restante.
**Regla de oro:** *cada cambio estructural entra por dev, con runbook,
con rollback definido.*

## Fase 4 — WATCH (Vigilar)

**Objetivo:** que el orden no vuelva a perderse.

- Monitoreo continuo: presupuestos y alertas de costo, tests de calidad
  en CI, freshness SLAs, revisión trimestral del scorecard.
- Gobierno vivo: onboarding de nuevas fuentes vía data contract,
  postmortems de incidentes de datos.

**Salida:** operación gobernada; el scorecard se vuelve un KPI trimestral.
**Regla de oro:** *lo que no se observa, se degrada.*
