# Frontones volumétricos y entablamentos continuos

## Ver los resultados

Desde `investigation/procedural_reconstruction`:

```bash
python3 steps/step23_fresh_theta/generar_frontones.py
# --only catalogue o --only house
```

- `steps/step23_fresh_theta/catalogo_frontones/`: diez familias y seis
  composiciones, 16 GLB. No enumera todas las combinaciones.
- `steps/step23_fresh_theta/casa_demostracion_barranco/building.glb`: **Casa de
  los Arcos**, composición original de inspiración republicana barranquina.
- Cada carpeta contiene request, arquitectura resuelta, coronamientos
  clasificados, validación, manifest y GLB. No hay renders.

La casa tiene tres cuerpos, dos pisos, jardín, cerco con puerta y portón,
galería blanca de cruces, columnas inferiores, pilastras rehundidas, ventanas
molduradas, rejas, puertas paneladas/vidriadas, zócalos y entablamentos.
Combina un frontón central mixto con óculo, otro triangular con cartela y una
sobrepuerta segmental. Las columnas de la galería se distribuyen entre los ejes
de los vanos. Es un diseño inventado, no una reconstrucción de un predio real.

## Arquitectura

- `domain/crowns.py`: `CrownDesign`, `CrownControls`, `EntablatureControls`.
- `crown_catalog.py`: clasificación determinista por atributos y selección manual.
- `crown_paths.py`: diez siluetas dimensionadas, radios derivados de ancho/flecha.
- `elevation_sweep.py`: barrido de sección en el plano de fachada, con encuentros
  de inglete limitados, tapas y orientación de malla.
- `crown_assembly.py`: cuerpo grueso, campo retranqueado, borde, cornisa de
  contorno, cordón interior, base, aperturas y ornamentos.
- `crown_resolver.py`: anclajes, herencia, compatibilidad, visibilidad y conflictos.
- `entablature_resolver.py`: arquitrabe, friso y cornisa en recorridos compartidos.

No hay reglas específicas por edificio ni coordenadas copiadas de referencias.

## Familias

| Identificador | Forma |
|---|---|
| `triangular` | Dos pendientes y tímpano moldurado. |
| `segmental` | Arco rebajado, con radio calculado a partir de la flecha. |
| `semicircular` | Medio punto; altura exactamente igual a la mitad del ancho. |
| `stepped` | Tres niveles de hombros y escalones. |
| `stepped_segmental` | Hombros escalonados y arco central. |
| `curved_pointed` | Dos ramas curvas hacia una cúspide. |
| `concave_shoulders` | Hombros cóncavos hacia un cuerpo central elevado. |
| `compound_curve` | Transición cóncava/convexa y remate central. |
| `broken` | Dos alas independientes con interrupción central. |
| `rectangular_attic` | Cuerpo horizontal y ático central. |

Los perfiles admiten las cinco familias de estilo: `republicano`, `barroco`,
`clasico`, `madera` y `moderno`. Los materiales se seleccionan independientemente.

## Clasificación dinámica

`family: auto` utiliza atributos de forma:

```json
{
  "silhouette": "mixed",
  "stepped": true,
  "thickness_m": 0.42,
  "moulding_width_m": 0.18,
  "projection_m": 0.25
}
```

Esto selecciona `stepped_segmental`. `open_center`, `concave_shoulders` y
`central_block` son otras características de selección. Precedencia:
familia explícita → abierto → hombros cóncavos → escalonado → ático → silueta.
El resultado guarda la familia y `classification_reason`. No es un clasificador
de fotografías entrenado: los atributos son observaciones/decisiones explícitas
que las reglas convierten en geometría reproducible.

## Uso en theta

```json
{
  "architectural_style": "republicano",
  "crowns": [{
    "id": "fronton_central",
    "mass_ref": "principal:0",
    "edge": 0,
    "u_m": 2,
    "width_m": 6,
    "height_m": 2,
    "anchor": "wall_top",
    "design": {
      "family": "auto",
      "silhouette": "mixed",
      "stepped": true,
      "style": "auto",
      "thickness_m": 0.4,
      "recess_m": 0.055,
      "moulding_width_m": 0.16,
      "projection_m": 0.22,
      "ornament": "keystone"
    },
    "aperture": "oculus",
    "aperture_width_m": 0.6,
    "aperture_height_m": 0.6,
    "aperture_sill_m": 0.5
  }],
  "entablatures": [{
    "id": "entablamento",
    "mass_refs": ["principal:0"],
    "height_m": 0.55,
    "projection_m": 0.20,
    "scope": "exposed",
    "ornament": "dentils"
  }]
}
```

