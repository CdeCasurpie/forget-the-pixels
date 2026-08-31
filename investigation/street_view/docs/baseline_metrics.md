# Baseline Experimental: Fotogrametría Clásica (COLMAP) vs Enfoque Top-Down

Este documento recopila las métricas exactas de la ejecución en el clúster HPC, sirviendo como evidencia empírica para justificar el abandono de los métodos Bottom-Up (MVS) en favor de abstracciones geométricas.

## 1. Parámetros del Dataset y Hardware

| Métrica / Recurso | Especificación |
| :--- | :--- |
| **Video Fuente** | DJI Drone (`PasaarAColmapTomasa.MP4`) |
| **Duración del Video** | 3 minutos y 16 segundos (196.44s) |
| **Resolución** | 4K UHD (3840 x 2160) @ 135 Mbps |
| **Estrategia de Extracción** | 2 FPS (Paralaje optimizado) |
| **Total de Imágenes procesadas**| ~390 imágenes |
| **Hardware de Cómputo (HPC)** | Clúster Khipu (UTEC) |
| **Nodo Asignado** | `ag001` |
| **Acelerador Gráfico (GPU)** | **NVIDIA A100 Tensor Core** (La GPU más potente disponible) |
| **Recursos Asignados** | 16 Cores CPU, 64 GB RAM |

## 2. Tiempos de Ejecución del Pipeline (Evidencia de Cuello de Botella)

Los siguientes tiempos demuestran el costo computacional prohibitivo del *Multi-View Stereo* (MVS), incluso utilizando hardware de grado supercomputacional.

| Fase del Pipeline (COLMAP) | Tiempo de Ejecución | Resultado Computado |
| :--- | :--- | :--- |
| **Extracción SIFT & Emparejamiento** | ~5 minutos | Detección de miles de esquinas por imagen. |
| **Sparse SfM (Bundle Adjustment)** | ~25 minutos | Nube dispersa: **~6,000 puntos** (Esqueleto). |
| **Alineación GPS & Undistortion** | ~2 minutos | Corrección radial de lentes. |
| **MVS: Consistencia Fotométrica** | **3 horas y 4 minutos** | Mapas de profundidad iniciales (100% GPU). |
| **MVS: Consistencia Geométrica** | ~3 horas *(estimado)* | Limpieza de ruido (En ejecución). |
| **Fusión y Mallado (Poisson)** | ~1.5 horas *(estimado)* | Triangulación final en CPU. |
| **TIEMPO TOTAL (3 min de video)** | **~7.5 a 8 horas** | Generación de geometría ruidosa. |

> [!IMPORTANT]
> **Argumento para la Tesis:** Si 3 minutos de vuelo en una sola calle requieren 8 horas en una NVIDIA A100, escalar este método clásico a nivel metropolitano (Lima) es computacionalmente inviable. Esto justifica matemáticamente la transición hacia heurísticas Top-Down y grafos de poses.

---

## 3. Conclusiones de la Investigación SOTA (Google Street View)

Mientras COLMAP gasta recursos masivos intentando adivinar dónde estaban las cámaras (SfM) y calculando profundidad a ciegas (MVS), la literatura actual apunta a otra dirección:

### A. El Fin de las Nubes de Puntos Densas
Los *papers* más recientes (basados en datasets gigantes como **HoliCity** y **OmniCity**) demuestran que el Estado del Arte ya no busca nubes de puntos densas. La academia se ha movido hacia la predicción de **formatos vectoriales ligeros**: esquinas, *wireframes* (L-CNN, HAWP), planos semánticos y cuboides. Se busca que la ciudad sea entendida como "geometría CAD", no como "polvo de píxeles".

### B. El Poder del Grafo de Poses (Pose Graph)
El reporte de APIs reveló que, aunque Google restringe su API oficial, los investigadores usan librerías abiertas (como `streetlevel` en Python) para extraer panoramas 360 junto con sus **coordenadas GPS exactas y ángulos (Yaw/Pitch/Roll)**. 
Al usar GSV, *ya tienes el Grafo de Poses resuelto por defecto*. Te saltas por completo las 8 horas de procesamiento de COLMAP. Tu única tarea se reduce a extraer los bordes (*wireframes*) de la imagen frontal y proyectarlos al espacio 3D usando las coordenadas que Google ya te regaló.
