# 🚗 Experimentos: Google Street View y Profundidad

**Ubicación de los scripts:** `investigation/street_view/`

Esta serie de experimentos se enfocó en extraer estructura 3D a nivel de calle (Street View), ya que el dron captura bien los techos pero pierde resolución y ángulo en las fachadas a nivel de piso.

## 1. Problemas de Proyección Equirectangular y "Balloon Effect"
Usamos **Depth Anything V2** (IA Monocular) para estimar la profundidad de los panoramas 360° (equirectangulares).
- **El problema de las costuras (Seams):** Si cortábamos el 360 en fotos pinhole y calculábamos la profundidad, los bordes no coincidían, causando fracturas en la nube de puntos.
- **La solución (test_pano_consistent.py):** Calculamos la profundidad usando la red neuronal sobre **toda la imagen 360 global** y luego aplicamos el mapeo cilíndrico a perspectivas (`cv2.remap`). Esto eliminó los cortes.
- **El problema del Globo (Balloon Effect):** Comprobamos matemáticamente (`test_spherical_direct.py`) que las redes neuronales monoculares asumen una perspectiva plana. Si proyectas esa profundidad directamente en un plano esférico (360°), las paredes planas se abomban y curvan como un globo. Es necesario hacer el unprojection con coordenadas Pinhole estrictas (`geometry.py`).

## 2. Corrección Matemática del Tensor
- Descubrimos un bug donde las nubes de puntos "explotaban" (dividían por cero). El tensor puro (`result["depth"]` en crudo) de Depth Anything arrojaba valores negativos o fuera de escala en ciertas condiciones.
- **Solución:** Usar la imagen normalizada de PIL (0-255) y escalarla linealmente.

## 3. Asunción Planar (Abstracción)
- Script: `test_planar_assumption.py`.
- **Objetivo:** Forzar a que la ruidosa profundidad neuronal reconozca que está viendo una fachada plana.
- **Método:**
  1. Usar el algoritmo de **Superpíxeles de Felzenszwalb** sobre la imagen RGB para agrupar píxeles que pertenecen a una misma pared o textura.
  2. Aplicar **RANSAC (Open3D)** a la nube de puntos de ese superpíxel para calcular el mejor plano matemático infinito (ax + by + cz + d = 0).
  3. Proyectar los puntos ruidosos hacia el plano perfecto.
- **Conclusión:** Logramos aplanar las fachadas matemáticamente, eliminando el ruido de la IA. Esto valida el enfoque Top-Down descrito en [[01_core_concepts_and_ideas]].
