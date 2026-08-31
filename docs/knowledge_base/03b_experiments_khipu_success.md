## Iteración 4: Éxito total Sparse Georeferenciado (1 FPS)

**Fecha:** 2026-08-31
**Objetivo:** Nube de puntos sparse con 1 FPS y coordenadas ECEF reales, usando el nuevo framework `khipu-colmap`.

**El último gran Bug descubierto (Doble Conversión ECEF):**
El job generó correctamente las poses (`sparse/0/1`), pero `model_aligner` falló nuevamente mostrando en consola: `Converting Alignment Coordinates from GPS (lat/lon/alt) to ECEF.`

**Causa raíz:**
1. Nuestro script en python `dji_srt.py` ya estaba haciendo la conversión matemática de grados Lat/Lon/Alt a cartesianas ECEF (X, Y, Z en metros).
2. COLMAP asume por defecto (`--ref_is_gps 1`) que los valores en `geo_priors.txt` están en formato `Latitud Longitud Altitud`, ¡e internamente hace su propia conversión a ECEF!
3. Por lo tanto, COLMAP recibía nuestros valores de $X \approx 1,500,000$ (metros) y los trataba como si fueran grados de Latitud, causando un desbordamiento matemático que rompía el algoritmo RANSAC, haciendo fallar la alineación silenciosamente.

**Solución definitiva:**
Se agregó el flag `--ref_is_gps 0` al script SLURM dentro del framework. Esto le avisa a COLMAP que las coordenadas provistas en el archivo de texto ya son cartesianas (ECEF locales) y que NO debe convertirlas. 

**Resultado de ejecutar con el flag corregido:**
```
=> Using 196 reference images
=> Alignment error: 1.206682 (mean), 1.143257 (median)
=> Alignment succeeded
```

**Resultado:**
- Se logró un error medio de **1.2 metros**. Tratándose de un drone comercial cuyo GPS tiene una tolerancia natural de ~3 metros de ruido atmosférico, ¡esto es un ajuste RANSAC estadísticamente perfecto!
- Se exportó la nube georeferenciada exitosamente a `sparse_1fps_aligned.ply`.
- El framework local `khipu-colmap` quedó completamente blindado contra este fallo y desplegado en Khipu.
