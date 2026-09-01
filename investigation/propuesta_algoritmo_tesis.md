# Propuesta de Algoritmo de Tesis: Reconstrucción 3D Estructural mediante Triangulación 2.5D Restringida por Segmentación

## Motivación
Los métodos tradicionales de reconstrucción de superficies (como Poisson Surface Reconstruction) asumen superficies continuas y cerradas, lo que genera artefactos ("ballooning effect" o "plastilina") en escenarios urbanos abiertos o en presencia de geometrías delgadas. Por otro lado, la triangulación 3D global (Delaunay 3D) tiende a conectar erróneamente puntos que pertenecen a distintos objetos en el espacio debido a la escasez espacial.

## Solución Propuesta
El objetivo es aprovechar la coherencia estructural y semántica presente en las imágenes 2D (donde los bordes de los objetos son perfectos) para guiar y restringir la triangulación en el espacio 3D, evitando conectar puntos que pertenecen a superficies o clases distintas.

## Flujo del Algoritmo

1. **Iteración por Vistas (Cámaras):**
   El algoritmo opera de manera iterativa, recorriendo el conjunto de datos cámara por cámara (imagen por imagen).

2. **Segmentación 2D:**
   Para cada imagen procesada, se aplica un algoritmo de segmentación (ya sea por agrupamiento de color o por segmentación semántica) para dividir los píxeles en múltiples regiones/máscaras cerradas.

3. **Clasificación de la Nube de Puntos:**
   Se toman los puntos 3D visibles por esa cámara específica, se proyectan sobre el plano 2D de la imagen y se agrupan (clasifican) según la región segmentada o el color dentro del cual cayeron.

4. **Triangulación 2D Restringida (Per-Segment):**
   A cada grupo de puntos (aislado por su región de color/segmento) se le aplica una triangulación Delaunay 2D en el espacio de la imagen. La clave fundamental aquí es la restricción: **no se triangulan puntos que pertenecen a distintos segmentos**. Esto preserva los bordes duros de los objetos y evita fundir el fondo con el primer plano.

5. **Retroproyección a Malla 3D:**
   Por cada triángulo 2D generado en el paso anterior, se toman las coordenadas 3D originales de sus 3 vértices para generar un triángulo poligonal en el espacio tridimensional.

6. **Fusión y Limpieza Global:**
   Dado que este proceso se repite para múltiples cámaras superpuestas, se generarán triángulos redundantes o solapados en el espacio 3D. El paso final consiste en fusionar la malla global eliminando la duplicación geométrica de los triángulos para obtener un modelo estructural unificado y ligero.
