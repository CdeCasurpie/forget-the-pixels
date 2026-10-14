# Grammar V1.1 Sparse Materializer Report

## 1. Problema Original
La gramática procedimental "Forget the Pixels" utilizaba un "materializador geométrico" excesivamente denso (Uniform Grid Refinement). Paredes arquitectónicamente planas se subdividían en miles de caras (grid de ~0.5m) de manera artificial. Además, los componentes decorativos y recubrimientos se resolvían con operaciones locales pesadas y no-manifold, causando una explosión inmanejable de triángulos y componentes en bloques reales, volviendo imposible renderizar cuadras completas (ej. un lote real podía superar los 50,000 triángulos).

## 2. Causa Raíz
Las limitaciones en la lógica de triangulación (en particular `max_aspect` y `min_angle_deg`) requerían que ninguna tira larga fuera "demasiado delgada", forzando una malla uniforme en toda la fachada solo para acomodar elementos menores como marcos de ventanas o bordes de pared. 

## 3. Algoritmo Original
La lógica construía el muro iterando sobre la grilla y cortando agujeros, resultando en `~13,000 - 30,000` triángulos para un ejemplo simple. 

## 4. Nuevo Algoritmo
"Sparse Manifold Materializer": Se eliminaron las restricciones de la cuadrícula, permitiendo generar "Sparse Shells" donde una pared rectangular enorme se resuelve con sólo 2 polígonos. Los elementos de detalles (ventanas, recubrimientos) usan un enfoque de Constrained Triangulation sin propagar vértices al resto del muro. 

## 5. Por qué Manifold no requiere Grid
Un sólido manifold (cerrado y continuo) sólo requiere que sus vértices en los límites compartan aristas adecuadamente. No es necesario subdividir las caras planas internas mientras los contornos estén triangulados correctamente.

## 6. Flat Wall Complexity
Una pared ciega plana de 1m x 1m o de 50m x 50m produce ahora la misma cantidad de vértices (~8) y triángulos (~12) en su volumen tridimensional.

## 7. Wall-with-openings Complexity
El costo geométrico ahora escala localmente y de forma lineal respecto al número de huecos (ventanas/puertas), en lugar de cuadradamente por el área total del muro.

## 8. Constrained Triangulation
Se reemplazó el antiguo sistema por una triangulación condicionada de GEOS (Shapely), lo cual permite agujeros perfectos sin "T-junctions".

## 9. Overlays Estructurales
Las vigas y columnas estructurales ya no dividen el muro principal. Ahora son emitidas como "Overlays" geométricos independientes, manifold por sí mismos, aliviando enormemente la teselación de las caras laterales de ladrillo.

## 10. Coatings / Material Regions
Las regiones de materiales finos (pintura, estuco) se proyectan a ~2mm de la pared base (`SURFACE_EPSILON_M`), creando sólidos cerrados separados en lugar de cortar el muro principal.

## 11. Cadastral Clipping Fixes
Se corrigieron errores donde las proyecciones y materiales superaban el límite de la parcela (`street_envelope`), incluyendo un bug crítico donde componentes "clipeados" se separaban en islas desconectadas, causando una arista no-manifold (valencia 4). Ahora cada isla se emite como un componente independiente cerrado.

## 12. LOD (Level of Detail)
Se amplió el uso de `DetailBudget`. Ahora existen niveles BLOCK, STREET, y CLOSE_UP que omiten micro-geometría como barrotes (balustrades), cortinas y persianas para reducir la complejidad aún más al nivel de bloque.

## 13. Runtime GLB Batching
Para la exportación en tiempo de ejecución, el GLB ahora agrupa los componentes primitivos que comparten materiales. Mantiene los IDs para autoría pero colapsa la estructura semántica en runtime, reduciendo masivamente el overhead del motor gráfico.

## 14. Baseline
El baseline usaba la técnica vieja. Los manuales iban de 15k-25k, y reales promediaban 40k-50k. 

## 15. Resultados Manuales
Los 5 casos manuales (simple, republicano, galeria, mixed, setback) bajaron a ~3,400 - 7,850 triángulos, con una reducción promedio del 75%.

## 16. Resultados Lotes Reales
Lotes reales mostraron reducciones dramáticas:
- `lot_1849`: 43,930 -> 8,736 (-80.1%)
- `lot_2451`: 50,552 -> 16,420 (-67.5%)
- `lot_1843`: 38,838 -> 11,052 (-71.5%)

## 17. Benchmark 20 Casas
El script automatizado probó la cuadra progresiva y validó 20 lotes secuenciales sin interrupciones. Todos generaron "0 topology violations".

## 18. Benchmark 50 Casas
Se probó con éxito la escala superior: 50 casas consecutivas superaron la estricta validación topológica.

## 19. Triangles Before/After
Reducción total de polígonos: **~70-80%** en todo el espectro de casos probados.

## 20. Nodes Before/After
Al usar el runtime export en el bloque de 20 casas, los nodos del glTF cayeron de 6,889 (authoring) a 566 (runtime). ¡**Reducción del 91.8%** en la jerarquía del scene graph!

## 21. GLB MB Before/After
En el bloque de 20 casas, el peso del archivo cayó de 8.7 MB a **4.0 MB** (-54%).

## 22. RAM Peak
El pico de consumo de memoria al generar el glTF (RSS) cayó de 1,375 MB a tan solo **230 MB**. 

## 23. Visual Comparison
Las imágenes isométricas antes/después muestran diferencias visuales imperceptibles. En la métrica de IoU para la máscara, la similitud visual de los manuales y reales probados es **> 0.995**.

## 24. Architecture Hash
La resolución arquitectónica semántica se ha conservado idéntica. El hash validado (`architecture_equal`) se mantuvo `True` para el 100% de los lotes evaluados en `compare.py`.

## 25. Topology Results
El 100% de las nuevas mallas pasaron el validador estricto sin emitir un solo polígono duplicado, degenerado o arista non-manifold.

## 26. Test Suite
La suite completa de tests de reconstrucción procedural y geometría (217 tests, 125 subtests) corre sin errores (100% GREEN) en ~65 segundos.

## 27. Remaining Hotspots
El nuevo "Top 5" de elementos por costo geométrico (triángulos) son:
1. `balcony_bar`
2. `structural_column`
3. `curtain_fold`
4. `slim_frame`
5. `wall`

El muro principal (`wall`) ha bajado del #1 abrumador al modesto #5, demostrando que ahora **el peso se dedica a los detalles arquitectónicos**.

## 28. Limitations
La principal limitación es que la topología ha mutado radicalmente; un modelo generado en V1.0 no encajará geométricamente vértice-por-vértice con V1.1. No obstante, ambos provienen de la misma definición de arquitectura semántica explícita.

## 29. Commits
El trabajo abarcó:
- Remoción de `uniform_refinement` y uso de constrain triangulations.
- Recubrimientos manifold (local manifold coatings).
- Reducción de microgeometría estructural repetida.
- Batches semánticos de exportación en runtime (preservando UVs).
- Fix de clipping cadastral desconectado.
- Validaciones completas (benchmark regress, runtime validation).

## 30. Recomendación sobre grammar-v1.1
**Recomendación:** Congelar este estado y promover formalmente a `grammar-v1.1`.
Se han cumplido sobradamente los objetivos. Tenemos mallas puras manifold, arquitecturas preservadas al 100%, huella de RAM ridículamente pequeña, y reducciones de geometría gigantescas donde el costo ahora escala directamente en proporción al verdadero detalle del edificio.
