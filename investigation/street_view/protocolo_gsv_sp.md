# Protocolo de Reconstrucción 3D de Google Street View (Línea Base Ancha)

## 1. Definición del Problema
Las imágenes de Google Street View (GSV) presentan un reto crítico para la fotogrametría clásica: **la línea base (distancia entre capturas) es de 15 metros**. A esta distancia, los descriptores tradicionales (como SIFT) fallan sistemáticamente debido a la severa distorsión de perspectiva, cambios bruscos de iluminación y falta de superposición, resultando en nubes de puntos fragmentadas (máximo 3 panoramas consecutivos).

## 2. Solución Arquitectónica
Para resolver este problema y lograr trayectorias ininterrumpidas de cuadras completas, este pipeline sustituye SIFT por Inteligencia Artificial (SuperPoint + LightGlue) y aplica transformaciones geométricas pre-calculadas a los panoramas esféricos.

### Parámetros Clave:
1. **Partición Perspectiva (FOV 135°):** 
   - Los panoramas esféricos (360°) se proyectan en 8 cámaras perspectivas estenopeicas (Pinhole) apuntando a diferentes ángulos (Yaw: 0, 45, 90...).
   - Se utiliza un **FOV ultra-ancho de 135°**. Esto obliga a un solapamiento lateral altísimo, garantizando que el punto ciego temporal de los 15 metros sea cubierto por la periferia del lente.
   - *Focal Teórica Exacta:* `212.08 px` (para un sensor de 1024x1024).
2. **Deep Feature Extraction (SuperPoint):**
   - Extrae puntos característicos resilientes a cambios drásticos de perspectiva (Aachen config).
3. **Deep Feature Matching (LightGlue):**
   - Red neuronal de atención (Transformer) que empareja los puntos de SuperPoint discriminando outliers geométricos masivamente mejor que los algoritmos de fuerza bruta o k-NN tradicionales.
   - Se configuran pares secuenciales (Ventana de Overlap = 30 imágenes) para forzar el anclaje entre un panorama y los panoramas vecinos subsiguientes.
4. **Bundle Adjustment y Alineación GPS:**
   - COLMAP Mapper (con `min_match_score=0.1` e inyección de parámetros fijos).
   - Aplicación de un **Transformación Rígida 3D (Model Aligner)** usando la data satelital extraída de la metadata `gps.csv`. 

## 3. Resultados Experimentales (Job 50673)
- **Registro:** 128 / 128 imágenes registradas (100% de éxito). Los 16 panoramas esféricos encadenados de principio a fin.
- **Nube:** 11,924 puntos estructurales firmes.
- **Error GPS:** 0.16 metros de error medio tras el alineamiento global, indicando que la calle mantiene su curvatura geográfica real sin "doblarse" sobre sí misma.

## 4. Uso del Automatizador en Khipu
Se ha diseñado un entorno automatizado en Khipu para reproducir esto con un solo comando.

1. Sube tu carpeta de proyecto (debe contener `images/` cortadas en FOV 135 y tu `gps.csv`) a Khipu.
2. Ejecuta el despachador apuntando a esa carpeta:
   ```bash
   bash ~/tesis_colmap/pipeline_gsv/submit_job.sh /ruta/a/tu/carpeta
   ```
El pipeline enviará el Job a SLURM, ejecutará HLOC y te dejará una carpeta `sparse_aligned/`.
