# Exploración Avanzada en Google Street View: Estimación Monocular y Fotogrametría IA

**Directorio:** `street_view/`

Este directorio contiene los esfuerzos por reconstruir geometría a partir de imágenes de Google Street View (GSV), superando las limitaciones nativas mediante dos enfoques experimentales:

## 1. Enfoque A: Estimación Monocular (DepthAnything V2)
En este experimento se intentó extraer la geometría directamente infiriendo mapas de profundidad densos a partir de las imágenes 2D usando redes neuronales monoculares (DepthAnything V2).

**Resultados Empíricos y Problemas Detectados:**
* **Efecto "Globo":** La estimación de profundidad de DepthAnything V2 generaba nubes de puntos deformes (convexas, como un globo) debido a la naturaleza errática y puramente relativa de la red.
* **Inconsistencia de Escala (Scale Ambiguity):** Al intentar fusionar múltiples fotos secuenciales, los mapas de profundidad individuales no cuadraban geométricamente entre sí. Se producían solapamientos extraños y duplicación de objetos dinámicos (por ejemplo, un mismo auto aparecía repetido o desfasado).
* El tiempo de matching o los falsos positivos *no* fueron el limitante aquí, sino la imposibilidad de alinear la profundidad relativa.

**Trabajo Futuro Propuesto (Solución Teórica):**
Para viabilizar este enfoque, sería necesario realizar un trabajo de corrección de escala adaptativa: generar primero una nube de puntos *sparse* (rala) muy rápida mediante fotogrametría clásica, y usar esos puntos reales para anclar y corregir la escala del mapa de densidad de cada imagen. Adicionalmente, se requeriría el uso de segmentación semántica para purgar objetos dinámicos antes de fusionarlos con imágenes adyacentes.

---

## 2. Enfoque B: Fotogrametría Multi-Vista Pura (SuperPoint + LightGlue)
Para resolver la deformación monocular, este segundo enfoque (desarrollado recientemente) trata a GSV puramente como un set de cámaras RGB, utilizando extracción de características profundas para realizar triangulación matemática estricta.

**Descripción Metodológica:**
El pipeline extrae de forma autónoma una cuadra continua de panoramas (mediante BFS). Para evitar artefactos dinámicos que arruinen la paralaje, se implementó una interfaz en OpenCV (`draw_mask.py`) que permite trazar una máscara poligonal interactiva directamente sobre la proyección equirectangular. Esto oculta el auto de Google antes de dividir la imagen en perspectivas pinhole. Posteriormente, las imágenes enmascaradas se envían a un clúster (Khipu) para emparejamiento exhaustivo ("todos contra todos").

**Ventajas:**
1. **Rigor Geométrico:** Deriva la estructura 3D mediante trigonometría multi-vista, eliminando el "efecto globo" de las redes monoculares.
2. **Eliminación de Artefactos Estáticos:** El enmascaramiento pre-proyección evita que la IA intente triangular el vehículo o las costuras de la cámara.
