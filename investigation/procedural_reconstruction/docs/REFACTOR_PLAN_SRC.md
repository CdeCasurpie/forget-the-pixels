# Propuesta de Refactorización de `src/`

Actualmente la carpeta `src/` contiene 15 submódulos al mismo nivel, mezclando la lógica de Visión Computacional (ML/CV) con la lógica de Generación Procedural (Geometría). El objetivo es agrupar esto para que funcione como una **librería local elegante**, sin romper ni reescribir la lógica interna.

## Estructura Actual
`cadastral_geometry`, `camera_selection`, `datasets`, `domain`, `exporters`, `facade_observations`, `facade_segmentation`, `geometry_projection`, `gsv_acquisition`, `height_estimation`, `multiview_input`, `pipeline`, `procedural_modeling`, `structural_estimation`, `texturing`.

## Estructura Propuesta

Para usar esto como una API limpia, dividiremos todo en dos grandes paquetes (`vision` y `modeling`), con un punto de entrada principal (`api` o `pipeline`):

```text
src/
├── vision/                 # Todo lo relacionado a extraer datos de Google Street View
│   ├── acquisition/        # (Agrupa: gsv_acquisition, datasets)
│   ├── cameras/            # (Agrupa: camera_selection, multiview_input)
│   ├── projection/         # (Agrupa: geometry_projection)
│   ├── segmentation/       # (Agrupa: facade_segmentation, facade_observations)
│   └── estimation/         # (Agrupa: height_estimation, structural_estimation)
│
├── modeling/               # Todo lo relacionado a síntesis 3D procedural
│   ├── domain/             # (Agrupa: domain - esquemas Pydantic/Dataclasses)
│   ├── procedural/         # (Agrupa: procedural_modeling, cadastral_geometry)
│   ├── texturing/          # (Agrupa: texturing - PBR y catálogos)
│   └── exporters/          # (Agrupa: exporters - OBJ/GLB)
│
└── pipeline/               # (Se mantiene como punto de entrada de la librería / orquestación)
```

## Tareas de Refactorización (Modificación de Imports)
Al mover estas carpetas, todas las declaraciones de `import` a lo largo del proyecto y los tests (`tests/`) deberán ser actualizadas.
Ejemplo:
- `from domain.architecture import ...` pasará a ser `from modeling.domain.architecture import ...`
- `from procedural_modeling.grammar import ...` pasará a ser `from modeling.procedural.grammar import ...`

## El Script Generador (Ejemplo de API)
Una vez refactorizado, crearemos un script en la raíz `generate_batch.py` que importe elegantemente desde la nueva estructura:
```python
import sys
sys.path.insert(0, 'src')
from modeling.domain.architecture import BuildingProgram
from pipeline.contracts import reconstruct_building # o la función orquestadora

# Bucle para generar 5 casas con parámetros aleatorios...
```
