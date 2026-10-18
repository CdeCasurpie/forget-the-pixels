# R0 — Inventario de capacidades y referencia visual fiable

**Estado:** completada. El inventario es de solo lectura; el único cambio en el
`src` es el renderizador de previsualizaciones (`src/modeling/software_render.py`)
conectado a `planning/envelope_export.py`. No se modificó ningún constructor de
catálogo ni el contrato de `steps/`.

**Objetivo de la fase:** registrar qué puede hacer cada uno de los nueve
catálogos, con qué controles, sobre qué anclaje y con qué pruebas, y sustituir
las previsualizaciones poco fiables por un render con profundidad real que
permita juzgar la integración de R1–R6.

---

## 1. Cómo ejecutar

```bash
# Regresiones del renderizador (nuevas, rápidas)
PYTHONPATH=house_grammar/src python3 -m pytest house_grammar/tests/test_software_render.py -q

# Banco de referencia R0: 19 casos mínimos, uno por familia de catálogo
PYTHONPATH=house_grammar/src python3 house_grammar/experiments/r0/run.py \
  --output apps/experimento_paralelizacion/gramatica_adaptable/r0 --sheet
```

`run.py` escribe por caso `preview.png` (perspectiva) y `front.png` (elevación
ortográfica real), más `manifest.json` con la semántica emitida, y compara cada
caso con la semántica esperada del catálogo. El directorio de salida **no debe
existir**.

---

## 2. Matriz de conservación de los nueve catálogos

Regla rectora: **el catálogo se conserva y se reutiliza; solo cambia quién lo
coloca.** La planificación (R1–R3) decide superficies, ejes y medidas; estos
constructores materializan la pieza. En R0 ninguno se reescribe.

| Catálogo | Contrato (`src/domain`) | Resolutor | Constructor | Anclaje que necesita | Muestras (`steps/step23_fresh_theta/`) |
|---|---|---|---|---|---|
| Ventanas | `models.Opening` (+`frame_profile`, `shape`) | `modeling/opening_catalog.resolve_opening` | `window_assembly.build_window` | arista de muro (`origin,tangent,normal`) + rectángulo del vano | `catalogo_ventanas/` — 40 |
| Puertas | `models.DoorControls` + `Opening` | `opening_catalog.resolve_opening` | `door_assembly.build_door` | igual que ventana; `door` aporta portal, sobreluz, hojas, reja | `catalogo_puertas/` — 20 |
| Entradas | `domain/entrances.EntranceControls` | `modeling/entrances.resolve_entrances` | `entrances.build_entrance` | arista de masa + `opening_index` (puerta existente) | `catalogo_entradas/` — 10 |
| Balcones | `domain/balconies.BalconyControls`,`RailingControls` | `modeling/balcony_resolver.resolve_balconies` | `balcony_assembly.build_balcony` (+`railing_assembly`) | arista de masa + `floor_m` + `u_m/width_m` | `catalogo_balcones/` — 103 |
| Pilastras | `domain/vertical_members.VerticalMemberControls`,`MemberDesign` | `vertical_member_resolver.resolve_members` | `vertical_member_assembly.build_member` | arista de masa + `u_m` + `bottom_m/height_m` + sección | `catalogo_pilastras/` — 35 |
| Frontones | `domain/crowns.CrownControls`,`CrownDesign` | `crown_resolver.resolve_crowns` | `crown_assembly.build_crown` | arista de masa + `u_m/width_m/height_m` + `anchor` | `catalogo_frontones/` — 16 |
| Remates | `models.CorniceControls`/`PlinthControls` (`theta`), `trim_resolver.ResolvedTrim` | `trim_resolver.resolve_trims`, `entablature_resolver.resolve_entablatures` | `trim_sweep.emit_sweep`/`emit_trims` | recorrido perimetral de la masa + sección + cortes en vanos | `catalogo_remates/` — 12 |
| Cercos | `domain/fence_catalog.FENCE_STYLES` + controles `site.runs` | validación en `modeling/theta.resolve_theta`; `boundaries.BoundarySpec` | `fences.build_fence` | tramo de lindero (`edge,start_m,end_m`) + puertas | `catalogo_cercos/` — 10 |
| Techos | `domain/roof_details.RoofDesign`,`EaveDesign`,`RoofAssemblyControls` | `roof_detail_resolver.resolve_roof_assemblies` | `roof_assembly.build_roof_assembly` | huella/región de masa + `RoofDesign` | `catalogo_techos/` — 20 |

