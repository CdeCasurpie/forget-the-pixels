# 🧠 Knowledge Base: Olvida los píxeles (Tesis)

Bienvenido a la base de conocimiento del proyecto de tesis: **"Olvida los píxeles: Modelado estructural a escala metropolitana guiado por grafos de poses y abstracción geométrica"**. 

Este repositorio documental está diseñado para ser leído en **Obsidian** y sirve como memoria persistente para el investigador (César) y cualquier Inteligencia Artificial (IA) que colabore en el proyecto en el futuro.

## 🗂️ Índice de Contenidos

### 1. Marco Conceptual e Ideas
- [[01_core_concepts_and_ideas]]: Fundamentos de la tesis. ¿Por qué abandonar los píxeles densos (Bottom-Up) y usar geometría catastral plana (Top-Down)? La sinergia entre lotes catastrales y fotogrametría.

### 2. Registro de Experimentos (Bitácoras)
- [[02_experiments_street_view]]: Experimentos procesando imágenes 360° de Google Street View, estimación de profundidad monocular (Depth Anything V2), superpíxeles de Felzenszwalb y segmentación de planos con RANSAC.
- [[02b_experiments_wireframe_heuristic]]: Experimento de MVP algorítmico para reemplazar redes pesadas (Co-PLNet) extrayendo topología estructural (aristas) mediante fuerza bruta de conexiones y funciones de costo sobre filtros Canny.
- [[03_experiments_khipu_colmap]]: Bitácora detallada del procesamiento de videos de Dron (Tomasa) en el supercomputador Khipu usando COLMAP. Resolución de errores de Memoria RAM (OOM), sincronización GPS y pipelines de optimización.

### 3. Planificación y Roadmap
- [[04_future_roadmap]]: El plan a futuro. Integración de los lotes catastrales de Barranco con las nubes de puntos de COLMAP, proyecciones de texturas y 3D Gaussian Splatting (3DGS) restringido por geometría.

---
*Última actualización general: 2026-08-31*
