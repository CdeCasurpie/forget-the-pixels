# FacadeZone — infraestructura horizontal de fachada (θ 0.3)

## Diagnóstico y alcance

`FaceBand` selecciona programas por Z sobre una arista completa. El resolver
clasifica cada arista mediante el producto escalar de su normal exterior con
`front=-inward`, `back=inward`, `left=-tangent`, `right=tangent`, usando el
marco de `PlanRegion`. Una etiqueta de cara puede identificar varias aristas.
`_composition()` usa metros locales; reutiliza `_relief()` de
`facade_program.py`. `wall_domains()` calcula exposición en el chart original
de la arista; `VisibleFacadeBuilder` recorta primitivas sin redistribuir vanos.

La extensión introduce únicamente regiones de composición. No cambia masas,
soportes, cubiertas, exposición, prefabs ni la identificación de caras.

## Contrato aditivo

```python
@dataclass(frozen=True)
class FacadeZone:
    face: str
    controls: FacadeControls
    u: tuple[float, float] = (0., 1.)
    z_m: tuple[float, float] | None = None
    role: str | None = None

# Nuevo campo opcional, al final de MassComponent:
zones: tuple[FacadeZone, ...] = ()
```

Ejemplo de un componente con tres composiciones distintas:

```json
{
  "id": "main",
  "region": {"front_edge": 0},
  "levels_m": [0, 3, 6],
  "zones": [
    {"face": "front", "u": [0, 0.25], "role": "left",
     "controls": {"bay_count": 1, "balconies": false}},
    {"face": "front", "u": [0.25, 0.60], "z_m": [0, 6], "role": "middle",
     "controls": {"mode": "explicit", "openings": []}},
    {"face": "front", "u": [0.60, 1], "role": "right",
     "controls": {"bay_count": 2, "balconies": false}}
  ]
}
```

Este objeto va dentro de `theta.massing.components` con `schema_version="0.3"`.
No hay entrada XY nueva ni hardcodes por identificador de lote en `src`.

### Coordenadas: composición local, clipping en el chart original

- `u` normalizado se mide de `vertex_a` a `vertex_b` de **cada arista original**,
  antes de exposición. No es izquierda/derecha en pantalla. Si cambia su longitud
  L, los límites siguen siendo `u0*L` y `u1*L`.
- `z_m` está referido a la base del componente, no a cota absoluta. `None`
  ocupa toda su altura.
- Dentro de los controles, `u_m`, `v_m`, `bay_axes_m`, aberturas añadidas o de
  reemplazo, proyecciones, regiones de material y escaleras son locales a la
  esquina inferior de la zona, en metros. No se escalan entidades explícitas.
- Se compone una vez con ancho `(u1-u0)*L`. Luego se suma `u0*L` a U y `z0`
  a V. El `FacadeSpecification` de una zona conserva los vértices y el ancho
  originales de la pared; su `ResolvedWall.base_z` es la base del componente.
- Los pisos intersectados por la zona conservan sus cotas; se incluyen los
  límites Z de zona como extremos locales. Las reglas de piso y
  `OpeningEdit.floor` usan el **índice original de piso del componente**.
  `OpeningEdit.bay` se refiere al bay local de la zona. La primera banda de
  una zona alta no se convierte en planta baja ni se renumera como piso 0.
- La composición no depende de cuánto se vea. Solo después de componer se
  intersecta su dominio con exposición. Los vanos ocultos conservan sus
  coordenadas semánticas; se recorta su geometría, incluidas curvas de arcos.

Esta elección permite inferir ritmos dentro de una región de imagen sin
convertirlos en coordenadas de todo el edificio. La transformación explícita
a un chart estable permite comparar observaciones y evita refluir entidades
cuando cambia una oclusión.

### Propiedad de la superficie y prioridades

1. Se resuelve el programa base exactamente como antes: override de arista,
   o `FaceBand`, o `component.facade` (ciego si es `None`).
2. Las zonas seleccionadas sustituyen ese programa **solo** en sus rectángulos.
   Sus controles se completan independientemente con los defaults de familia,
   igual que `FaceBand`; no heredan campo a campo los controles de la base.
3. El programa base conserva sus entidades originales y se dibuja en el
   complemento. No se compone de nuevo en cada hueco residual.
