# Proyecto de Geometría Urbana (`proy_geom`)

Este directorio contiene el pipeline experimental para reconstrucción urbana
top-down a partir de Street View, catastro y posteriormente modelos de
segmentación/generación.

## Generación procedural detallada

El paso 10 genera OBJ/MTL y GLB, con fachadas, balcones, cercos selectivos y
azoteas mediante una gramática reproducible. Desde `investigation/` ejecutar
`make run-procedural-proposal`. Ver [parámetros, ejemplos y límites](steps/step10_procedural_generation_test/README.md).

La explicación completa del algoritmo actual, contratos, limitaciones,
materiales PBR y expansión de familias está en
[PROCEDURAL_GENERATION_PLAN.md](PROCEDURAL_GENERATION_PLAN.md).

La composición automática usa `detail_level="composed"`: acentos por grupos de
ventanas, marcos entre pisos, marquesinas y aleros. `detail_level="basic"` permite
comparar la geometría anterior. La guía de implementación de texturas para Gemini
está en [GEMINI_PBR_GUIDE.md](GEMINI_PBR_GUIDE.md).

## Organización

La rama procedural posterior al Paso 5 valida reproyección, construye una
entrada multivista por lote, observa el límite techo/cielo y ajusta altura.
La arquitectura reutilizable está documentada en
[`ARCHITECTURE.md`](ARCHITECTURE.md). `steps/` guarda evidencia y CLI; `src/`
contiene los módulos canónicos.

Actualización: los pasos 3 y 4 se ejecutan offline con las panorámicas locales.
`make run-gsv-step3` genera perspectivas horizontales y `make run-gsv-step4`
genera elevaciones. `make test-gsv-projection` valida geometría sintética.
El experimento cilíndrico anterior se ejecuta ahora con `make run-gsv-step5`;
su carpeta es `steps/step5_cylindrical_facade` y sus variables son
`GSV_STEP5_*`. Las panorámicas existentes se trasladaron con el experimento.

### Módulos del pipeline

| Componente | Estado y responsabilidad |
| --- | --- |
| `src/gsv_acquisition` | Existente: adquisición de panoramas y metadata |
| `src/geometry_projection/rectilinear.py` | Reutilizable: cámara pinhole, K, yaw/pitch, dirección 3D y muestreo |
| `src/geometry_projection/cylindrical.py` | Existente: franja angular completa; matemáticamente recorte equirectangular, no cilindro tangente |
| `src/geometry_projection/experiment.py` | Adaptador CLI compartido: entrada/salida y evidencias de los pasos 3 y 4 |
| `src/cadastral_geometry` | CRS, localización de lote, aristas y bearings de cuadrícula |
| `src/camera_selection` | Visibilidad 2D, autooclusión y selección de las K cámaras visibles más cercanas |
| `src/domain` | Contratos tipados de lote, pose, observación, altura, especificación y malla |
| `src/datasets` | Paquete versionado de entrada por lote y vistas seleccionadas |
| `src/facade_observations` | Evidencia 2D de fachada; actualmente límite cielo/techo |
| `src/structural_estimation` | Alineación, ajuste de altura y regularización arquitectónica de pisos |
| `src/procedural_modeling` | Gramática, composición, triangulación y validación de mallas |
| `src/exporters` | OBJ/MTL y GLB con materiales y grupos semánticos |
| `src/texturing`, `src/pipeline` | Contratos preparados para texturas fotográficas y API pública |

Los pasos 2 y 5 comparten ahora las mismas funciones de visibilidad. El Paso 2
conserva su ranking experimental por proximidad; el Paso 5 exige además una
arista visible. La proyección no depende de
Street View, shapefiles, segmentación ni selección de cámaras.

Convención: yaw relativo al centro equirectangular, positivo a la derecha;
pitch positivo hacia arriba; focal en píxeles con píxeles cuadrados, centro
óptico `((W-1)/2, (H-1)/2)`. La matriz guardada transforma ejes de cámara
OpenCV (derecha, abajo, adelante) al marco del panorama (derecha, arriba,
adelante). Por el cambio de lateralidad no es una rotación SO(3); no debe
usarse directamente como pose de un motor 3D sin convertir sus ejes.
El yaw heredado del Paso 2 usa norte de cuadrícula UTM; la convergencia con
norte geográfico y la orientación pitch/roll del proveedor siguen pendientes
de calibración para ajuste métrico preciso.

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
en los siguientes pasos del pipeline. Los prototipos `multiview_input` y
`height_estimation` permanecen como adaptadores de compatibilidad; el código
nuevo usa `datasets`, `facade_observations` y `structural_estimation`.

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
