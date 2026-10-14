# Step 18.5 — auditoría de contrato anterior a Step 19

Rama: `step18-theta-interface`. Candidata: `theta-candidate-v0`, schema 0.2.
Baseline previa: `PRE_STEP19_BASELINE.md`. El tag `grammar-v1.0` permanece
en el commit `357a9ba`. El README raíz modificado antes de este trabajo se
conservó sin mezclar en los commits.

## Hallazgos sobre el código real

1. `floors=4` con altura desconocida completaba la altura fija 8.4 m, y daba
   un piso de 2.1 m inválido. Ahora el prior de altura usa `floors*2.8`.
2. `FacadeControls` imponía `False`, `stucco`, `brick`, `standard` y listas
   vacías desde el constructor. No se podía distinguir falta de evidencia de
   ausencia observada. Ahora los campos de identidad usan `None` cuando se
   omiten. `mode=repeat` resuelve `projections=None` y
   `material_regions=None` con reglas familiares; `()` suprime esas entidades.
3. `RoofControls` era global y su `kind` llegaba a todas las superficies;
   se añadieron overrides por masa, manteniendo polígonos derivados.
4. El modo repetitivo no permitía quitar o reemplazar un único vano. Ahora
   `opening_edits` apunta al piso y bay, y `added_openings` añade excepciones.
   Una revisión adicional detectó que el override repetitivo tampoco heredaba
   los bays globales: podía cambiar toda la pared al editar un vano. Ahora
   hereda los controles globales y sobreescribe solamente valores locales no
   nulos. `main:0` con cinco bays conserva cinco bays al suprimir uno.
5. La entrada de masas prohibía dos roles iguales; las referencias dependían
   del nombre solo. Ahora se generan `role:index` por orden métrico canónico.
6. La evidencia aceptaba índices de lista, que cambian al reordenarla. Ahora
   acepta selectores de masa, arista y `(floor,bay)`; el objeto de evidencia
   queda separado de los valores de θ.

La sospecha de que *toda* lista vacía tenía que cambiar fue demasiado amplia:
`facades=()` significa que no se introdujeron overrides, y
`materials=()` que no hay reasignaciones de slots; ninguna de esas listas
declara que el edificio no tenga fachadas o materiales. `roof.props=()` sí
declara ausencia de objetos de azotea. Tampoco cambiamos `openings=None` en
modo repetitivo: significa que la composición se deriva del patrón; en modo
explícito es obligatorio indicar una lista, incluso `[]`.

## Autoridad y completion

Prioridad: altura externa fija > altura θ > prior determinista. Si P y θ
ambos dan altura, deben coincidir o se genera error. Con pisos conocidos y
altura desconocida, `height=floors*2.8`; con altura conocida y pisos
desconocidos, `floors=round(height/2.8)` sujeto a altura de piso válida;
con ambos ausentes, 8.4 m y tres pisos. `floor_height` se deriva y no se
predice. En masas explícitas, `levels_m` es autoritativo: altura y pisos
globales deben omitirse y quedan derivados. La cerradura externa se valida
también frente al máximo de esos niveles.

`None` es valor no conocido o no especificado; `False` es ausencia conocida;
`()`/`[]` es conjunto conocido vacío. `requested.theta` y el mapa de
`Evidence` no se modifican. `ResolvedArchitecture.completed` conserva el
resumen de fuentes y `completion_details` guarda valor, fuente y política.
El prior de techo desconocido es `flat`, sin variación aleatoria; el patrón
desconocido es `single_block`. Familia desconocida: `quiet_house`.

Errores: masa/referencia no válida, solapamiento de vanos, altura
contradictoria, techo no compatible o dato condicional inactivo. Una
confianza baja en evidencia y un prior completado se registran para revisión
humana; no hay una API separada de warnings automáticos.

## Schema real 0.2

Los contratos son dataclasses de `src/domain/theta.py`:

```text
ReconstructionRequest
├── context: ReconstructionContext(parcel, fronts, crs, metric_origin, locked_height_m)
├── theta: ThetaCandidate
│   ├── height_m, floors, family, primary_color, side_material, finish
│   ├── massing: MassingControls; masses?: ArchitecturalMass[]
│   ├── facade: FacadeControls; facades: FacadeOverride[]
│   │   └── repeat: opening_edits[], added_openings[] | explicit: openings[]
│   ├── roof: RoofControls; roofs: RoofOverride[]
│   ├── site: SiteControls
│   └── materials: MaterialControl[]
├── nuisance: NuisanceParameters(seed, curtains)
├── config: GrammarConfig(implementation, grammar_reference, completion_policy, detail)
├── observations: Observation[]
└── evidence: dict[stable_theta_path, Evidence]
```

