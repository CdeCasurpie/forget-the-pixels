# Remates perimetrales — cornisa y zócalo

## Activación

Bloque opcional `theta.trim`. Ausencia = comportamiento anterior. `enabled: false` desactiva explícitamente ese remate y suprime sus equivalentes automáticos antiguos en esos componentes.

```json
{
  "trim": {
    "cornice": {"enabled": true, "profile": "auto", "height_m": 0.24, "projection_m": 0.18, "anchor": "wall_top", "offset_m": 0.0, "material": "cornice", "scope": "exposed", "courtyards": false},
    "plinth": {"enabled": true, "design": "horizontal_joints", "height_m": 0.60, "relief_m": 0.025, "material": "plinth", "course_height_m": 0.20, "block_width_m": 0.50, "joint_width_m": 0.012, "scope": "exposed", "courtyards": false}
  }
}
```

- `MassComponent.trim` / `RoofBody.trim` reemplaza el bloque completo; `None` hereda global.
- `profile: auto` usa `theta.architectural_style` (republicano, clasico, barroco, madera, moderno).
- `FenceRun.plinth` + `base_height_m` reutilizan el contrato de zócalo para cercos. Desactivar el acabado no elimina el tramo sólido.

## Cornisa: sweep continuo

Sección (profundidad × altura) en `trim_profiles.CORNICES`, recorrida sobre el borde del volumen en `trim_sweep.emit_sweep`:

- Republicano escalonado, clasico sobrio, barroco curvo, madera con tapa, moderno delgado. Todos desactivables con `enabled: false`.
- Anclaje `wall_top` (borde superior del muro) o `parapet_top` (remate del parapeto). Con `parapet_top` se suprime la tapa de parapeto antigua y la losa usa material de fachada para no generar franja gris.
- Esquinas por inglete en un solo recorrido; ángulo muy agudo cae a bisel acotado. Recorridos abiertos llevan tapas. No se unen perfiles o alturas incompatibles.
- La proyección debe caber en la envolvente de calle; si no cabe se rechaza, no se recorta en silencio.

Resolución (`trim_resolver.resolve_trims`):

- Agrupa masas con igual configuración y une huellas en planta considerando alturas: si un cuerpo continúa encima con la misma huella no hay cornisa intermedia; si se retira, corona el borde inferior expuesto; elimina remates en interfaces ocultas y medianeras.
- Exige muros planos con remate horizontal en componentes con trim.
- Rechaza cornisas que invadan vanos.

## Zócalo: acabado inferior con relieve opcional

- `relief_m: 0` + `smooth` = solo acabado (región de material en la base del muro), sin geometría adosada.
- `relief_m > 0`: geometría adosada con recorrido continuo:
  - `smooth`: banda continua.
  - `horizontal_joints`: respaldo + cursos con juntas rehundidas cada `course_height_m`.
  - `stepped`: 2–3 cursos con profundidades decrecientes.
  - `blocks`: respaldo + bloques con juntas verticales alternadas (`block_width_m`). Genera muchas piezas (ver catálogo); usar con moderación.
- Solo en cuerpos con `base_z ≈ 0`. Se interrumpe en puertas/portones y respeta vanos. Las juntas usan distancia acumulada del recorrido.
- "Piedra" es material (`plinth`/otro slot), no un diseño obligatorio.
- Materiales nuevos: slots `cornice` y `plinth`, coloreables vía `theta.materials`.

## Precedencia sobre el sistema antiguo

Con `trim` activo en un componente se suprimen en sus muros: losa/faja superior de concreto, zócalo de piedra, bandas entre pisos, división de caparazón por retranqueo y proyecciones `cornice`/`denticulated_cornice` de familia u orden (se conserva la cornisa del portal monumental de la puerta). Sin `trim` todo sigue igual.

## Generación, catálogo y salmón

Desde `investigation/procedural_reconstruction`:

```
python3 steps/step23_fresh_theta/generar_remates.py
```

- `catalogo_remates/`: 5 cornisas + 4 zócalos + `sin_remates` + `zocalo_al_ras` + `cerco_esquina`, con GLB, request, validación y `resolved_trim.json`. Sin renders.
- `lotes/1134299_casa_salmon_republicana/remates_vinculados/`: cornisa republicana 0.30×0.22 anclada al parapeto, zócalo de juntas 0.60 m, zócalo escalonado en cerco. Se retiran 2 proyecciones de cornisa antiguas (registro en `removed_projections.json`); se conserva la cornisa del portal de la puerta. Piso inferior con anclaje `wall_top` por no tener parapeto expuesto.
- Pruebas: `tests/test_perimeter_trim.py` (cierre/hermeticidad, orientación, coronación al tope, masas apiladas/retiradas, cortes de vanos, on/off, parapeto, cercos, controles inválidos).

## Límites

- Sin capiteles corintios ni talla escultórica; barroco geométrico.
- Sin bandas decorativas entre pisos ni losas vistas decorativas: solo coronación o desactivado.
- Sin análisis de colisión de hojas de puerta con la portada; sin slots de color por puerta individual.
- Bloques generan una pieza por bloque; vigilar presupuesto en lotes grandes.
