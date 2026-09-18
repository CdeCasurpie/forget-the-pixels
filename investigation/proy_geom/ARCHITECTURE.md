# Arquitectura de reconstrucción procedural

## Principio de diseño

`steps/` contiene protocolos reproducibles, CLI, gráficas y evidencias.
`src/` contiene lógica reusable sin argumentos de terminal ni decisiones de
ruta de salida. Los algoritmos reciben contratos de `domain/` y retornan datos
tipados o estructuras serializables. Esto permite reemplazar Street View por
fotos propias, añadir satélite o cambiar el generador procedural sin rehacer
la geometría calibrada.

## Flujo estable

```text
catastro + panoramas + poses
        │
        ▼
datasets/reconstruction_package
        │ ReconstructionInput
        ▼
camera_selection + geometry_projection
        │ vistas, bearings, reproyecciones
        ▼
facade_observations
        │ RoofObservation / recortes rectificados futuros
        ▼
structural_estimation
        │ HeightEstimate
        ▼
procedural_modeling/specification
        │ BuildingSpecification
        ▼
procedural_modeling/grammar          [implementado: ensamblaje paramétrico]
        │ MeshData
        ▼
exporters                           [OBJ/MTL y GLB implementados]
texturing                           [atlas fotográfico pendiente]
```

## Contratos

`ReconstructionInput` representa el material que llega a la futura función de
reconstrucción: lote, vistas 360, pose de cada vista, alineación y, más tarde,
una observación satelital opcional. Las imágenes se referencian por ruta; no se
duplican en cada experimento.

`HeightEstimate` conserva dos resultados distintos. `continuous_height_m` es
la estimación geométrica multivista. `regularized_height_m` es la altura usada
por la gramática. Para el caso actual, 33.62 m se regulariza como 12 pisos de
2.80 m, dando 33.60 m. La regularización no sobrescribe la medición continua.

`BuildingSpecification` es el único input de la gramática. Incluye
huella, altura, pisos, aristas de fachada, tejado y metadata. La gramática no
debe leer panoramas, shapefiles, JSON de Street View ni imágenes satelitales.

`MeshData` es independiente de Blender, Trimesh u otro exportador. Guarda
vértices, caras, UV opcionales, materiales y grupos semánticos; `exporters/` convierte a
GLB, OBJ u otros formatos.

## Módulos actuales

| Módulo | Estado | Responsabilidad |
| --- | --- | --- |
| `domain` | listo | contratos tipados del pipeline |
| `datasets` | listo | paquete versionado por lote y vistas |
| `gsv_acquisition` | listo | adquisición de panoramas y metadata |
| `cadastral_geometry` | listo | CRS, aristas y bearings |
| `camera_selection` | listo | visibilidad 2D y ranking de cámaras |
| `geometry_projection` | listo | rectilínea, franja angular y reproyección de prismas |
| `facade_observations` | listo | límite cielo/fachada y futuras observaciones 2D |
| `structural_estimation` | listo | alineación, altura multivista y pisos |
| `procedural_modeling/specification` | listo | puente entre evidencia y gramática |
| `procedural_modeling/layout` | listo | hipótesis reproducible a partir de frentes explícitos |
| `procedural_modeling/grammar` | listo | vanos, balcones, cercos selectivos, cubiertas y detalles |
| `procedural_modeling/mesh_builder` | listo | sólidos recortados y triangulación restringida con patios |
| `procedural_modeling/validation` | listo | geometría, materiales y contención de caras/aristas |
| `texturing` | contrato listo | elección de vistas, rectificación, UV y atlas |
| `exporters` | listo | GLB Y-up y OBJ/MTL Z-up |
| `pipeline` | contrato listo | API pública de reconstrucción |

## Regla de dependencias

```text
domain ← datasets / geometry / observations / estimation
domain ← procedural_modeling ← texturing / exporters ← pipeline
```

Los módulos de dominio no importan OpenCV, GeoPandas, Matplotlib, Street View
ni una librería de exportación. Matplotlib se permite solamente en `steps/`.
La función futura será:

```python
reconstruct_building(input: ReconstructionInput, config: ReconstructionConfig) -> ReconstructionResult
```

La gramática ya funciona de forma independiente. La integración automática
foto → metadata de fachada → especificación detallada sigue pendiente; no se
debe confundir una hipótesis procedural con una observación visual.

## Gramática detallada (new-proposal)

API: `propose_building(parcel, front_edges=..., height_m=..., seed=...)` produce
una especificación editable; `generate_mesh(spec)` produce `MeshData`.
La altura obtenida en pasos 8–9 se conserva como entrada, y los detalles deben
marcarse como observados o supuestos. La semilla da variedad reproducible.

El contrato distingue parcela/huella construida, patios, frentes y cercos
seleccionados. La malla es un ensamblaje de componentes, no una unión booleana
global. Los ejemplos incluyen parámetros explícitos de demostración, no nuevas
mediciones. Las unidades, ejes, límites, parámetros y comandos reproducibles
están en [la documentación del paso 10](steps/step10_procedural_generation_test/README.md).
