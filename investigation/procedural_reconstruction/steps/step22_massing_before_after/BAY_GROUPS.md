# BayGroup — ritmo local y relief de ámbito de fachada

## Diagnóstico y decisión

El compositor theta-candidate resolvía un solo par `axes/pitch` y asignaba
implícitamente una entrada al bay 0 de planta baja. `_relief` recibía esos
dos argumentos pero no los usaba. Sus balcones y shutters dependen de cada
opening; cornisa, bandas, pilastras de extremos, galería, toldo, letrero,
bajante y regiones de material dependen del chart completo.

La extensión pertenece a `modeling/facade_composition.py`, compartido por
paredes base y FacadeZone. Se genera el layout de todos los grupos, se unen
sus openings y se ejecuta **una sola pasada de relief para todo el chart**.

## API pública (schema 0.3)

```python
@dataclass(frozen=True)
class BayGroup:
    u: tuple[float, float]
    count: int
    ground_role: str = "inherit"
    role: str | None = None

# Campo aditivo en FacadeControls:
bay_groups: tuple[BayGroup, ...] = ()
```

Ejemplo JSON dentro de `FacadeControls`, tanto en una pared como en una zona:

```json
{
  "mode": "repeat",
  "bay_groups": [
    {"u": [0, 0.30], "count": 3, "role": "left_wing"},
    {"u": [0.30, 0.52], "count": 1, "ground_role": "entrance", "role": "primary_entry"},
    {"u": [0.52, 1], "count": 4, "role": "right_wing"}
  ],
  "balconies": false
}
```

Los grupos no vacíos requieren schema 0.3 y modo `repeat`. No pueden
coexistir con `bay_count` ni `bay_axes_m` explícitos. Se valida toda la
configuración, incluso controles de caras ocultas. No se usan XY globales.

### Intervalos, layout e índices

- U está normalizado al **chart actual**: pared completa o ancho de FacadeZone.
- La entrada debe estar ordenada por U, sin solapamientos de interiores:
  se rechaza una lista desordenada, en vez de reordenar silenciosamente.
- Se exige `0 <= u0 < u1 <= 1`, valores finitos y `count` entero positivo.
- Se permiten gaps: **no generan openings**, aunque el relief global puede
  continuar a través de ellos. `blind` solo afecta a planta baja, no al layout
  ni a los pisos superiores.
- Cada grupo conserva márgenes de 0.32 m en sus extremos. Para longitud L:

  ```text
  start = u0 * L
  end   = u1 * L
  pitch = (end - start - 0.64) / count
  axis[i] = start + 0.32 + (i + 0.5) * pitch
  ```

- Los grupos demasiado estrechos o los vanos que no caben producen error.
  Las aberturas deben respetar también 0.12 m de margen respecto a su grupo.
- Se aplanan los bays en orden izquierda→derecha: 3|1|4 produce índices
  **0,1,2 | 3 | 4,5,6,7**. `OpeningEdit(floor,bay)` conserva su API.
- `ResolvedBay` conserva `axis_m`, `pitch_m`, límites del grupo, índice de
  grupo, índice local, índice aplanado, `ground_role` y `role`.
  `resolve_bay_layout()` permite recuperar esa información sin reconstruirla
  a partir de distancias entre ejes. No se añade una nueva entidad al theta
  resuelto: `FacadeComposition` conserva sus cuatro campos.

### Planta baja y pisos superiores

| ground_role | Semántica |
| --- | --- |
| `inherit` | Ventanas según la familia; storefront si el ground de familia es shopfront. Nunca inventa una puerta/garage en el primer bay. |
| `entrance` | Requiere `count=1`; genera una puerta `wood_panel`. |
| `garage` | Requiere `count=1`; genera un gate `roller`. |
| `shopfront` | Todos sus bays ground usan `storefront`. |
| `blind` | Omite sus openings ground y conserva ejes/índices para pisos superiores. |

El acceso ocupa 75% del pitch de su grupo; no se aplica el cap legacy de
1.2 m para puertas. Su altura usa `max(window_height_m, 2.3)`, acotada por
el piso. Esto permite dominar por ancho mediante el intervalo del grupo,
sin introducir un prefab nuevo ni un lenguaje de portales.

En pisos superiores se conservan reglas de familia y alternancia de
balcones por índice aplanado. FacadeZone conserva los índices de piso del
componente y desplaza las entidades después de componer. La exposición
no modifica ejes ni recompone grupos.

Las ediciones `suppress/replace` son posteriores a la semántica ground:
un reemplazo puede ocupar un bay ground ciego, pero debe quedar dentro
de su grupo. Un `added_opening` también debe pertenecer a un grupo y no
solaparse con otro vano; no puede ocupar un gap.

### Herencia de overrides

