# Paso 1: Adquisición y orientación de panoramas Street View

Este experimento implementa únicamente el Paso 1 del baseline de reconstrucción
urbana: localizar panoramas de Google Street View a partir de coordenadas GPS,
descargar sus imágenes equirectangulares y guardar la metadata necesaria para
orientarlas posteriormente respecto al norte y al catastro de Barranco.

## Librería utilizada

Se reutiliza la librería `streetlevel`, que ya se emplea en los experimentos
anteriores del repositorio:

```python
import streetlevel.streetview as sv
```

El flujo utilizado es:

1. `find_panorama(lat, lon)` para encontrar el panorama cercano.
2. `find_panorama_by_id(id)` para obtener la metadata completa.
3. `get_panorama(pano, zoom=2)` para descargar la imagen 360 equirectangular.

## Ejecución

El Makefile de `investigation/` ya apunta explícitamente al entorno compartido
`/home/cesar/Escritorio/UTEC/PFC1_Lima/venv310/bin/python` y elimina
`WAYLAND_DISPLAY`, igual que los demás experimentos visuales del repositorio.

Desde `investigation/` se puede ejecutar mediante el Makefile:

```bash
make run-gsv-step1
```

Los parámetros por defecto se pueden cambiar sin editar el Makefile:

```bash
make run-gsv-step1 \
  GSV_STEP1_LAT=-12.137248 \
  GSV_STEP1_LON=-77.020423 \
  GSV_STEP1_COUNT=20 \
  GSV_STEP1_OUTPUT=proy_geom/steps/step1_acquisition/data/barranco_sample
```

También se puede usar la ruta existente del repositorio:

```bash
make run-gsv-step1-route
```

Para validar visualmente la orientación, después de descargar el dataset se
puede abrir el visor:

```bash
make view-gsv-north
```

El visor muestra tres ventanas:

- `Recorrido mirando al Norte`: una vista rectilínea que siempre apunta al
  norte, aunque cambie el panorama.
- `Equirectangular y orientacion`: la panorámica original, con una línea verde
  en el norte calculado y una línea roja en el centro horizontal original.
- `Mapa GPS del recorrido`: las posiciones GPS numeradas en el orden de
  adquisición; el panorama actual aparece en rojo.

Controles: `N` o flecha derecha para avanzar, `B` o flecha izquierda para
retroceder y `Q` o `Esc` para salir.

La ejecución directa equivalente, desde `investigation/`, es:

```bash
/home/cesar/Escritorio/UTEC/PFC1_Lima/venv310/bin/python \
  proy_geom/steps/step1_acquisition/run.py \
  --route-json ../custom_route.json \
  --output proy_geom/steps/step1_acquisition/data/custom_route
```

La entrada ejecutable actual del paso es `run.py`; el código reutilizable vive
en `../../src/gsv_acquisition/acquisition.py` respecto a esta carpeta.

El script genera:

```text
data/<dataset>/
├── panoramas/
│   ├── 000_<pano_id>.jpg
│   └── ...
└── metadata.json
```

## Convención de orientación

La metadata de `streetlevel` se conserva en su forma original (`heading_raw`) y
se normaliza a grados (`heading_deg`). En los resultados existentes del proyecto
los valores de `heading` están expresados en radianes, por lo que el experimento
detecta y convierte automáticamente valores dentro de `[-2π, 2π]`.

Se adopta inicialmente esta convención:

- el centro horizontal de la equirectangular representa el heading de la
  panorámica;
- el yaw aumenta hacia la derecha de la imagen;
- el norte se ubica en:

```text
north_pixel_x = width * (0.5 - heading_deg / 360)
```

Esta fórmula fue validada visualmente con el visor de recorrido antes de
utilizarla para proyectar lotes. El script guarda también
`north_pixel_x` y `north_fraction` para que esa validación sea reproducible.

## Alcance

Este experimento no descarga lotes, no segmenta con SAM, no proyecta fachadas y
no ejecuta SAM3D Objects. Su salida es exclusivamente un dataset reproducible de
panoramas, posiciones y orientación. Los pasos geométricos se construirán sobre
esta salida en experimentos posteriores.
