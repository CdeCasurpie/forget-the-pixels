# Proyecto de Geometría Urbana (`proy_geom`)

Este directorio contiene el pipeline experimental para reconstrucción urbana
top-down a partir de Street View, catastro y posteriormente modelos de
segmentación/generación.

## Organización

```text
proy_geom/
├── steps/
│   └── step1_acquisition/
│       ├── data/                  # datasets producidos por el paso
│       ├── README.md              # protocolo y resultado del paso
│       ├── run.py                 # entrada ejecutable del paso
│       └── view_north.py           # visor de validación
├── src/
│   └── gsv_acquisition/
│       ├── __init__.py
│       └── acquisition.py          # módulo reutilizable de adquisición
└── requirements.txt
```

La regla del proyecto es mantener en `steps/` los experimentos reproducibles
y sus evidencias, mientras que `src/` contiene los módulos que se reutilizarán
en los siguientes pasos del pipeline.

## Paso 1 completado: adquisición Street View

El primer paso utiliza `streetlevel.streetview` para localizar panoramas a
partir de coordenadas GPS, recorrer vecinos o rutas explícitas, descargar
imágenes equirectangulares y guardar `pano_id`, coordenadas, fecha, heading,
pitch y roll. Los ángulos se normalizan a grados conservando también su valor
original, y se calcula la posición horizontal estimada del norte.

El entorno usado y validado es:

```text
/home/cesar/Escritorio/UTEC/PFC1_Lima/venv310/bin/python
Python 3.10.18
```

El Makefile elimina `WAYLAND_DISPLAY` para mantener compatibilidad con las
ventanas OpenCV del visor.

## Validación del norte

La orientación se confirmó visualmente mediante `view_north.py`. El visor
recorre los panoramas con `N`/flecha derecha y `B`/flecha izquierda, pero
reproyecta cada imagen mirando siempre al norte. También muestra la
equirectangular con el norte calculado, además del mapa GPS con el panorama
actual resaltado.

La validación confirmó que el norte se mantiene correctamente orientado.
También reveló que el orden BFS de vecinos puede producir saltos espaciales;
ese problema pertenece al ordenamiento de la ruta y no a la orientación.

## Ejecución

Desde `investigation/`:

```bash
make run-gsv-step1
make view-gsv-north
```

El Paso 1 no ejecuta todavía SAM, SAM3D Objects, proyección hacia lotes ni
generación procedural. Es la base geográfica y fotométrica para esos módulos.

