# 💡 Conceptos Core e Ideas de la Tesis

**Título de Tesis:** Olvida los píxeles: Modelado estructural a escala metropolitana guiado por grafos de poses y abstracción geométrica.

## El Problema: El Enfoque "Bottom-Up" Tradicional
La fotogrametría clásica (SfM y MVS usando COLMAP o OpenMVS) intenta reconstruir la geometría estimando la profundidad de cada píxel de forma independiente (dense point clouds).
**Problemas:**
- Extremo consumo de memoria RAM y tiempo de cómputo (e.g. 93GB de mapas de profundidad generados en Khipu).
- El ruido de las cámaras y la falta de textura (paredes blancas, ventanas reflectantes) generan mallas "derretidas" (melted wax effect) o nubes con agujeros.
- No hay noción estructural: la malla no sabe qué es una pared, qué es un techo o qué es el suelo.

## La Solución: El Enfoque "Top-Down" (Abstracción Geométrica)
En lugar de inferir la geometría a partir de los píxeles, **usamos conocimiento previo estructural** (Prior) para restringir el modelo. 
Los edificios no son masas amorfas de puntos, son cajas y prismas compuestos de planos geométricos perfectos.

### 1. El Rol del Catastro (Lotes Oficiales)
- Descubrimiento crucial: Existen mapas de polígonos 2D (lotes oficiales) de distritos como Barranco.
- Estos polígonos sirven como la base plana perfecta (LOD1 CityGML). Si extruimos estos lotes en el eje Z (usando la altura promedio extraída de una nube de puntos ligera), obtenemos prismas perfectos y paredes "watertight".

### 2. El Rol de las Fotos (Grafo de Poses)
- Renunciamos al "Multi-View Stereo" denso de los píxeles.
- Usamos COLMAP o Google Street View **exclusivamente para obtener las poses de las cámaras** (Sparse Reconstruction: `images.bin`, `cameras.bin`).
- Una vez que sabemos exactamente dónde está la cámara (Dron o GSV) respecto al prisma catastral 3D, **proyectamos** la imagen 2D sobre la cara plana del prisma (Texture Mapping).
- **El resultado:** Hiperrealismo (texturas puras sin deformar) con geometría ultra-ligera (wireframes matemáticos).

### Relación con los Experimentos
- Para entender los fallos del enfoque Bottom-Up, revisa [[03_experiments_khipu_colmap]].
- Para ver nuestro progreso extrayendo planos a nivel de calle, revisa [[02_experiments_street_view]].
- Para el roadmap de cómo fusionar el catastro y el Dron, revisa [[04_future_roadmap]].