4. Cada patch posee una porción disjunta de superficie. `patch_domains()`
   descompone el complemento en rectángulos sin solapes, incluso si hay un
   hueco interior. No se emite una pared completa adicional detrás de las zonas.
5. Los escalones de acceso de una arista zonificada también respetan esos
   dominios, para no recuperar puertas eliminadas por una zona ciega.

Una zona ciega sigue produciendo pared, con cero aberturas automáticas.
Los bordes compartidos están permitidos; una intersección de área positiva
entre zonas de la misma cara (incluido `all`) se rechaza con
`overlapping facade zones`. La validación se ejecuta también para caras
ocultas. Se rechazan intervalos inválidos, NaN/inf, Z fuera del componente,
zonas en componentes abiertos y entidades explícitas fuera de su chart local.

### Compatibilidad

`FaceBand` permanece intacto; conserva su selección vertical y su prioridad
histórica «última banda coincidente». Esa regla no se extiende a las zonas.
JSON anteriores sin `zones` se decodifican con `zones=()`; no necesitan
migración ni cambio de versión. La ruta de composición anterior se conserva.
El test de compatibilidad compara paredes y bytes de vértices/caras con
huellas capturadas antes de esta extensión.

Además, se reconstruyeron en memoria los **19 AFTER anteriores** y sus
fingerprints de malla coinciden **19/19** con los manifiestos previos.

### Corrección semántica del checkpoint

`FacadeSpecification.is_front` indica exclusivamente orientación hacia un
frente de calle declarado, usando la comparación de normales del resolver.
Una cara local `right` puede mirar a una segunda calle; su nombre no basta
para decidir este atributo.

`program_enabled: bool | None = None` controla independientemente si se
ejecuta el programa arquitectónico. La propiedad `has_program` utiliza ese
valor explícito, o `is_front` si es `None`, para leer especificaciones legacy.
Las zonas se resuelven con `program_enabled=True` y la orientación real de
su arista. La misma separación se aplica a los programas base de componentes
y overrides de arista: tampoco convierten una cara posterior en frente.

La gramática consume `has_program` para generar vanos, acabados y relieves.
Por tanto, corregir `is_front` no suprime los vanos laterales/posteriores.
Cinco casos de regresión verifican las cuatro caras y una segunda calle,
incluida igualdad de geometría con el comportamiento anterior. Los
**21 fingerprints** (19 AFTER + 2 demos) siguen idénticos; se actualizaron
los `resolved_theta.json` para guardar la separación semántica.

## Prueba visual: solo BCP y Metro

`facade_zone_recipes.json` añade las zonas a copias de las recetas existentes.
`build_after.py --facade-zones` procesa únicamente esos dos casos y escribe
`after_facade_zones/`, usando las cámaras, semillas y parcelas anteriores.

```bash
python steps/step22_massing_before_after/build_after.py --facade-zones
# Regenerar solo uno:
python steps/step22_massing_before_after/build_after.py --facade-zones --lot 1138323
```

- **BCP / 1137619:** primer 25% con puerta alta; 75% restante con tres ventanas
  en un programa explícito independiente, sobre las aristas `front`.
- **Metro / 1138323:** alas 0–30% y 70–100% con repetición; centro 30–70% con
  un único vano ancho. Los tres programas abarcan Z=0.3–5.6 m; zócalo y banda
  superior conservan el programa base. Se selecciona la cara local `right`,
  que corresponde a la fachada principal visible. El vano central es una
  demostración del chart, no un portal monumental.

### Revisión de las diez vistas generadas

Las planchas incluyen todas las cámaras `present`, en orden de `cameras.json`:

- `lotes/1137619_banco_neoclasico/after_facade_zones/review_all_views.jpg`
- `lotes/1138323_casona_amarilla_esquina/after_facade_zones/review_all_views.jpg`

**BCP:** la primera vista oblicua (`qFcEPr9c2-KlfqA3Wi0cYw`) muestra el
acceso alto y la secuencia de ventanas más estrechas en los tramos `front`.
Las vistas orientadas a la otra cara conservan su programa anterior; por eso
la diferencia en ellas es pequeña. La envolvente gris coincide con la base.
No se resolvió el acceso arquitectónico de esquina ni la secuencia real de
pilastras; la finalidad es demostrar propiedad independiente de cada tramo.