Un override con grupos no vacíos sustituye el layout heredado, conservando
los restantes controles heredables. Si el override declara simultáneamente
grupos y count/axes, se rechaza. Una tupla local vacía selecciona la ruta
legacy del override; los grupos no se heredan implícitamente desde el global.

## Relief y pitch no uniforme

El pitch se usa **por bay/grupo** para dimensionar sus openings. No se
calcula un pitch global ficticio. Se expuso `compose_relief()` en
`facade_program.py` sin argumentos axes/pitch; el antiguo `_relief()` queda
como wrapper compatible para sus consumidores legacy.

Scopes actuales:

- **Bay:** opening y relief vinculado a él (balcony/shutter).
- **Group:** intervalo, cantidad, pitch y semántica ground.
- **Chart/zone:** cornisa, sill bands, pilastras de extremos, galería,
  toldo, letrero, bajante y regiones de material existentes.

El relief global no se llama por grupo. Los tests comparan estas entidades
con las de un chart sin grupos y comprueban que cada balcón corresponda
al opening esperado. Las proyecciones no se recortan a los límites de grupo:
siguen las reglas existentes y el clipping del chart superior.

## Compatibilidad

La rama `bay_groups=()` conserva el algoritmo anterior. La serialización
`canonical()` omite exclusivamente este campo vacío en FacadeControls para
preservar hashes semánticos anteriores; `asdict()` sí expone el nuevo campo
vacío, como es normal en una extensión de dataclass. Los grupos no vacíos
se serializan completos y tienen roundtrip estricto.

Se verificaron **21/21 fingerprints antiguos idénticos**, junto a igualdad
de los 21 θ resueltos canónicos contra los artefactos guardados. Incluye
19 AFTER y los dos demos FacadeZone; no se reescribieron sus salidas.
Los seis pares de hashes congelados del compositor anterior también pasan.

## Demostración y revisión visual

Ejecutar desde `investigation/procedural_reconstruction`:

```bash
/home/cesar/Escritorio/UTEC/PFC1_Lima/venv310/bin/python steps/step22_massing_before_after/build_bay_groups.py
```

`bay_group_recipes.json` define solo BCP y Metro. El builder lee el AFTER
original, reemplaza un programa de arista y escribe `after_bay_groups/`.
Verifica que contexto, masas, cubiertas, cercos, soportes y áreas exteriores
coincidan con el baseline. Las cámaras y semillas son las mismas; ambos
casos pasan validación de envolvente con cinco vistas `present` cada uno.

Planchas **PHOTO | AFTER antes de BayGroup | AFTER BayGroup**:

- `lotes/1137619_banco_neoclasico/after_bay_groups/review_all_views.jpg`
- `lotes/1138323_casona_amarilla_esquina/after_bay_groups/review_all_views.jpg`

Se revisaron las diez vistas finales:

- **BCP:** la arista 5 ahora muestra tres ventanas, puerta ancha y cuatro
  ventanas. Las vistas segunda a cuarta muestran claramente la jerarquía
  entre grupos y la cornisa continua. La posición es una demostración de
  acceso no inicial: **no reproduce el acceso real de esquina**. Los shutters
  de la familia republicana siguen visibles; no se añadieron como feature.
- **Metro:** la arista 6 presenta dos alas y una puerta central de mayor
  ancho. La tercera vista muestra con claridad el ritmo 3|1|4. Se conservó
  el amarillo evitando la región ground de piedra mediante el control
  existente `material_regions=[]`. El vano sigue siendo una puerta simple;
  su remate monumental anterior no forma parte del nuevo programa.

Mejora observada: el centro puede dominar por ancho sin enumerar ventanas
explícitas y sin multiplicar cornisas. No es una mejora global de semejanza
fotográfica: el perfil monumental y los arcos de Metro siguen pendientes.

## Pruebas y límites

Validación final:
- BayGroup + FacadeZone + compositor: **64 passed in 4.44s**.
- Suite completa: **328 passed, 127 subtests passed in 70.84s**.
- BayGroup añade **28 casos**; los 300 tests anteriores siguen pasando.
- **21/21 fingerprints legacy idénticos**, 21/21 planes canónicos equivalentes.
- `git diff --check`: sin errores.

`tests/test_bay_groups.py` contiene los diez tests solicitados y casos de
validación, gaps, roles ground, edición fuera de grupo, esquema/roundtrip,
pisos de zona vertical, balcones y herencia del layout. La suite anterior
continúa cubriendo `is_front` frente a `has_program` en laterales/posteriores.

Limitaciones deliberadas: un acceso/garage por grupo de un bay; controles
de ancho/alto compartidos por chart; sin programas superiores por grupo;
sin agrupación alrededor de esquinas. La metadata de layout es interna y
recuperable, no un nuevo schema de instancias arquitectónicas.

La deuda existente de `program_enabled` y los relieves implícitos de la
gramática permanece igual. ArchitecturalMotif, CrownProfile y
ArchitecturalOrder no forman parte de esta iteración.
