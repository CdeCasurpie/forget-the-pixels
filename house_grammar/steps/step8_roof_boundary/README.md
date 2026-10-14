# Paso 8: límite aparente cielo–edificio

Desde investigation: `make run-gsv-step8`.

Lee el paquete del Paso 7 y la corrección del Paso 6. Traslada el polígono,
busca su punto de frontera más cercano a cada cámara y calcula el azimut
geodésico. Extrae 9 columnas del panorama original (con wrap horizontal),
desde cenit hasta la base proyectada. Se asumen panoramas nivelados y terreno
plano; no se aplican automáticamente pitch/roll del proveedor.

La mediana por fila en Lab se divide en dos intervalos contiguos minimizando
la suma de errores cuadráticos internos. Pesos Lab: 0.2, 1, 1; mínimo 8 filas
por segmento. Se redujo el peso de luminosidad tras observar que la cuarta
vista elegía el revestimiento negro inferior en vez del techo. Esta elección
se ajustó en este edificio y aún requiere validación con otros edificios.

`outputs/observations.json` guarda coordenadas originales, corte, intervalos
binarios, pose, punto objetivo, alineación y parámetros. `comparison.png`
muestra las tiras reales y los cortes para inspección. El score es separación
de colores, no probabilidad semántica. Árboles, sombras y fachadas azules pueden
engañar al detector. La visibilidad se hereda de las vistas proporcionadas;
este paso no certifica ausencia de oclusión.

La altura individual es un diagnóstico, calculado con
H = altura_cámara + distancia_horizontal * tan(elevación_del_corte).
No se utiliza la altura manual de 41 m para detectar el techo ni optimizar.
