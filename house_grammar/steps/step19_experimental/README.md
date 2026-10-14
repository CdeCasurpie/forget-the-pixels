# Step 19 — archivo experimental (2026-10-06)

Todo lo que estaba en `scripts/` y era operativa de experimentos viejos se
movió aquí intacto para limpiar la raíz de `scripts/`. Nada de esto se usa en
el pipeline actual (cuadra seed 123), salvo dos módulos importados con
`sys.path` explícito desde `scripts/cuadra_fotos/`.

## Contenido movido

| Archivo | Qué hacía |
|---|---|
| `step1_select_block.py` | Elige cuadra semilla + alrededores desde el catastro (`load_lots`, `select_block_lots`). **Aún importado** por `extraer_fotos_cuadra.py` y `tests/test_block_progress.py` |
| `step3_generate_full_block.py` | Generaba manzanas con thetas aleatorios y GLB acumulado. Reemplazado por el flujo foto→theta→GLB de `cuadra_fotos/`; solo se reutilizan `combine_meshes` (lógica) y `select_fronts` en tests |
| `glb_incremental.py` | `append_glb`: concatena GLBs sin re-decodificar. **Aún importado** por `unir_cuadra_glb.py` y tests |
| `download_assets.py` | Descarga suelta de assets viejos (reemplazado por `scripts/descargar_fotos.py`) |
| `render_objs.py` | Render de OBJs sueltos, fuera del pipeline GLB |
| `gis/` | `align_2d_cv2`, `align_lotes`, `extrude_lotes`, `texture_lotes`, `check_camera_points`: extrusión/texturizado plano pre-gramática |
| `golden_v1/` | Set dorado de la gramática congelada (referencia, no se ejecuta) |
| `README_block_progress.md` | Bitácora de la cuadra procedural aleatoria |

## Lo que NO se movió (trabajo activo en `scripts/`)

- `cuadra_fotos/` — extracción de fotos, thetas manuales, GLB por lote, unión y recorrido dual.
- `generacion_mannual/` — generaciones manuales sueltas con comparativas.

## Experimentos de cuadra y generación manual (movidos aquí el 2026-10-06)

- `cuadra_fotos/` — pipeline foto→theta→GLB por lote (cuadra seed 123: 24 lotes,
  `cuadra_completa.glb`, recorrido dual GSV-vs-modelo).
- `generacion_mannual/` — 4 generaciones manuales sueltas con comparativas.
