# Cuadra → lotes + fotos (sin gramática todavía)

`extraer_fotos_cuadra.py` toma **una sola cuadra** (el centro de
`step1_select_block.select_block_lots`, sin alrededores) y, lote por lote:

1. Limpia y simplifica el polígono con `--simplify-tolerance-m`
   (funde vértices casi-duplicados; por defecto 0.10 m).
2. Calcula frentes con `spatial.street_fronts` (misma regla que step3).
3. Busca panoramas GSV cercanos a la cuadra (una sola caminata BFS),
   rankea por lote con `vision.cameras.select_cameras` (oclusión + frontalidad)
   y descarga los necesarios (`--zoom`, por defecto 3).
4. Recorta por cámara una franja cilíndrica centrada en el lote con
   `vision.projection.extract_full_vertical_strip`: esa es la foto usable.

```bash
python steps/step19_experimental/cuadra_fotos/extraer_fotos_cuadra.py --seed 123 --fotos-por-lote 2
python steps/step19_experimental/cuadra_fotos/extraer_fotos_cuadra.py --seed 123 --simplify-tolerance-m 0.15
```

Salida en `steps/step19_experimental/cuadra_fotos/cuadra_seed_<seed>/`:

- `manifest.json` — estado por lote (`ok` / `parcial` / `sin_visibilidad` / `failed`).
  `verificada` = arista visible confirmada por `src` (oclusión + frontalidad);
  `sin_visibilidad` = panorama más cercano, solo para inspección manual, no
  como evidencia de fachada.
- `mapa_cuadra.png` — los 24 lotes numerados.
- `panoramas/<pano_id>.jpg` + `panoramas_metadata.json` — caché única.
- `lote_<index>/lot.json` — `parcel_local_m` (anillo CCW como el que step3
  pasa a `ReconstructionContext`), `fronts`, `front_source`, `street_edges`,
  simplify, cámaras.
- `lote_<index>/fotos/vista_<NN>_<pano>.jpg` — ≥2 fotos por lote.

El paso siguiente (pendiente) será generar un GLB por lote con la gramática
y unirlos en un único modelo para render/Blender.
