# ☁️ Experimentos: Supercomputador Khipu y COLMAP

**Objetivo:** Reconstruir la geometría de Barranco vista desde arriba usando un video de Dron de DJI y el clúster Khipu de UTEC.

## Contexto de Khipu
- El clúster corre SLURM. Se usó la partición `gpu` (nodos como `ag001` y `g002`).
- **Restricción Crítica:** La política `QOSMaxMemoryPerUser` limita la memoria RAM. El script inicial pedía 120GB, lo que provocaba rechazos instantáneos de SLURM. El límite seguro probado es **64GB**.
- Problemas de SSH: Debido a que la llave de SSH de César usa `passphrase`, comandos en background locales (`nohup ssh... &`) fallaban porque no podían pedir contraseña. Todo debía correr nativamente en batch en el servidor.

## Primera Iteración: El colapso por RAM (OOM)
- **Directorio original:** `~/tesis_colmap/tomasa`
- COLMAP procesó el paso disperso pero colapsó trágicamente durante `stereo_fusion`.
- **Causa:** Intentó fusionar **93 GB de mapas de profundidad** en RAM, superando con creces los 64 GB permitidos por SLURM (Out of Memory).
- **Solución implementada:** Se escribió un script de rescate `fuse_job_cached.sh` inyectando los flags `--StereoFusion.use_cache 1` y `--StereoFusion.cache_size 32`. Esto forzó a COLMAP a usar el disco duro como SWAP y limitó el uso de RAM a 32GB. Logró exportar exitosamente un archivo `fused.ply` de 1.5 GB.

## Segunda Iteración: Eficiencia y 1080p (El Bypass)
- **Directorio:** `~/tesis_colmap/tomasa_1080p`
- **Petición del usuario:** Crear una nube más ligera a 1080p y saltando fotogramas (0.5 fps), usando la GPU más potente.
- **La cadena de errores:**
  1. **Variables Bash:** Al usar variables `$` en la creación del script (`cat << 'SHEOF'`), se escribieron literalmente `\$COLMAP`, rompiendo el pipeline en el paso 1. (Solucionado usando EOF sin escape o escapando selectivamente).
  2. **Error de Robust Alignment:** COLMAP v3.13.0 en Khipu no reconocía `--robust_alignment 1` en `model_aligner`. Esto se borró del script.
  3. **Jerarquía Sparse:** COLMAP anidó el modelo en `sparse/0/0/`, pero el script buscaba en `sparse/0/`. Esto se ajustó en un script de reanudación.
  4. **El Desfase GPS (El error letal):** El script `inject_gps.py` tenía una expresión regular (Regex) defectuosa que no extraía bien las coordenadas `abs_alt` del archivo `.SRT` de DJI. Al estar a 0.5 FPS, los tiempos no coincidían. Esto generaba un `geo_priors.txt` vacío. Como resultado, `model_aligner` fallaba por "insufficient reference locations", dejando las carpetas vacías y rompiendo el paso final de PatchMatch.
- **Solución Radical (El Bypass):** Se corrigió el Regex, pero para agilizar, se omitió por completo el paso 6 (`model_aligner`), pasando directamente de `mapper` a `image_undistorter`. Perdimos la georreferenciación mundial, pero mantuvimos la estructura visual intacta.
- **Resultado (2026-08-30 21:31):** El Job **50353** finalizó exitosamente 10/10. La nube de puntos densa resultante (`fused.ply`) bajó de 1.5 GB a **solo 80 MB**, y la malla `meshed-poisson.ply` pesó 350 MB. Un éxito rotundo para obtener un Prior ligero para la tesis.

Para entender cómo usar este `fused.ply` de 80MB junto con los Lotes Catastrales, ver [[04_future_roadmap]].

## Tercera Iteración: Nube Dispersa (Sparse) Georreferenciada a 1 FPS
- **Directorio:** `~/tesis_colmap/tomasa_1080p_1fps_sparse`
- **Objetivo:** Obtener una reconstrucción dispersa ("Sparse") de muy alta calidad y perfectamente alineada con el GPS para usarla como base del modelo georreferenciado, sin malgastar cómputo en mallas densas.
- **Configuración (El Job Perfecto):**
  - Video copiado limpiamente y muestreado a **1.0 FPS** a resolución **1080p**. (196 imágenes estimadas).
  - El script `inject_gps.py` con su Regex parcheado fue sincronizado matemáticamente a `fps_extract=1.0`, asegurando que `geo_priors.txt` asigne las coordenadas ECEF correctas a cada imagen.
  - El Pipeline ejecuta `feature_extractor`, `sequential_matcher` y `mapper` generando la reconstrucción en `sparse/0/0/`.
  - Luego, ejecuta `model_aligner` leyendo `sparse/0/0/` con `--alignment_max_error 3.0` para amarrar la geometría a las coordenadas geográficas mundiales, depositándola en `sparse/0_aligned/`.
  - Finalmente, incluye el comando `model_converter` automatizado para escupir directamente `sparse_1fps_aligned.ply`.
- **Tiempos Estimados de Ejecución:** Para 196 imágenes a 1080p, la extracción de SIFT, emparejamiento y *Bundle Adjustment* (Mapper) tomará aproximadamente entre **15 y 25 minutos**.
- **Resultado Esperado:** Un archivo `.ply` que al importarse en cualquier software SIG caerá matemáticamente encima de los polígonos del catastro.
