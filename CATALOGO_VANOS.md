# Catálogo único de vanos (ventanas y puertas)

**Mantener esta guía y sus pruebas al cambiar perfiles, modelos de puerta o validación.**
Muestras: `house_grammar/steps/step23_fresh_theta/catalogo_ventanas/` (40 casos:
5 perfiles × 4 formas × con/sin reja) y `catalogo_puertas/` (20 casos:
5 estilos × rectángulo/arco × puerta/portón).
Generadores: `generar_ventanas.py`, `generar_puertas.py`.
Detalle de diseño: `house_grammar/DISENO_VENTANAS.md`, `house_grammar/DISENO_PUERTAS.md`.

## Contrato de autoría

- Toda ventana usa exclusivamente `modeling/window_assembly.py`; toda puerta o
  portón usa exclusivamente `modeling/door_assembly.py`. No hay emisores
  alternativos: `prefabs.build_opening` y `apertures.shaped_opening` están
  retirados y fallan si se les llama.
- Punto único de despacho: `modeling/opening_catalog.py` (`resolve_opening` /
  `build_opening`). `grammar.opening` delega ahí; `theta` resuelve cada vano
  contra `architectural_style` antes de emitir geometría.
- `prefab`: escribir `catalog` (valor por defecto) u `open` (ventana sin vidrio
  ni divisiones). `legacy`/`slim_window`/`storefront` se aceptan solo como alias
  de lectura y se normalizan a `catalog`. En puertas, `wood_panel`,
  `metal_gate`, `roller`, `storefront` y `open` también son alias de lectura
  (se completan con `door` automático desde el estilo, preservando intención
  material: tablas/madera, paneles/metal, lamas/metal, vidriada, calada);
  `louver`, `screen` y nombres desconocidos se rechazan.
- Las fachadas en modo repetición componen vanos `catalog` automáticamente;
  las puertas/portones compuestos llevan `door` con `model: auto`, que hereda
  el estilo del edificio (sin estilo global: `moderno`).
- Un `frame_profile` o `door.model` que contradiga `architectural_style`
  produce error; no hay conversión silenciosa.

## Ejemplo: ventana de catálogo

```json
{
  "kind": "window", "u_m": 1.2, "v_m": 0.9,
  "width_m": 1.4, "height_m": 2.0,
  "shape": "arch", "arch_rise_m": 0.6,
  "recess_m": 0.18, "prefab": "catalog",
  "frame_profile": "auto", "frame_width_m": 0.12,
  "frame_depth_m": 0.14, "sill": true,
  "grid_spacing_m": 0.4,
  "grille": true, "grille_pattern": "diamond",
  "grille_spacing_m": 0.14
}
```

`frame_profile`: `republicano`, `barroco`, `clasico`, `madera`, `moderno`
(o `auto`, que hereda el estilo global). El contorno (`rectangle`, `arch`,
`circle`, `ellipse`) determina vano, revelado, vidrio, divisiones y reja;
las curvas son polígonos reales, no texturas. `sill` sigue el contorno inferior.
`grid_spacing_m` activa conteo adaptativo; si es `null` mandan
`mullion_columns`/`mullion_rows`. Semántica emitida: `window_reveal`,
`window_profile`, `window_glass`, `window_mullion`, `window_grille`, `window_sill`.

## Ejemplo: puerta de catálogo

```json
{
  "kind": "gate", "u_m": 2.0, "v_m": 0.1,
  "width_m": 3.2, "height_m": 3.4,
  "shape": "arch", "arch_rise_m": 0.6,
  "frame_width_m": 0.12, "frame_depth_m": 0.14, "recess_m": 0.2,
  "prefab": "catalog",
  "door": {
    "model": "auto", "leaves": 0, "construction": "panelled",
    "portal": "columns", "portal_width_m": 0.28,
    "portal_gap_m": 0.12, "portal_depth_m": 0.24,
    "cornice": true,
    "transom_height_m": 0.55, "transom_infill": "glass",
    "transom_grille": true, "grille_pattern": "scrolls",
    "threshold": true, "opening_angles_deg": [0, 0]
  }
}
```

`model`: los cinco estilos o `auto` (hereda el global). Solo `rectangle`/`arch`.
`leaves: 0` elige una o dos hojas desde 1.35 m de ancho útil. `construction`:
`auto` (paneles en republicano/barroco/clásico, tablas en madera, lamas en
moderno), `panelled`, `glazed`, `grille`, `boards`, `louvers`.
`opening_angles_deg`: un ángulo por hoja, 0–110°, apertura exterior (sin
análisis de colisión: verificar espacio). La sobreluz exige paso ≥ 1.5 m.
Materiales por slots compartidos (`leaf_material`, `frame_material` admiten
`auto`); colores vía `theta.materials`.

## Vocabulario

| Control | Valores |
|---|---|
| `kind` | `window`, `door`, `gate`, `balcony_window` (misma carpintería que `window` + losa y baranda) |
| `prefab` | `catalog` (defecto), `open` (solo ventana); `legacy`/`slim_window`/`storefront` solo alias de lectura |
| `frame_profile` | `republicano`, `barroco`, `clasico`, `madera`, `moderno`, `auto` |
| `shape` (ventana) | `rectangle`, `arch`, `circle` (ancho = alto), `ellipse` |
| `shape` (puerta) | `rectangle`, `arch` |
| `grille_pattern` (ventana) | `vertical`, `grid`, `diamond` |
| `grille_pattern` (puerta) | `auto`, `vertical`, `grid`, `rings`, `scrolls` |
| `door.portal` | `none`, `pilasters`, `columns` (+ `cornice` opcional) |
| `door.transom_infill` | `glass`, `open` |

`Opening.style` no selecciona catálogo (hojas abatidas/cortinas antiguas no se
generan). `balcony_window` se resuelve a `window` en composición y suma losa.

## Relieve y vuelos sobre la calle

Las molduras del catálogo (`window_profile`, `door_moulding`, etc.) vuelan
sobre la vereda hasta la envolvente de calle: pertenecen a
`PROJECTING_SEMANTICS` en `mesh_builder.py`, igual que cornisas y balcones.
En muros sobre lindero lateral/posterior el relieve exterior se recorta (regla
de medianería: no se invade al vecino); el revelado, vidrio y divisiones,
alojados dentro del vano, se emiten siempre. Al añadir semánticas nuevas de
vano que vuelen, registrarlas ahí o desaparecerán en muros a filo de lote.

## Migración y verificación

- Los prefabs antiguos en JSON activos se normalizan a catálogo (`door`
  automático desde el estilo en puertas). Escritura nueva: `catalog` (+ bloque
  `door` explícito en puertas). `louver`, `screen` y nombres desconocidos
  fallan con mensaje que indica el catálogo correspondiente.
- Pruebas: `test_opening_catalog_only.py` (las 60 muestras conservan vértices
  y caras exactas al pasar por el despacho único + rechazo de prefabs
  obsoletos), `test_window_assembly.py`, `test_door_assembly.py`, tests de
  composición/fachada y goldens V4.
- Las muestras originales conservan su autoría (`prefab: legacy`); no se
  promete que solicitudes históricas con prefabs descartados resuelvan con la
  gramática actual.
