# Extracción técnica del compositor theta-candidate

## Checkpoint previo

La regresión de `FacadeOverride` lateral verifica `has_program=True`,
`is_front=False` y generación de geometría. Validación antes de extraer:
75 tests relacionados y 34 subtests; suite completa: **294 passed,
127 subtests passed in 67.73s**. Los 21 fingerprints y sus θ resueltos
coinciden con los artefactos guardados. Checkpoint independiente creado.

## Dependencias y API

`modeling/theta.py` llama a
`modeling/facade_composition.py::compose_facade` tanto para paredes base
como para `FacadeZone`. El compositor recibe controles ya completados,
familia, longitud, niveles locales, altura, ground/top y `floor_indices`.
Devuelve `FacadeComposition`, una NamedTuple con `axes_m`, `openings`,
`projections` y `material_regions`.

La función extraída conserva el orden de operaciones y las reglas originales:
ejes/pitch, puertas, balcones, ediciones, validaciones locales y relief.
El resolver conserva defaults/validación del contrato, selección de programas,
transformación de charts y exposición. No se modificó la API JSON.

Dependencia unidireccional:

```
theta -> facade_composition -> facade_program (FAMILY_RULES, _relief)
                           -> domain / detail / numpy / shapely
```

No hay dependencia del compositor hacia el resolver. El compositor legacy
`compose_wall` y `modeling/composition.py::compose_facade` mantienen sus
responsabilidades anteriores; el nuevo entry point es canónico únicamente
para theta-candidate.

## Equivalencia

Se capturaron seis pares de hashes con la función `_composition` anterior a
la extracción: bytes de vértices/caras/materiales y JSON canónico del plan
resuelto. Cubren pared repeat, zona repeat, explicit, suppress, replace con
índice de piso 1 en una zona vertical y programa posterior. Se conservan en
`tests/fixtures/facade_composition_hashes.json`. Los tests existentes cubren
también programas laterales, orientación hacia calle y hashes de malla previos.

Después de extraer:
- Relacionados: **81 passed, 34 subtests passed in 10.96s**.
- Completa: **300 passed, 127 subtests passed in 63.61s**.
- **21/21 fingerprints idénticos**, 21/21 θ resueltos equivalentes.
- Se conservan los renders existentes: no se produjo ningún cambio visual.

## Extensión futura y deuda técnica

BayGroup podrá enriquecer la composición en este único punto, sin duplicar
lógica entre pared y zona. Los resultados explícitos permiten que el resolver
siga transformando y recortando entidades sin conocer cómo se organizan bays.
BayGroup, Motifs, CrownProfile y ArchitecturalOrder no están implementados.

Deuda existente: `_relief` es un helper privado compartido con el pipeline
legacy; la normalización de controles permanece en el resolver. La frontera
está documentada: el compositor consume controles completos. No se unificaron
los pipelines ni se alteraron las limitaciones de clipping de FacadeZone.
