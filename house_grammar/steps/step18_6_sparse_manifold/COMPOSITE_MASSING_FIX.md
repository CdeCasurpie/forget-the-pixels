# Fix para Bug de Massing Compuesto (Edificios "Partidos")

## 1. El Síntoma Reportado
Al generar la cuadra, ciertas tipologías compuestas (`stepped_back`, `podium_tower`, `front_tall_rear_low`) producían edificios visualmente fracturados, con fachadas aisladas, paredes faltantes y techos desconectados.

## 2. La Hipótesis Original (Refutada)
La hipótesis del usuario planteaba que `apply_edge_setbacks(body, fronts, m.upper_setback_m + m.front_setback_m)` estaba aplicando el retiro doblemente respecto al `body`, causando un *gap* masivo (ej. un setback de 8.5m en lugar de 5.5m).

Tras realizar un análisis geométrico estricto, **esta hipótesis matemática es incorrecta**:
* `apply_edge_setbacks` utiliza `fronts` como referencia, que es el frente original de la parcela (`y=0`), **no el borde del `body`**.
* Por lo tanto, para lograr que la masa hija se ubique a `2.5m` del `body` (el cual ya está a `3.0m`), es **matemáticamente obligatorio** pasar `5.5m` a la función, ya que el cálculo se hace desde `y=0`.
* Se crearon tests (ver `tests/test_theta_massing_assembly.py`) que demuestran formalmente que los polígonos 2D son matemáticamente perfectos: `setback` descansa exactamente sobre `main`, y `front` comparte un borde 100% contiguo con `rear`. **No existen huecos ni "gaps" topológicos.**

## 3. La Verdadera Causa Raíz (Confirmada)
Si las masas son perfectas matemáticamente, ¿por qué desaparecen partes en el render 3D?

El problema reside en un **Bug de Precisión de Punto Flotante (Floating Point Precision)** entre la capa de exposición (`exposure.py`) y la generación de muros (`theta.py`).

1. **La Limpieza en `exposure.py`**: Al calcular bandas de exposición Z, `calculate_mass_exposures` aplica `shapely.set_precision(poly, grid_size=1e-4)` para resolver inconsistencias booleanas.
2. **La Intersección en `theta.py`**: Durante el armado final de muros, `theta.py` itera sobre el *ring original* (sin precisión aplicada):
   ```python
   line = LineString([a,b])
   segment = line.intersection(band["exposed_segments"])
   ```
3. **Fallo Silencioso**: En parcelas catastrales reales (con ángulos e imperfecciones) o cuando `offset_curve` devuelve flotantes infinitos, `line` se desvía microscópicamente ($\sim 10^{-14}$) de `exposed_segments`.
4. En Shapely, la intersección de dos líneas casi paralelas pero microscópicamente desfasadas es **VACÍA**.
5. Al cumplirse `segment.is_empty`, el muro entero se salta (`continue`) y **NO se genera**.
6. Como las masas compuestas comparten fronteras internas complejas, las paredes laterales y fronteras que "deberían" ser exterior caen en este desajuste de precisión. Al no generarse, el edificio pierde sus costados, dejando solo la fachada frontal flotando como una hoja de papel (aislada).

## 4. La Solución (Aplicada)
Se modificó `src/modeling/theta.py` para sincronizar la precisión de la línea evaluada con el grid de exposición antes de calcular la intersección:

```python
# src/modeling/theta.py - Línea ~406
clean_line = shapely.set_precision(line, grid_size=1e-4)
for band in exposures[mass.id]["walls"]:
    segment = clean_line.intersection(band["exposed_segments"])
```

## 5. Invariantes Geométricos Garantizados
Se añadió una suite formal en `tests/test_theta_massing_assembly.py` que asegura las siguientes invariantes requeridas por el usuario:
* **`single_block`**: `footprint` base inicia exactamente a distancia `front_setback_m`.
* **`stepped_back`**: `setback footprint ⊂ main footprint` (El `body` cubre al `top`). Alturas contiguas (`main.roof_z == setback.base_z`). Distancia incremental desde el `body` equivale estrictamente a `upper_setback_m`.
* **`front_tall_rear_low`**: `front ∪ rear ≈ body`. Área de intersección es nula, pero la longitud de frontera compartida es estrictamente $> 0$.

El problema ha sido aislado y corregido manteniendo la arquitectura de la gramática V1.1 intacta.