`roofs[]` hereda el techo global salvo campos indicados. El valor resuelto
por masa se guarda en `ResolvedArchitecture.roofs`. Un `tile_shed` recibe
parapeto cero si no se indica uno compatible. Los objetos de azotea siguen
en `roof.props`, con referencia `role:index`.

Orden de masa: rol, centroide XY, cota base, área, huella normalizada y
niveles. Con el mismo conjunto geométrico, invertir el orden de entrada
produce las mismas referencias. Si una huella cambia y cruza el centroide
de otra masa del mismo rol, hay que revisar los paths de evidencia: ningún
índice geométrico puede prometer identidad permanente frente a esa edición.

Paths recomendados: `theta.height_m`, `theta.massing.upper_setback_m`,
`theta.roofs[setback:0].kind`,
`theta.facades[main:0,edge:0].controls.opening_edits[floor:1,bay:2].action`,
`theta.masses[main:0].levels_m`. Los paths numéricos de listas no se aceptan
como identificadores de evidencia.

## Migración 0.1 → 0.2

No se cambiaron nombres existentes. Omitir `facade.cladding`, `services`,
`projections`, `material_regions`, `stairs`, `roof.props`, `side_material`
y `finish` ahora produce `None` en la petición en lugar de valores
implícitos. Se completan con la política 0.2, conservando la petición.
Se añaden `roofs[]`, `opening_edits[]` y `added_openings[]`.
El parser acepta 0.1, y los cinco JSON previos ejecutan 0.2 sin edición.
No se promete igualdad binaria de las salidas candidatas 0.1 y 0.2: la
canonización de masas cambia IDs y, con ello, streams de microdetalle.
El pathway histórico V1 conserva exactitud golden.

## Casos de desafío

| Caso | Líneas JSON | Entidades de vano escritas | Vanos resueltos | Qué comprobó |
|---|---:|---:|---:|---|
| 01 regular + excepción | 19 | 3 edits | 11 | portón, supresión y balcón ausente sobre 4 bays |
| 02 dos cubiertas | 12 | 0 | 16 | main plano y setback inclinado |
| 03 rol repetido | 15 | 0 | 8 | dos `main`, referencia `main:1` estable |
| 04 muchos unknown | 18 | 0 | 9 | prior sencillo, evidencia y completion separados |
| 05 irregular explícito | 17 | 5 vanos | 5 | control total sin repetición |

Los cinco tienen `input_theta.json`, `resolved_theta.json`, GLB, ISO,
STREET y manifest/fingerprint bajo `challenge_cases/outputs/` (gitignored).
`summary.json` contiene las cuentas y huellas completas. Son ejercicios de
contrato, no muestras de Barranco ni datos de entrenamiento.

La auditoría de los cinco ejemplos de Step 18 está en
`EXAMPLE_RESOLUTION_SUMMARY.md` y el JSON homónimo. Entre 8–14 campos θ
fueron explícitos y 15–20 quedaron registrados como completados o derivados; la cota por piso,
las exposiciones y muchos vanos fueron derivados. Sus semillas solo afectan
cortinas, jardín y microdetalle permitido.

## Gate y evaluación

Las pruebas nuevas cubren tri-state, seis combinaciones de altura, conflicto,
techos por masa, ediciones de vanos, referencias estables, evidencia,
roundtrip y ξ. El gate post-hardening terminó con **37/37 pruebas θ**, **203
passed y 125 subtests passed** en la suite completa (250.79 s). El
comparador golden confirmó **3/3 hashes exactos** de geometría, UV,
materiales y componentes contra `grammar-v1.0`. Los cinco challenges
generaron GLB, ISO y STREET con validación de contención; sus huellas
están en `challenge_cases/outputs/summary.json`.

Sí estamos listos para **comenzar un primer ajuste manual exploratorio** en
Step 19 con edificios que puedan describirse con masas poligonales simples.
No es una garantía de expresar todos los casos reales. Siguen abiertos
patios/agujeros, terreno inclinado, fachadas explícitas que cruzan bandas de
exposición parcial y algunos volúmenes curvos. Ante uno de esos casos, el
contrato falla expresamente; no convierte la observación en otro edificio
sin aviso. Step 19 deberá registrar cuántos casos tropiezan con esos límites
antes de considerar congelar `theta-v1`.