### Anclajes

- `wall_top`: cuerpo que continúa por encima del muro. `base_m` debe mantener
  el contacto con su coronación; no levita sobre él.
- `opening_top`: sobre un vano existente, seleccionado con `opening_index`;
  se centra automáticamente. `base_m` es la separación sobre el vano.
- `facade`: pieza adosada; `base_m` se mide desde la base de la masa.

`u_m` se refiere al borde izquierdo sobre la arista canónica. Las zonas que
producen varios candidatos se rechazan como anclajes ambiguos.

### Profundidades y acabados

`thickness_m` da el espesor del cuerpo hacia el interior del muro, `recess_m`
retrasa el campo respecto al borde y `projection_m` determina el vuelo de la
moldura hacia fuera. Son medidas independientes. El cuerpo incluye 15 mm de
solape de unión al muro. El campo y el borde se emiten como sólidos cerrados.

`material`, `field_material` y `moulding_material` aceptan slots del edificio,
incluidos los declarados en `theta.materials`. `detail` (1–3) cambia el muestreo
de curvas. `base` activa la cornisa inferior.

Ornamentos disponibles: `none`, `keystone`, `cartouche`, `volutes`, `dentils`.
Las cartelas son campos ornamentales sin inscripciones ni esculturas inventadas.

### Aperturas

`none`, `oculus`, `roundhead` y `pointed`. Son huecos que se sustraen del cuerpo,
con revelados, vidrio y divisiones. Deben caber dentro del campo, libres de las
molduras. Solo se permiten sobre el muro: una pieza pegada a una pared maciza
no puede declarar una ventana falsa delante de ella. Un frontón partido no
tiene sustrato central para un óculo.

Los grandes cuerpos superiores siguen perteneciendo al sistema de masas o
`RoofBody`. El ejemplo `hombros_bajo_torre` utiliza un `RoofBody` independiente;
no alarga el frontón para simular una torre.

## Continuidad de entablamentos

Las masas seleccionadas se agrupan por cota. Sus contornos se unen antes de
distribuir arquitrabe, friso y cornisa; no se reinicia la geometría por paño.
`scope: street` selecciona frente; `exposed` incluye retornos expuestos.
Las medianeras, masas bloqueantes y huecos interrumpen el recorrido.

`anchor: absolute` con `top_m` permite una faja intermedia. Con `wall_top`,
`top_m` es un desplazamiento desde la coronación. Los motivos se repiten con
separación métrica y márgenes equilibrados.

Un entablamento explícito anclado al tope administra la cornisa superior de
sus masas: reemplaza su cornisa automática de trim, evitando duplicación.
Los zócalos siguen usando los controles de remates existentes.

## Migración

- `pediment`, `crown_triangular` y `crown_stepped` son adaptadores a cuerpos
  moldurados. Sus viejos generadores de panel plano se retiraron.
- Las bandas planas de `FacadeTopProfile` ahora usan el sweep en elevación.
  Su `trim_profile` puede indicarse o heredar el estilo del edificio.
- `ArchitecturalOrder` conserva su contrato de composición. Sus paneles y
  cornisas horizontales pasan a recorridos resueltos y ya no se emiten otra vez
  como cajas por paño. Los controles explícitos de entablamento tienen prioridad.
- Los frontones de portadas usan el mismo adaptador y motor.
- Las semánticas nuevas son `crown_body`, `crown_rim`, `crown_moulding`,
  `crown_inner_bead`, `crown_base_cornice`, `crown_*` para detalles y
  `entablature_*` para las partes horizontales.

## Verificación y límites

Pruebas de cierre, orientación y volumen positivo; dimensiones y espesores;
agujeros reales; clasificación y roundtrip; unión de frisos entre masas;
visibilidad en zonas y pisos elevados; conflictos con vanos, otros cuerpos,
proyecciones antiguas y envolvente.

Los perfiles deben caber en sus radios y escalones. Los offsets que se cruzan
se rechazan; no se reparan silenciosamente cambiando la silueta.
Los ornamentos son simplificaciones procedurales. El conjunto es un ensamblaje
de sólidos, no una unión booleana global. Las verificaciones geométricas no
afirman parecido exacto con las fotografías ni constituyen cálculo estructural.
