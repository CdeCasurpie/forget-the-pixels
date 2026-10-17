# Contrato de intención arquitectónica — intent-v1

Fuente ejecutable: `house_grammar/src/domain/building_intent.py`. Esta entrada es independiente del theta antiguo; no exige compatibilidad ni evidencia. No ejecuta aún la planificación geométrica.

## Entrada mínima

```json
{
  "version": "intent-v1",
  "context": {
    "parcel": [[0,0],[8,0],[8,14],[0,14]],
    "fronts": {"F1": 0},
    "levels_m": [0,3.2,6.0]
  },
  "building": {}
}
```

`context` lo proporciona la aplicación, no el LLM. El modelo produce `building`. La aplicación añade versión y semilla. `building: {}` autoriza completado completo; no significa casa vacía.

## Coordenadas e identidad

- Parcela: anillo XY métrico, sin vértice de cierre repetido; válido y con área positiva. Puede recibirse horario o antihorario.
- `fronts`: IDs estables asociados a aristas del **anillo recibido**, sin canonización silenciosa en esta fase.
- Para interpretar izquierda/derecha: observador exterior mirando perpendicularmente al interior del lote. El futuro planificador deriva ese marco de la orientación geométrica, no del orden de las fotos ni de los vértices.
- `levels_m`: cotas de pisos terminados; la última delimita el nivel superior del cuerpo. Los espesores se resuelven después. Las cotas pueden estar elevadas respecto del terreno.
- `ground_z_m`: cota exterior opcional; omitida autoriza completado. Pendiente ampliar a suelo variable en fases geométricas.
- Pisos de autoría: **base 1**. `[1,2]` son primer y segundo piso. No confundir con índices del theta anterior.
- Cuerpo implícito: `main` si se omite `bodies`. Si se declara la lista, reemplaza ese cuerpo; debe contener al menos uno.
- IDs: letras iniciales, seguidas por letras, dígitos, `_` o `-`; únicos en su colección.
- No se aceptan `u_m`, `depth_m` o huellas métricas por operación. Las proporciones relativas sí son válidas.

## Omisión y ausencia

| Entrada | Semántica |
|---|---|
| Propiedad omitida | El generador decide |
| `site.fence: false` | No generar cerco |
| `site.garage: false` | No generar cochera |
| `site.door: true` | Generar puerta y decidir ubicación |
| `site.door: "left"` | Generar puerta a la izquierda |
| `site.door: {position, style?, material?}` | Puerta con diseño local (`style` y `material` independientes del estilo global) |
| `windows.count: 0` | Cero ventanas en el ámbito declarado |
| `roof.objects: []` | Ausencia explícita de objetos de azotea |
| `roof.objects` omitido | Poblar automáticamente |
| `roof.objects: ["water_tank"]` | Incluir tanque; permitir completar otros compatibles |
| `null` | No se usa como sinónimo de omisión en este contrato |

`evidence` puede omitirse completamente. Si se adjunta, es un objeto de metadatos; no modifica permisos de generación ni se valida como prueba de existencia.

## Campos de building

| Campo | Contenido |
|---|---|
| `organization` | `compact`, `bar`, `L`, `U`, `courtyard`, `stepped`, `podium`, `attached`, `corner`, `incremental` |
| `profile` | Uno de los perfiles de `generation_profile.py` |
| `style` | `republicano`, `moderno`, `clasico`, `barroco`, `madera`, `mixed` |
| `bodies` | ID, posición cualitativa, pisos, ancho relativo, estilo local |
| `operations` | Operaciones sobre cuerpos con IDs y dependencias |
| `site` | Espacio frontal, cerco, puerta y cochera |
| `facades` | Ámbitos cuerpo/frente/pisos, ventanas y alineación |
| `roof` | Cubierta, objetos y sombra |
| `finishes` | Acabados de frente y laterales |

### Masas y operaciones

Operaciones: `setback`, `bite`, `courtyard`, `attach`, `advance`, `overhang`, `open_ground`, `recess`, `depth_rhythm`, `floor_shift`, `chamfer`, `round_corner`, `crown`, `loggia`.

- Campos obligatorios: `id`, `kind`, `body`.
- `front` obligatorio en operaciones orientadas; opcional para patio y adición.
- `floors`: subconjunto ordenado de los pisos del cuerpo; omitido usa su ámbito completo.
- `position`: `left`, `center`, `right`, `corner`, `rear`, `all`.
- `depth`: `shallow`, `medium`, `deep`.
- `width`: `narrow`, `medium`, `wide`, `all`.
- `after`: IDs de operaciones previas, sin ciclos.
- `depth_rhythm` exige `weights` positivos y un `planes` por sector: `base`, `recessed`, `projecting`.
- `attach` solicita una adición conectada al cuerpo; no requiere que el LLM dibuje el nuevo polígono.
- `floor_shift` significa desfase de planos entre niveles; `depth_rhythm`, alternancia horizontal. `crown` afecta la coronación. No usar «zigzag» sin distinguirlos.

