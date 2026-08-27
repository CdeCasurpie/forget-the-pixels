# Nuevas Ideas y Brainstorming de la Tesis (Pipeline Semántico Top-Down)

## 1. Preprocesamiento: Eliminación de Ruido Dinámico
- **Concepto**: Aplicar algoritmos de *Video Inpainting* (o simplemente enmascarar) para ignorar objetos dinámicos (autos, personas, animales, etc.).
- **Beneficio**: Estabiliza el modelo de *tracking* de cámara (Odometría/SfM).

## 2. Tracking y Matching 2D-2D de Nodos Estructurales (Wireframes)
- **Concepto**: Entrenar/usar modelos de Deep Learning para detectar y hacer *matching* de "nodos estructurales" (esquinas arquitectónicas, intersecciones de líneas) entre imágenes 2D.
- **Detalle**: Se cuenta con data de WIREFRAMES extraída (ej. Co-PLNet). El matching de estas líneas y nodos entre frames garantiza un tracking libre de ruido.
- **SOTA Recomendado**: **GlueStick** (Joint Point-Line Matching) que une nodos y líneas en un GNN unificado. Alternativa para líneas ocluidas: **LineTR**.

## 3. Segmentación Semántica y Clasificación Planar vs. No-Planar
- **Concepto**: Por cada imagen, aplicar modelos fundacionales de segmentación.
- **SOTA Recomendado para Planos**: **ZeroPlane** (In-the-wild 3D Plane Reconstruction), que supera a PlaneRCNN y SAM porque está entrenado en 14 datasets para exteriores y no necesita fine-tuning. Alternativa híbrida: usar **DUSt3R / Depth Anything V2** para obtener profundidad y aplicar RANSAC clásico.
- **Fusión Temporal (Video)**: Los segmentos 2D no se procesan de forma aislada. Aprovechando el video, se identifican y fusionan los segmentos semánticos que se solapan entre fotogramas para agruparlos como un único gran plano físico, resolviendo el problema de la oclusión parcial.

## 4. Triangulación y Ajuste de Planos (LO-RANSAC)
- **Triangulación Dispersa**: Una vez que se tienen los nodos estructurales y el tracking, se triangula mediante geometría epipolar (`solvePnP`).
- **Agrupación y LO-RANSAC**: Para cada súper-segmento fusionado, se toman los nodos estructurales 3D que caen dentro de él y se ajusta el plano matemático con LO-RANSAC.

## 5. Extracción de Fronteras (Boundaries) y Texturizado
- **Wireframes como Fronteras**: Para delimitar el plano infinito de RANSAC y convertirlo en un polígono finito, se usan los *wireframes* 2D proyectados y los bordes de la máscara de segmentación. Las líneas del wireframe y el borde del segmento deberían coincidir, proporcionando un límite coherente.

## 6. Tratamiento de Objetos Complejos (No-Planos)
- **Generación Procedimental / Trabajo Futuro**: Elementos muy ornamentados (balcones republicanos) que sí tienen nodos estructurales pueden generarse proceduralmente a futuro.
- **Marcado de Bounding Boxes**: Estatuas, macetas u objetos complejos se marcan con cajas limitadoras (Bounding Boxes) o se les reemplaza por un asset genérico. Posteriormente pueden reconstruirse con MVS local o de forma manual, evitando que el pipeline global falle.

## 7. Estado del Arte: Papers Similares (Reconstrucción "MVS-Free")
La comunidad científica respalda esta dirección (evitar la densificación masiva de MVS). Aquí están los papers top que debes citar en tu tesis para validar tu enfoque:
- **PlanarSplatting (CVPR 2025):** Estado del arte en velocidad. Optimiza primitivas planas 3D directamente contra las imágenes usando renderizado diferenciable, eliminando la nube densa.
- **DUSt3R (CVPR 2024):** Evita el pipeline de MVS clásico transformando la reconstrucción 3D en un problema de regresión directa con Transformers.
- **PlaneRCNN (CVPR 2019):** Pionero en el uso de Deep Learning para predecir parámetros 3D y máscaras de segmentación de planos desde una sola imagen.
- **StreetSurf (ICCV 2023):** Usa Campos Neuronales Implícitos (SDFs) con restricciones de planaridad para generar mallas poligonales limpias de calles sin correlacionar millones de píxeles.
- **Plane-based SLAM (ej. Atlas):** Demuestran que rastrear planos en lugar de millones de puntos ahorra memoria masivamente en entornos artificiales (Manhattan-world).
