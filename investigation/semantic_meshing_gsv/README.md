# Experimento: Extracción Geométrica mediante Mapas de Profundidad Nativos de Google Street View

**Directorio:** `semantic_meshing_gsv/`

## Descripción Metodológica
Este experimento evalúa la viabilidad de utilizar los datos espaciales pre-calculados (Depth Maps) incrustados en los metadatos de Google Street View (GSV) para la reconstrucción urbana, prescindiendo por completo de algoritmos de fotogrametría clásica (Structure-from-Motion). 

El pipeline desarrollado realiza un recorrido sobre el grafo de vecindad de GSV mediante búsqueda en amplitud (BFS). Para cada panorama equirectangular, se decodifica el mapa de profundidad radial y se aplica trigonometría esférica para mapear las coordenadas de la imagen (yaw, pitch) hacia un espacio cartesiano (X, Y, Z). Posteriormente, las nubes de puntos individuales se trasladan a un sistema de coordenadas global local utilizando aproximaciones espaciales basadas en sus coordenadas GPS (latitud, longitud) y se rotan respecto a su orientación de brújula (heading) para ensamblar un bloque urbano continuo.

## Ventajas
1. **Eficiencia Computacional:** Evita los altos costos de procesamiento computacional inherentes a la extracción y emparejamiento de características fotogramétricas.
2. **Inmunidad al "Wide Baseline":** Al contar con la profundidad absoluta calculada por panorama, el algoritmo es indiferente a las amplias distancias espaciales (10-15 metros) entre capturas fotográficas que normalmente harían fracasar a algoritmos estándar de visión computacional.
3. **Escala Absoluta:** La geometría generada posee dimensiones métricas reales por defecto, sin requerir alineaciones escalares a posteriori.

## Desventajas
1. **Cuantización Extrema:** El formato de compresión de Google almacena la profundidad aproximando la geometría a una serie de planos esféricos discretos, lo que destruye la continuidad anatómica de las superficies arquitectónicas.
2. **Carencia de Optimización Global:** Al basar la fusión puramente en datos GPS en bruto (sin un paso de *Bundle Adjustment* o alineación *Iterative Closest Point*), el margen de error del sensor GPS provoca derivas espaciales severas, generando nubes superpuestas discordantes.

## Resultados Empíricos
El experimento determinó que **los datos espaciales nativos de Google no derivan de escáneres LiDAR continuos ni representan profundidad arquitectónica real**. Por el contrario, la geometría decodificada consiste en agrupaciones ("chunks") de planos aproximados y fuertemente cuantizados, diseñados exclusivamente para previsualizaciones rápidas de transición en la aplicación web de Google Maps. Como consecuencia, las estructuras geométricas resultantes no concuerdan con la volumetría de los edificios reales (produciendo artefactos circulares en el suelo y paredes disjuntas), concluyendo que **el uso de esta estructura de datos no produce un resultado útil para el mallado semántico urbano de alta fidelidad**.

*(Nota: Históricamente, se desarrolló un experimento paralelo utilizando modelos fundacionales de estimación monocular como `DepthAnything V2` en un intento por solucionar este problema. Sin embargo, dicho método también fracasó debido a la falta de concordancia multi-vista estricta entre imágenes independientes, aunque dicho vector de investigación permanece abierto para estudios futuros).*
