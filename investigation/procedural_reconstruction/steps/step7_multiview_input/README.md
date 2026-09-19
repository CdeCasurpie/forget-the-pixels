# Paso 7 — Entrada multivista por lote

Este paso crea el contrato de datos que consumirán la detección de techo, la
optimización de altura y la generación procedural. No modifica el shapefile ni
copia imágenes: el JSON referencia las imágenes 360 y cilíndricas producidas
por el Paso 5.

El paquete contiene:

- el polígono del lote en `EPSG:32718` y WGS84;
- centroide y coordenada objetivo;
- parámetros globales de proyección;
- una vista por cámara con `pano_id`, rutas, posición, heading, pitch, roll,
  fecha, yaw relativo, bearing y distancia al lote.

Ejecutar desde `investigation/`:

```bash
make run-gsv-step7
```

Salida:

`proy_geom/steps/step7_multiview_input/outputs/lot_1134979.json`

El archivo usa `schema_version=2` y representa `ReconstructionInput`: lote,
alineación inicial, proyección y vistas con pose. Es autocontenido salvo por
las rutas absolutas de imagen. Eso evita duplicar varios cientos de MB y
permite comprobar que apunta al dataset exacto usado en el experimento.
