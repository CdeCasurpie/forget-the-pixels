# 🗺️ Roadmap y Siguientes Pasos (El Camino al Gemelo Digital)

Nuestra meta es materializar el concepto de **"Olvida los Píxeles"** fusionando lo que aprendimos de la geometría (Street View/Catastro) con lo que aprendimos de las texturas y escalas (Khipu/COLMAP Dron).

## Paso 1: Fusión de Nube de Puntos + Lotes Catastrales
1. **Importar Lotes:** Cargar el Shapefile oficial de los lotes catastrales de Barranco (Polígonos 2D perfectos).
2. **Cruzar con la Nube de 80MB:** Superponer la nube generada en [[03_experiments_khipu_colmap]] sobre el mapa 2D.
3. **Extrusión Matemática:** Intersectar los puntos del dron que caen dentro del polígono catastral 2D y encontrar la Z máxima o promedio (altura del techo). Luego, extruir el polígono 2D desde Z=0 hasta la altura del techo, generando un bloque 3D (prismas LOD1 perfectos y sin agujeros).

## Paso 2: Proyección de Texturas (Hiperrealismo)
En lugar de depender de la malla deforme de COLMAP (Poisson mesher):
1. Importar el grafo de poses de las cámaras (`cameras.bin` y `images.bin`) generados por COLMAP.
2. Usar álgebra de rayos (Camera Raycasting) para proyectar cada píxel de las fotos originales del dron directamente sobre las caras planas de nuestro modelo extruido de lotes.
3. Esto generará fachadas que se ven perfectamente planas, sin el molesto efecto de cera derretida de la fotogrametría bottom-up.

## Paso 3: Optimización con 3D Gaussian Splatting (3DGS)
Para los detalles que los lotes catastrales no tienen (e.g., postes de luz, árboles, balcones salientes):
1. Entrenar un modelo de **3D Gaussian Splatting** usando las imágenes del dron.
2. **Restricción de Prior Geométrico:** Modificar el código de 3DGS para que las gaussianas no puedan volar o "flotar" libremente en el cielo, sino que se inicialicen y se vean fuertemente atraídas a descansar sobre la superficie de nuestros bloques catastrales extruidos.
3. Esto reduce dramáticamente la memoria y los artifacts visuales, logrando calidad fotorrealista que pesa megabytes en lugar de gigabytes, ideal para escala metropolitana.

*Revisar la lógica conceptual detrás de esto en [[01_core_concepts_and_ideas]] y las lecciones aprendidas de la asunción planar en [[02_experiments_street_view]].*
