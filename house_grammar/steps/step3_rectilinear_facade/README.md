# Paso 3 — Perspectiva rectilínea frontal

Desde `investigation/`: `make run-gsv-step3`.
Consume las cuatro panorámicas locales del lote OBJECTID 1134979 seleccionadas
previamente. No consulta la red. Para otro conjunto, pasar
`GSV_PROJECTION_MANIFEST=ruta/projection_metadata.json`; debe contener `cameras`
con `pano_id`, `raw_image` relativo al manifiesto, `relative_yaw_deg` y
`target_bearing_deg`.

El centro apunta al bearing del punto medio de la arista elegida. Pitch=0,
FOV horizontal=90°, resolución=1200x900. Ajustables mediante `GSV_RECT_FOV`,
`GSV_RECT_WIDTH`, `GSV_RECT_HEIGHT`. Es una cámara perspectiva orientada a la
fachada: no elimina la perspectiva oblicua ni rectifica el plano del muro.

`outputs/` contiene imágenes PNG limpias, `comparison.jpg` y un manifiesto con
intrínsecos K, transformación de ejes, yaw, pitch, FOV, fuente y fecha. Las
ejecuciones reemplazan los archivos del mismo nombre; usar `run.py --output`
para conservar experimentos distintos.

El panorama se asume verticalmente alineado, siguiendo la validación del
Paso 1. Pitch/roll del proveedor no se aplican sin validar su convención.
La visibilidad del Paso 2 es una aproximación catastral 2D, no una garantía
de ausencia de árboles, vehículos u otras oclusiones reales.
