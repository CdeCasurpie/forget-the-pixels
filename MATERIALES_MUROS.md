# Materiales de muros: acabado sin geometría duplicada

## Regla de autoría

**Material y forma son decisiones independientes.** Pintar una región cambia el
material de la superficie existente: no añade panel, espesor, retiro ni volumen.
Los límites de material dividen triángulos, conservando huecos, silueta y espesor.
También se aplica el acabado a los cantos y derrames del muro; no se crean caras
internas en los límites de pintura. La textura conserva su escala métrica.

Para describir una casa:

1. Define masas, mordidas y planos de fachada con `massing` y zonas de fachada.
2. Elige `side_material` para los laterales/fondo: `plaster` (tarrajeado),
   `brick` (ladrillo visto), `concrete` (concreto visto) o un material propio.
   Si se omite, se usa `plaster`; es un default, no una inferencia de la foto.
3. Elige `wall_material` dentro de los controles de fachada para su acabado
   uniforme. Funciona en `facade`, overrides, `component.facade`, `faces[].controls`
   y `zones[].controls`. Sin selección local, los frentes usan
   `theta.facade.wall_material` o `plaster`; los demás usan `side_material`.
4. Añade `material_regions` solo si hay cambios de material/color en ese plano.
5. Usa `materials` para nombrar los colores sin alterar accidentalmente otros
   elementos que compartan `accent`, `wood`, etc.

El estilo arquitectónico o la familia no eligen el material de planta baja en
el compositor theta. Tanto `null` como `[]` en `material_regions` significan
que no se añaden regiones de pintura de familia. Los zócalos solicitados por
`trim` siguen siendo explícitos y tienen prioridad en su zona.

## Plantilla completa: dos colores, laterales de ladrillo

Ejemplo independiente de 10 × 12 m, con un muro de 6 m; las regiones usan
coordenadas locales del plano, no coordenadas mundiales ni porcentajes.
No describe las aberturas de una casa real: añádelas en `openings`.

```json
{
  "context": {
    "parcel": [[0, 0], [10, 0], [10, 12], [0, 12]],
    "fronts": [0]
  },
  "theta": {
    "height_m": 6,
    "floors": 2,
    "side_material": "brick",
    "materials": [
      {"slot": "blanco_muro", "template": "plaster", "color": [0.92, 0.91, 0.88]},
      {"slot": "ocre_muro", "template": "plaster", "color": [0.80, 0.55, 0.12]}
    ],
    "facade": {
      "mode": "explicit",
      "wall_material": "ocre_muro",
      "openings": [],
      "projections": [],
      "material_regions": [
        {"u_m": 0, "v_m": 0, "width_m": 10, "height_m": 3, "material_slot": "blanco_muro"}
      ]
    },
    "trim": {"cornice": {"enabled": false}, "plinth": {"enabled": false}},
    "roof": {"kind": "flat", "parapet_m": 0, "props": []},
    "site": {"fence": "none", "runs": [], "garden": false}
  }
}
```

Para tarrajear también los laterales, cambia únicamente
`"side_material": "blanco_muro"`. Para todo un plano de concreto, establece
`"wall_material": "concrete"` en sus controles. No hace falta una región del
tamaño del muro ni una proyección `panel`.

## Vocabulario y prioridad

| Campo | Significado |
|---|---|
| `side_material` | Material base de los planos no frontales, salvo selección local. |
| `wall_material` | Material base de la fachada/plano seleccionado; `null` usa el default correspondiente. |
| `material_regions` | Lista ordenada de rectángulos de acabado, sin espesor. |
| `u_m`, `v_m` | Esquina inferior inicial en el sistema local de la fachada. |
| `width_m`, `height_m` | Dimensiones positivas; deben caber en el dominio/silueta. |
| `material_slot` | Nombre de un material existente o declarado en `theta.materials`. |
| `source`, `score` | Metadatos opcionales de la región; no alteran su geometría. |
| `materials[].slot` | Nombre único nuevo o nombre existente a reemplazar. |
| `materials[].template` | Material del catálogo base del que copiar textura y propiedades PBR. No referencia otro alias. |
| `materials[].color` | RGB normalizado de 0 a 1; si se omite, conserva el tinte de la plantilla. |

Prioridad: **material base → regiones en orden (la última gana) → acabado de
zócalo `trim`, si se solicitó**. Las ventanas/puertas se recortan antes de pintar:
una región no tapa sus huecos. En zonas de fachada las coordenadas de entrada
son locales a la zona; el resolver las traslada al plano padre.

`plaster`/`accent` usan estuco; `brick` usa aparejo de ladrillo;
`concrete` usa concreto. La textura física del catálogo PBR se aplica al exportar
GLB; una previsualización de colores planos no muestra su relieve/normal map.
Los materiales propios reutilizan esas texturas, sin inventar archivos de imagen.

## Geometría explícita

- Cambiar de `brick` a `plaster` ya no crea/quita pórticos de concreto ni cambia
  la profundidad del muro. Un aparejo es acabado; una columna real es geometría.
- El número de pisos ya no causa un retiro automático de 12 cm en planta baja.
  Usa `FacadeZone.offset_m` o regiones de masa para los cambios de plano.
- Una banda de concreto enrasada puede ser una región de material. Si realmente
  sobresale, utiliza los controles geométricos correspondientes (trim, miembros,
  composición), no un espesor oculto de pintura.
- `ground_floor_material` de la API histórica se normaliza como región en el
  mismo motor; no conserva un constructor de coatings alternativo.

## Implementación y mantenimiento

- `house_grammar/src/domain/theta.py`: controles y serialización de theta.
- `house_grammar/src/domain/models.py`: `FacadeMaterialRegion` y fachada resuelta.
- `house_grammar/src/modeling/theta.py`: selección frontales/laterales, validación,
  materiales propios y conexión con trim.
- `house_grammar/src/modeling/facade_composition.py`: regiones explícitas en theta;
  no copiar bandas cromáticas automáticas de las familias históricas.
- `house_grammar/src/modeling/grammar.py`: una única superficie de muro.
- `house_grammar/src/modeling/wall_finish.py`: partición de triángulos y materiales.
- `house_grammar/src/modeling/mesh_builder.py`: aplicación tras recorte geométrico,
  manteniendo identidad del componente, índices y UV por esquina.
- `house_grammar/src/modeling/facade_depth.py`: continuidad en retornos de zonas.
- `house_grammar/src/modeling/materials.py`: propiedades PBR base.

**Si cambia este sistema, actualizar también esta guía**, la guía theta y sus
referencias de campos. No reintroducir `material_coating`, superficies paralelas
separadas por epsilon o cambios de masa disparados por un material.

Pruebas principales:

```bash
PYTHONPATH=house_grammar/src python3 -m pytest \
  house_grammar/tests/test_material_boundaries.py \
  house_grammar/tests/test_wall_finish_theta.py \
  house_grammar/tests/test_perimeter_trim.py \
  house_grammar/tests/test_facade_depth.py \
  house_grammar/tests/test_wall_corners.py -q
```

Verificar siempre: áreas exactas por material, ausencia de caras superpuestas,
topología cerrada, volumen/silueta invariantes, vanos curvos, parcela oblicua,
escalas UV y colores independientes. Las snapshots antiguas de geometría con
coatings/pórticos implícitos necesitan una actualización consciente.
