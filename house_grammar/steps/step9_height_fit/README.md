# Paso 9: ajuste multivista de altura

Desde investigation: `make run-gsv-step9` (ejecuta también el Paso 8).
Los scripts aceptan `--input` y `--output`; el Paso 8 acepta `--alignment`.
Para otro lote se necesita su propio paquete, cámaras y corrección compatible.

Modelo: y(H) = altura_imagen * (0.5 - atan2(H-altura_cámara, distancia)/pi).
Se ajusta H entre 1 y 150 m usando residuos escalados a un panorama de 1024
píxeles de alto. Se reportan mínimos cuadrados y un ajuste robusto soft-L1
(escala 3 px). Se requieren al menos dos observaciones utilizables.

`outputs/height_fit.json` contiene altura, residuos, RMSE, vistas usadas y
ajustes dejando una cámara fuera cada vez. Estos últimos miden sensibilidad,
no un intervalo estadístico de confianza. `comparison.png` reproyecta el
prisma: verde=malla, cruz roja=corte observado, punto cian=altura ajustada.
`building_specification.json` es la salida preparada para la futura gramática:
huella ya alineada, altura continua, 12 pisos de 2.80 m y altura procedural
33.60 m para el caso actual. No contiene todavía una malla ni texturas.

Resultado inspeccionado para 1134979: detecciones individuales aproximadamente
37.19, 37.74, 31.76 y 30.18 m; ajuste robusto 33.62 m, mínimos cuadrados
33.84 m. RMSE normalizado 8.57 px (17.13 px en las imágenes originales de
2048 px de alto). Las cuatro cruces caen visualmente sobre el borde del techo,
pero la extrusión no coincide exactamente en todas las vistas. El informe
marca `needs_geometric_review` por superar 5 px normalizados.

El lote catastral puede diferir de la huella de la torre, especialmente con
retiros; también influyen GPS, orientación y terreno. Una sola altura no
resuelve esas discrepancias. No se debe presentar 33.62 m como medida exacta.
La revisión siguiente debe contrastar huella/pose y una altura independiente.

Pruebas desde investigation:
`PYTHONPATH=proy_geom/src /home/cesar/Escritorio/UTEC/PFC1_Lima/venv310/bin/python -m unittest discover -s proy_geom/tests -p 'test_height_estimation.py'`