Las categorías cualitativas todavía no tienen constantes métricas: los rangos dependen de tipo y escala y se calibrarán en Fase 1/2. No inventar una equivalencia universal como «medium = 1 m».

### Sitio y cerramiento

- `front_space`: `false` o `{front, depth?, use?}`. Usos: `garden`, `patio`, `driveway`, `mixed`.
- `fence`: `false` o `{front, form, height?, style?, cap?}`.
- Formas: `solid`, `open`, `base_and_rail`, `partial`.
- Alturas: `low`, `high`. Tapa: `plain`, `tile`, `corrugated`.
- `door`/`garage`: booleano o `left`/`center`/`right`. `door` admite además un objeto `{position, style?, material?}`; los materiales de puerta son `wood`, `metal` y `glass`, y no cambian el estilo del resto del edificio.
- Con cerco, accesos en el cerramiento; sin cerco, en la envolvente. La Fase 5 enlaza el cerramiento con los vanos reales de planta baja.
- Ausencia de cerco no impone retiro cero. Cerco alto no determina profundidad del espacio oculto.

### Fachadas

Cada entrada exige `body`, `front`, `floors`. No permitir dos entradas ambiguas para el mismo cuerpo/frente/piso; agrupar o dividir explícitamente sus ámbitos.

- `alignment`: `aligned`, `staggered`, `independent`.
- `windows`: `count` entero no negativo; proporción opcional `horizontal`, `vertical`, `square`, `small_high`; distribución `balanced`, `left`, `right`, `grouped`; material de marco `wood`, `metal`, `pvc`; mecanismo opcional `guillotine`, `sliding`, `casement`, `awning`, `fixed`; estilo local opcional.
- El conteo se aplica a **cada piso** del ámbito, no al total del grupo.
- Un plano con cero ventanas no obliga a eliminar puertas ni detalles.
- Máscaras por sector y grupos secundarios se incorporarán con pruebas al ampliar el contrato; no fingir que ya existen.

### Cubiertas y acabados

- Cubierta: `slab`, `corrugated`, `tile`, `mixed`.
- `shade`: booleano; omitido permite decisión generativa.
- Objetos: `water_tank`, `tank_elevated`, `laundry`, `antenna`, `planter`, `caseta`, `stair_bulkhead`, `hvac`.
- Acabados de `front`/`sides`: `plaster`, `rough_plaster`, `brick`, `concrete`, `mixed`.
- Cobertura parcial, colores por sector, pendientes y muebles se ampliarán en sus fases. No son geometría implementada por esta entrada.

## Prioridad y conflictos

1. Contexto humano fijado.
2. Presencias, ausencias, conteos y relaciones explícitas.
3. Selecciones locales antes que valores globales.
4. Perfil generativo.
5. Variación aleatoria.

Orden de operaciones: cuerpos → vacíos → pisos → planos → espacios → coronaciones. Sitio se planifica antes. Dependencias `after` se respetan dentro de ese orden; una dependencia hacia una fase posterior se rechaza. Empates independientes se ordenan por ID, no por posición en el JSON.

Una organización es un prior; las operaciones explícitas refinan esa base. Si dos operaciones modifican la misma región, el futuro planificador debe componerlas según dependencia o diagnosticar contradicción. La Fase 0 verifica referencias y orden; **no detecta intersecciones espaciales**.

Ante una imposibilidad geométrica, ajustar dimensiones libres primero. No suprimir operaciones ni elementos declarados, ni deformar la parcela o las alturas fijadas. Si no existe solución dentro de los parámetros libres, devolver conflicto localizado.

## Perfiles iniciales

`barranco_residential`, `barranco_incremental`, `barranco_casona`, `barranco_mixed_use` definen uso, construcción, acabado, evolución, conservación y ocupación. Todos permiten interiores, props de azotea y estilos mezclados, sin evidencia obligatoria.

Son **hipótesis iniciales de diseño**. No se ha medido su frecuencia real ni se atribuye estado socioeconómico a partir de una cubierta. En esta fase no seleccionan mallas ni asignan porcentajes de área libre. Esas decisiones deben evaluarse posteriormente.

## Límites de Fase 0

- Contrato y validación, no generación geométrica.
- Un espacio frontal y un cerco principales en esta versión; los múltiples frentes de masas/fachadas sí se pueden referenciar.
- No es un catálogo exhaustivo de ambientes, mobiliario, cierres o estructuras.
- No certifica coherencia estructural ni habitabilidad.
- Los casos de evaluación son sintéticos y aún no constituyen una evaluación visual independiente sobre fotos reales.
- Ampliar el lenguaje con casos y pruebas durante las fases posteriores; no añadir claves ignoradas silenciosamente.

## Extensión Fase 2