**Metro:** en las vistas segunda, tercera y cuarta se distingue claramente
el centro de un solo vano ancho entre dos grupos de ventanas estrechas.
La tercera (`XOMWgrPYXSuEk0wkcsLh2g`) es la demostración más directa de las
tres regiones en una misma pared. Las proporciones y el vano rectangular no
reproducen el portal arqueado de la foto: es una prueba de infraestructura.
Las proyecciones base sustituidas por las zonas desaparecen, y el pedimento
que sobresalía de la banda superior queda recortado por el dominio residual.
Esto hace la demostración menos fiel en remates que el AFTER base; no se
presenta como una mejora fotográfica global. La masa y la cubierta resueltas
son iguales a las anteriores.

Ambos manifiestos pasan la validación de envolvente: **5 comparativas por
caso**, BCP **5 112 triángulos**, Metro **21 596 triángulos**. Los archivos
`request.json`, `resolved_theta.json`, `building.glb`, `cameras.json` y las
comparativas individuales acompañan las planchas.

## Verificación automatizada

`tests/test_facade_zones.py` incluye los seis contratos solicitados:

- `test_facade_zone_three_horizontal_regions`
- `test_facade_zone_combines_u_and_z`
- `test_facade_zone_blind_region`
- `test_facade_zone_rejects_overlap`
- `test_facade_zone_preserves_visibility_clipping`
- `test_facade_zone_backwards_compatible`

También cubre límites inválidos/NaN/inf, complemento del programa base,
escalado de longitud, índices de piso, transformación de entidades, roundtrip,
errores aun con oclusión total, bays estables tras exposición, escalones de
puertas suprimidas, caras rotadas y componentes elevados. El área de pared
triangulada se mide para detectar duplicación de superficies exteriores.
`tests/test_step22_after.py` comprueba en los dos demos que masas, cubiertas,
soportes, zonas exteriores, cercos, semillas y cámaras permanecen iguales,
y que una sola arista contiene los dos/tres programas esperados.

Desde la raíz de `procedural_reconstruction`:

```bash
PYTHONPATH=src:. /home/cesar/Escritorio/UTEC/PFC1_Lima/venv310/bin/python -m pytest tests -q
```

Resultado final: **289 passed, 127 subtests passed in 63.83s**. Incluye
**25 casos de FacadeZone** y **2 regresiones de los demos**, además de la
suite previa. `git diff --check` también pasa.

## Limitaciones y siguiente iteración

- Los intervalos se aplican a cada arista clasificada, incluidos bordes de
  patio. No existe todavía una fachada lógica que fusione varios segmentos
  catastrales casi colineales ni composición alrededor de esquinas.
- Los controles de repetición existentes pueden generar una entrada por zona
  de planta baja. Para exigir exclusivamente ventanas se puede usar un
  programa explícito o sus ediciones existentes. No se añadió un lenguaje
  arquitectónico de accesos.
- Una zona de repetición demasiado estrecha (<1.5 m), o con pisos recortados
  donde no caben sus vanos, se rechaza; un programa explícito permite franjas
  pequeñas o ciegas. Las entidades explícitas usan metros: una reducción de
  ancho puede invalidarlas aunque sus límites normalizados sigan siendo válidos.
- Los detalles implícitos de la gramática (losas, zócalos, juntas y servicios)
  siguen anclados al chart de pared y se enmascaran por patch. No son nuevos
  ritmos locales. Los prefabs/relieves que exceden el dominio de un patch se
  recortan; no se extiende el dominio sobre la cubierta para conservar remates.
- Los sólidos de patches vecinos pueden tener tapas internas coincidentes;
  sus superficies exteriores de pared tienen propiedad disjunta, comprobada
  midiendo área de triángulos. No se introdujo un booleano global de sólidos.
- La siguiente iteración **BayGroup** podrá definir grupos de bays y ritmos
  dentro del chart local de una zona, con asignación explícita de vanos por
  grupo/piso. Esta iteración aporta límites validados, composición local,
  índices de piso estables, transformación al chart de pared y clipping sin
  reflujo. BayGroup todavía no está implementado.