Sistema transversal (no es un catálogo de piezas): **materiales** —
`modeling/materials.py` (PBR base) y `modeling/wall_finish.py` (partición por
regiones); regla de autoría en `MATERIALES_MUROS.md`. Los colores por pieza
viajan por `theta.materials` y se aplican por cara.

Notas de anclaje que importan para R1–R3:

- Ventanas y puertas comparten **un solo despacho** (`opening_catalog`); su
  profundidad/carpintería es del catálogo, no de la gramática.
- Balcones, pilastras y frontones se anclan a **una arista de masa** con `u_m`
  medido desde el vértice inicial y una profundidad propia (vuelo).
- Los remates son un **barrido de sección** sobre el perímetro, no una caja; por
  eso heredan recortes de vanos y esquinas.
- El cerco es un tramo de lindero independiente del uso del edificio.
- El techo sustituye la losa plana de su masa; no se apila.

---

## 3. Pruebas de capacidad vs pruebas con JSON histórico

La separación que pedía R0, verificada con `grep`:

**Pruebas de capacidad** (construyen la pieza desde cero; no dependen de ningún
archivo de `steps/`):

| Catálogo | Archivo de pruebas |
|---|---|
| Ventanas | `tests/test_window_assembly.py` |
| Puertas | `tests/test_door_assembly.py` |
| Entradas | `tests/test_entrances.py` |
| Balcones | `tests/test_balcony_assembly.py` |
| Pilastras | `tests/test_vertical_members.py` |
| Frontones | `tests/test_volumetric_crowns.py`, `tests/test_crown_profiles.py` |
| Remates | `tests/test_perimeter_trim.py` |
| Cercos | `tests/test_fence_styles.py` |
| Techos | `tests/test_roof_assemblies.py`, `tests/test_roofscape.py`, `tests/test_top_composition.py` |
| Materiales | `tests/test_material_boundaries.py`, `tests/test_wall_finish_theta.py`, `tests/test_facade_depth.py` |

**Pruebas que dependen de JSON histórico** (leen solicitudes de `steps/`):

- `tests/test_opening_catalog_only.py` — las 60 muestras de vanos conservan
  vértices y caras exactas al pasar por el despacho único.
- `tests/test_roof_catalog_only.py` — las muestras de techos.
- `tests/test_step22_after.py` — solicitudes del paso 22 (preexistente, ya
  fallaba antes de esta fase).

Estas tres no certifican la capacidad del catálogo para el sistema nuevo: fijan
compatibilidad con muestras antiguas. **No deben usarse para aprobar R1–R6.**

Los **casos mínimos nuevos** (§6) aportan la referencia de capacidad que faltaba
fuera de `steps/`.

---

## 4. El defecto de render y su corrección

Las previsualizaciones anteriores usaban `matplotlib` 3D
(`Poly3DCollection`). Tenían dos defectos:

1. **Orden de dibujo.** Se ordenan triángulos completos por una única clave de
   profundidad; muros grandes vistos de canto y paneles finos detrás aparecían
   como vetas diagonales y fragmentos flotantes. Una malla cerrada podía verse
   rota.
2. **Cámara vs culling.** La elevación proyectaba con `set_proj_type('ortho')`
   pero **solo llamaba a `view_init` en perspectiva**; el culling usaba
   `face_normals @ direction` con una dirección de fachada. La cámara y el
   culling no coincidían: desaparecían muros enteros y se dibujaban piezas
   interiores en la fachada.

**Corrección:** `src/modeling/software_render.py` rasteriza triángulos en un
**z-buffer real**. El píxel más cercano gana sin importar el orden de entrega, y
la proyección se construye con la **misma base de cámara** que el sombreado, así
que `direction` + `ortho=True` da una elevación ortográfica verdadera. Sin GPU:
`numpy` rasteriza y `PIL` escribe el PNG. `planning/envelope_export._render`
ahora delega aquí y conserva su firma, de modo que `site_export` (Fase 5) sigue
funcionando sin cambios.

Qué demuestra y qué no:

- Demuestra orden correcto, oclusión y encuadre ortográfico fiel (pruebas en
  `tests/test_software_render.py`).
- **No** demuestra todavía que la *composición* sea arquitectónicamente buena:
  mide, no juzga. La evaluación estética es R6.

---

## 5. Resultado visual de R0

`contact_sheet.png` del banco R0 muestra, en un solo lienzo, los nueve catálogos
materializados sobre masas nuevas: los cinco perfiles de ventana, el portal de
columnas, escalera y rampa, barandas de hierro y vidrio, pilastra, frontón,
cornisa/zócalo, cerco de barrotes y de lamas, y cubiertas de teja a dos aguas y
de calamina a un agua. Todas las elevaciones frontales son limpias, con vanos
perforados y derrames reales; ninguna pieza flota ni atraviesa el volumen.

