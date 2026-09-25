# Cuadra procedural progresiva

Desde `investigation/procedural_reconstruction/`:

```bash
python scripts/step1_select_block.py
python scripts/step3_generate_full_block.py --max-lots 2 --output-dir /tmp/cuadra_prueba
python scripts/step3_generate_full_block.py
```

La selección parte de un lote semilla reproducible (`--seed 123`), expande
su manzana y después incorpora las manzanas vecinas hasta 20 m
(`--surrounding-m`). El orden de generación coloca primero todos los lotes de
la manzana central; dentro de ella empieza cerca del lote semilla.

`step3` genera cada casa con `ThetaCandidate` 0.2, verifica que su malla tenga
muros hasta el suelo, exporta un GLB individual temporal y lo incorpora al
`outputs/cuadras_completas/cuadra_completa.glb`. El archivo visible se reemplaza
de forma atómica al terminar cada casa. El programa vuelve a escribir el GLB
completo porque el formato no permite agregar bytes arbitrariamente al final;
el acumulador reutiliza los buffers glTF existentes sin recalcular las mallas.

Los archivos de seguimiento son:

- `progress.json`: estado general, resultados por lote y memoria del proceso;
- `timings_per_house.csv`: tiempos de geometría, exportación individual,
  incorporación al GLB, tamaño y memoria por casa;
- `lot_selection.png`: manzana central en rojo y alrededores en gris;
- `cuadra_completa_iso.png`: vista rápida solo para pruebas de hasta 10 lotes.

Por defecto el GLB usa colores PBR sin mapas de textura, apropiado para probar
la estructura. `--textures` incorpora los mapas y aumenta tiempo/tamaño.
`--no-render` omite la vista isométrica. `--max-lots N` limita la prueba a los
primeros N lotes del mismo orden.

Un borde clasificado como calle se marca `street_inferred`. Si un lote no tiene
ningún borde así, se elige el borde de mayor separación como hipótesis y queda
marcado `fallback_unverified` en los reportes. Los vanos de fachadas demasiado
estrechas prueban primero un solo eje; si todavía no caben, esa fachada queda
ciega (`facade_mode=blank_facade`). Esas hipótesis solo sirven para la vista
exploratoria y no sustituyen evidencia de Street View.

Una nueva ejecución empieza otra vez desde el primer lote. Para observar un
checkpoint abierto en un visor GLB, recarga el archivo después de que avance
el contador `generated` de `progress.json`.