Se añaden operaciones `portico`, `vestibule` y `balcony` en la fase `spaces`,
con el mismo vocabulario de cuerpo, frente, pisos, posición, ancho y profundidad
cualitativos. No reciben coordenadas. `planning.articulation.plan_articulation`
materializa estas operaciones junto con `loggia`, `recess`, `depth_rhythm` y
`floor_shift`. Véase `../phase2/README.md` para dimensiones iniciales, semántica
del plano base y reserva de accesos para Fase 3. El banco Fase 0 no se modifica.

## Extensión Fase 3

`planning.interiors.plan_interiors` consume el plan de articulación y produce
`interior-plan-v1`: plantas esquemáticas con ambientes, puertas, ventanas,
núcleo vertical y grafo de conexiones. No añade claves nuevas a `intent-v1`; la
única entrada de habitabilidad es la ya declarada (`site.door`, `site.garage`,
`facades[].windows` con `proportions`/`weights`/`distribution`). Los accesos
reservados por Fase 2 se conectan a un único ambiente. Véase
`../phase3/README.md` para plantillas del núcleo, anchos de circulación,
partición condicionada por fachada y expectativas de las fijaciones.

## Extensión Fase 4

`planning.envelope.plan_envelope` consume el plan interior y produce
`envelope-plan-v1`: vanos métricos, muros y particiones huecas, losas por nivel,
soportes y carpintería. No añade claves nuevas a `intent-v1`; reconoce las ya
documentadas `site.door` como objeto y `windows.mechanism`.

- Antepechos por uso: `small_high` 1.50 m; baño/servicio 1.20; cocina-comedor
  1.05; sala 0.70; tienda 0.60; resto 0.90. Dintel libre 0.20 m sobre el vano.
- Altura de vano y proporción se resuelven juntas. Si la banda solicitada no
  cabe en la altura útil, el vano se limita al máximo disponible y la adaptación
  queda como decisión explícita (`requested proportion adapted...`).
- Mecanismo derivado si se omite: `vertical` → `casement`, `horizontal` →
  `sliding`, `small_high` → `awning`; cochera `sliding` + `metal`; puerta
  peatonal `hinged`. Estilo local hereda del cuerpo y del estilo global.
- Completado activo: una ventana por ambiente perimetral habitable en ámbitos
  no declarados; los frentes nombrados tienen prioridad y las aristas sobre el
  borde del lote son muros medieros. `facades: []` desactiva el completado.
  Los pisos ya declarados con `windows` quedan cerrados.
- Las decisiones (`decisions`) usan un vocabulario auditado: proporción
  adaptada, cabeza limitada por losa y dintel, completado en frente no
  especificado, desplazamiento a lo largo del mismo muro y revelas fusionadas
  en un muro doble delgado. Lo pendiente queda en `pending` (`roof`,
  `site.fence`, `site.access_route`, `interior.furniture`); una planta baja
  abierta difiere la puerta de calle hasta la fase de acceso.

Véase `../phase4/README.md` para escenarios, comandos y limitaciones
(envolvente sin CSG, piezas cerradas por sólido y saneadas para extrusión, y
verificación ingenieril pendiente).

## Extensión Fase 5

`planning.site_access.plan_site` toma la envolvente y produce `site-plan-v1`:
cerramiento físico en el frente declarado, portones y recorrido desde la calle
hasta los **vanos reales** de planta baja. No amplía las claves de `intent-v1`:
usa `site.front_space`, `site.fence`, `site.door` y `site.garage` ya existentes.

- `fence: false` prohíbe el cerco. Con `front_space` explícito y `fence`
  omitido, se completa una reja baja y abierta; sin espacio frontal declarado
  se deja la entrada del edificio en el borde de la calle, sin cerco inventado.
- `form` define la **geometría** (`solid`, `open`, `base_and_rail`, `partial`),
  mientras `style` se hereda o se expresa localmente sin cambiar esa forma.
  `height: low/high` produce 1.15/2.20 m. `cap` (`plain`, `tile`,
  `corrugated`) se apoya en el muro o postes; un portón vehicular con remate
  de teja/calamina recibe cubierta apoyada en sus jambas.
- `site.door.position` y `site.garage` orientan los accesos; el plan de sitio
  **no crea una puerta de edificio nueva**. Con cerco, las hojas viven en el
  cerramiento; sin cerco, la entrada sigue siendo la del edificio. La planta
  baja abierta conserva su umbral sin simular un muro ni una hoja.
- Los itinerarios libres miden 0.82 m peatonal y 2.20 m vehicular. Si el
  primer piso está elevado, se usa rampa de pendiente máxima 1:12 cuando hay
  longitud disponible; en otro caso, escalones de contrahuella máxima 0.17 m.
  Un desnivel sin carrera dentro del lote devuelve `access_run`.
- Medidor, timbre y numeración son piezas ancladas junto al portón peatonal.
  `site.fence` y `site.access_route` dejan de figurar en `pending` de esta
  etapa; cubierta, muebles e ingeniería siguen pendientes.

Véase `../phase5/README.md` para banco, comparaciones, auditoría y límites.
