# Semantic Meshing (Multi-View Sparse)

Este experimento contiene la mejor iteración hasta la fecha para la reconstrucción de mallas (Meshing) a partir de datos de fotogrametría.

## ¿Qué hace diferente a este enfoque?
En lugar de depender de la densificación de COLMAP (que suele generar ruido, "derretimiento" de estructuras y nubes pesadas), este algoritmo opera directamente sobre la **Nube de Puntos Sparse** (`.bin`) y la red de visibilidad extraída de forma nativa con `pycolmap`. 

El proceso funciona así:
1. **Carga Sparse Directa**: Se leen los puntos 3D geométricamente exactos (Tie Points) y la relación de qué cámara ve qué puntos directamente desde el `Reconstruction` de COLMAP.
2. **Proyección 2D Pinhole**: Para una cámara específica, se proyectan los puntos 3D visibles hacia su plano de imagen 2D.
3. **Triangulación de Delaunay**: Se conectan los puntos proyectados en 2D de forma ultrarrápida.
4. **Filtros Geométricos Heurísticos**: 
   - *Edge Length Filter*: Descarta conexiones entre puntos que están demasiado lejos físicamente.
   - *Z-Stretch Filter*: Detecta y elimina los temidos "triángulos rotos" que se forman al conectar fondo y primer plano (midiendo la varianza de profundidad Z relativa a la cámara).
5. **Mapeo UV Multi-Textura**: Extrae coordenadas UV precisas y mapea el triángulo generado obligatoriamente a la textura de la foto original que lo capturó.
6. **Acumulación (Multi-View)**: Permite recorrer la trayectoria del dron y "proyectar telas" que se acumulan en un grafo global continuo.

## Controles del Visor
- `N` / `B` : Avanzar / Retroceder por las cámaras del Dron.
- `F`       : Desbloquear la cámara y pasar a Órbita Libre.
- `C`       : Centrar la cámara (Raycast) en el punto donde apunte tu mouse.
- `W` / `S` : Caminar Hacia Adelante / Atrás (supera el límite de FOV de Open3D).
- `H`       : Mostrar u ocultar la Nube de Puntos Local.
- `I`       : Mostrar u ocultar la Imagen de Fondo (Image Plane).
- `G`       : Alternar vista entre la Nube de Puntos y la Malla Global Texturizada.
- `M`       : **[ACCIÓN MESH]** Extraer malla de la vista actual, filtrar, texturizar y fusionar a la Malla Global.

## Ejecución
Desde la raíz de `investigation/`, ejecuta:
```bash
make run-multiview
```
