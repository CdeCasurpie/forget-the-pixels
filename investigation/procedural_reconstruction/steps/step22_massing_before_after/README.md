# Step 22 — Edificios por lote, before/after

**Estado:** 20 lotes seleccionados, 20 mallas `before` validadas con la
gramática de `src` sin masas explícitas. Diecinueve tienen comparativas
foto | render; el lote `1138310` tiene cinco vistas `absent` y solo renders
sin imagen etiquetada para comparar. Los `after/` siguen vacíos. El baseline
sintético anterior fue retirado y no forma parte de este recorrido.

`lotes/TRACKING.md` contiene el algoritmo de inspección y el checklist.
La ampliación de masa `theta 0.3` y sus 19 resultados `after/` se explican en
`MASSING_REDESIGN.md`, `AFTER_REVIEW.md`, `after_recipes.json` y `build_after.py`.
La extensión horizontal de fachada y las dos demostraciones BCP/Metro están
en `FACADE_ZONES.md`, `facade_zone_recipes.json` y `after_facade_zones/` de esos lotes.
Los ritmos BayGroup y su relief compartido se documentan en `BAY_GROUPS.md`;
`build_bay_groups.py` reproduce únicamente BCP y Metro en `after_bay_groups/`.
La prueba opt-in `monumental_portal` de Metro se documenta en
`MONUMENTAL_PORTAL.md` y `after_monumental_portal/`.
`lotes/AUDITORIA_COMPARATIVAS.md` contiene el diagnóstico visual lote por
lote, separando errores de elección de θ y límites reales de la gramática;
`lotes/AREA_LIBRE_AUDIT.md` detalla las pruebas de retiro/cerco.
Cada `lotes/<id>_<tipo>/README.md` identifica la evidencia, el θ propuesto
y las brechas observadas. Los lotes generados en la última pasada son
**primeras propuestas**, no resultados de una búsqueda exhaustiva ni
semejanza fotográfica garantizada.

## Entradas

- `../step21_lot_fronts/seleccion/lotes.json`: IDs seleccionados.
- `../step21_lot_fronts/lot_fronts.json`: lados despejados inferidos.
- `data/lotes/BARRANCO_LM_geogpsperu.geojson`: geometría catastral original.
- `data/cadastral_offset.json`: solo colocación comparativa del modelo ante
  cámaras Street View, no modificación de la parcela en θ.
- `edificios_a_probar/<id>/`: fotos JPG, `views.json`, `segmentation.json`,
  máscaras y vistas de inspección.

## Reproducción

Desde `investigation/procedural_reconstruction/` con el venv310:

```bash
python steps/step22_massing_before_after/build_mask_previews.py
python steps/step22_massing_before_after/build_lot_before.py \
  --lot 1135847 --name local_comercial_bajo --seed 11 \
  --theta-file steps/step22_massing_before_after/lotes/1135847_local_comercial_bajo/analisis_theta.json
python steps/step22_massing_before_after/lotes/build_remaining.py
```

`build_remaining.py` omite lotes ya generados; para regenerar un caso se
ejecuta `build_lot_before.py` directamente con su `analisis_theta.json` y
la semilla del `request.json` existente. No ejecutar `build_test_buildings.py`
sobre etiquetas existentes: reconstruye JPG recortados que el usuario marcó
`absent` y eliminó voluntariamente.

## Salidas por lote

`before/request.json`, `resolved_theta.json`, `building.glb`,
`render_<camera>.jpg`, `compare_<camera>.jpg` y `manifest.json`. Las
comparativas ponen la foto a la izquierda y la malla a la derecha con el
mismo ojo, orientación y FOV. El modelado usa la parcela original en metros
locales; el desfase guardado se aplica solo en los renders de comparación.

`edificios_a_probar/<id>/` contiene `<camera>_mask.png` (binaria),
`<camera>_masked.jpg` (foto con fondo negro), `<camera>_overlay.jpg`
(selección verde) y `<camera>_lot.jpg` (guía catastral amarilla). El
etiquetador interactivo se abre con
`python steps/step22_massing_before_after/label_buildings.py`.