---

## 6. Casos mínimos nuevos (fuera de `steps/`)

Autoría en `experiments/r0/cases.py`; ejecución y salida en `experiments/r0/run.py`.
Son 19 casos deliberadamente desnudos (una masa, un techo plano, sin ornamento
salvo el catálogo probado):

`ventanas_*` (5 perfiles) · `puertas_republicano_portal`, `puertas_moderno_plain`
· `entradas_steps`, `entradas_ramp` · `balcones_republicano`, `balcones_moderno`
· `pilastras_republicano`, `pilastras_moderno` · `frontones_republicano`
· `remates_republicano` · `cercos_republicano`, `cercos_moderno`
· `techos_gable_tile`, `techos_shed_corrugated`.

Cada caso declara qué semántica debe aparecer (`cases.EXPECTED`), así que un
catálogo que deje de emitir su pieza se reporta como `MISS`, no como silencio
visual. Último resultado: **19/19**.

---

## 7. Referencias históricas consultables

Se conservan como referencia visual, no como API:

- `steps/step23_fresh_theta/catalogo_ventanas/` (40), `catalogo_puertas/` (20),
  `catalogo_techos/` (20), `catalogo_cercos/` (10), `catalogo_entradas/` (10),
  `catalogo_frontones/` (16), `catalogo_remates/` (12), `catalogo_pilastras/`
  (35), `catalogo_balcones/` (103); cada caso trae su `.json` de solicitud.
- Diseño: `CATALOGO_VANOS.md`, `CATALOGO_CERCOS.md`, `CATALOGO_TECHOS.md`,
  `MATERIALES_MUROS.md`, `house_grammar/docs/guia_theta/CATALOGOS.md` y
  `REFERENCIA_CAMPOS.md`.

Pueden dejar de resolver con la gramática nueva; no se actualizan para
perseguir compatibilidad.

---

## 8. Huecos detectados (entrada para R1–R6)

Hallazgos de R0 que condicionan las fases siguientes:

1. **Dos motores de piezas conviven.** El nuevo `planning/` no importa el
   catálogo; sus previews de Fase 4/5 dibujan ventanas y puertas con geometría
   propia (`_joinery`) y no con `build_window`/`build_door`. R1/R3 deben
   conectar el catálogo y retirar el duplicado solo tras verificar equivalencia.
   → **R1 (hecho):** la mitad de coronación y balcones ya está conectada
   (`planning/catalogue.py` con `build_crown`/`build_balcony`); los vanos
   (`_joinery`) siguen pendientes para R3.
2. **El render ya no es el cuello de botella.** A partir de aquí, una pieza que
   se vea mal es geometría, no dibujo.
3. **Los catálogos aceptan hoy "aristas de masa".** R1 debe publicar superficies
   con ID, sistema local, normal, espesor y región de fachada para que el
   anclaje no dependa de la numeración de aristas.
   → **R1 (hecho):** `domain/surfaces.py` publica `WallSurface`/`SurfaceChart` y
   `planning/chart.py` las deriva de las masas nuevas; `crown_resolver` y
   `balcony_resolver` ya las consumen y el balcón se ancla al plano construido
   (`plane_offset_m`), con espesor declarado (`thickness_m`) y regiones visibles
   validadas (véase `experiments/r1/README.md`). La regla de estilo
   (`domain/styles.resolve_style`) ya no rechaza excepciones locales en ninguno
   de los cinco resolvers.
4. **El vocabulario de uso/tipología no existe** en `intent-v1` (solo
   `organization/profile/style`). R2 lo introduce.
5. **`DoorControls.portal_depth_m` ya prevé profundidad propia**; conviene
   usarla en R3 en vez del retranqueo único actual.

---

## 9. Checklist R0

- [x] Matriz de conservación de los nueve catálogos (contrato, resolutor,
  constructor, anclaje, muestras, pruebas).
- [x] Separación explícita capacidad vs JSON histórico.
- [x] Render con profundidad real (z-buffer) conectado a los exportadores.
- [x] Pruebas del renderizador (`tests/test_software_render.py`, 7 casos).
- [x] Casos mínimos nuevos fuera de `steps/` con verificación de semántica.
- [x] Referencias históricas catalogadas.
- [x] No aprobar integración con los PNG antiguos: quedan sustituidos.
