# Safety Patterns

Reglas no negociables para revisar y modificar plataformas de datos.
Diseñadas para que un tercero (consultor o herramienta) pueda operar
en un entorno ajeno sin generar riesgo.

## 1. Read-only por defecto
Todo scanner de este repo opera exclusivamente con permisos de lectura
(Viewer / ReadOnlyAccess / roles de metadata). Ningún comando de `scan`
crea, modifica ni borra recursos. Si un chequeo requiere permisos de
escritura, no pertenece a `scan`.

## 2. Credenciales del dueño, nunca compartidas
Las herramientas usan las credenciales locales del usuario
(gcloud auth / AWS profile). Nunca se piden, almacenan ni transmiten
credenciales. Nada sale de tu máquina.

## 3. Evidencia antes de recomendación
Cada hallazgo referencia su evidencia (query, export, métrica).
Sin evidencia → es hipótesis, no hallazgo.

## 4. Pausar antes que borrar
En remediación: los recursos "zombie" se pausan/desactivan y se observan
un ciclo completo (mínimo 2 semanas o un cierre de mes) antes de
eliminarse. El costo de pausar es cero; el de borrar mal, no.

## 5. Dev primero, runbook siempre
Ningún cambio estructural va directo a producción. Todo fix entra por
un entorno inferior, sigue un runbook con pasos verificables y tiene
rollback definido ANTES de ejecutarse.

## 6. Cambios de a uno
Un cambio estructural a la vez por sistema afectado. Si el costo o la
calidad se mueven, tienes que poder atribuir el efecto.

## 7. Baseline o no ocurrió
Antes de optimizar, congela el baseline (costo/mes, tiempos, tasas de
error). El valor entregado se demuestra contra ese baseline.

## 8. Datos sensibles fuera del reporte
Los reportes y scorecards contienen metadatos y agregados, nunca filas
de datos reales ni PII. Los ejemplos en issues/PRs van anonimizados.
