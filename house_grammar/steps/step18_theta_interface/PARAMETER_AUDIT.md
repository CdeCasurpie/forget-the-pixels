# Step 18 — auditoría de autoridad paramétrica

Referencia: `grammar-v1.0^{commit}=357a9bad89fd4d6243dc80ce18f00c4986095c49`.
Lectura del flujo efectivo V4, no solamente sus dataclasses. Los nombres de
módulos de ARCHITECTURE.md, ARCHITECTURAL_FAMILIES.md y PROCEDURAL_GENERATION_PLAN.md
son históricos: hoy el motor está en `src/modeling/`. README raíz establece el
objetivo inverso y el freeze. Esta auditoría antecede a la implementación.

## Convenciones de la matriz

Cada fila es una decisión o grupo de campos con idéntica autoridad y consumo.
`code` es relativo a `src/modeling/` salvo prefijo. Las clasificaciones son
exactamente P, THETA, XI, DERIVED, CONFIG, UNUSED, FUTURE. Fuentes originales:
explicit_input, RNG, deterministic_rule, derived_geometry, external_context,
unused/dead, legacy_only. Observabilidad: V visible, P parcial/oculta, N no visual.
Identificabilidad: A alta con cámara/escala; M ambigua; B débil; — no objetivo.
Los límites métricos son del candidato y no certifican habitabilidad normativa.

## Matriz de decisiones

| conceptual_name | code | current_source | data_type / legal_range/categories | dependencies | mesh_effect | observability | identifiability | proposed_classification | reason / implementation status |
|---|---|---|---|---|---|---|---|---|---|
| parcela métrica | geometry_constraints.parcel_polygon | external_context | Polygon simple válido | CRS | límite de masas | P | A con catastro | P | contexto, nunca target visual |
| CRS y origen | domain/architecture.ParcelContext | explicit_input | CRS proyectado/origen XYZ | catastro | georreferencia; no desplaza mesh local | N | — | P | metadatos métricos |
| frentes | geometry_constraints.front_lines | external_context | aristas del anillo | parcela | apertura, retiro, salientes | V | M | P | conservar frentes explícitos; sin fallback sur |
| cámaras, imágenes, fechas | domain/models.PanoramaView | external_context | lista de vistas | captura | ninguno directamente | N | — | P | ObservationContext separado |
| altura externamente fijada | vision/estimation/height | external_context | m positivos, cota de losa | cámara y techo | escala vertical | P | M | P | conflicto con theta debe fallar |
| altura arquitectónica | massing.generate_masses | explicit_input | 2..150 m | pisos | cota principal | V | M | THETA | desconocido se completa explícitamente |
| cantidad de pisos | massing.floor_ladder | derived_geometry | entero 1..50 | altura | niveles | V | A | THETA | independiente de altura; altura de piso derivada |
| altura por piso/niveles | massing.floor_ladder | derived_geometry | altura/pisos | altura,pisos | escalera vertical | P | M | DERIVED | no tres números independientes |
| uso | facade_program.resolve_family; roofscape._weights_for | explicit_input | residential/commercial/mixed | familia desconocida | prior de familia/props | P | M | THETA | uso semántico, nunca inferir renta de residentes |
| occupancy | domain/architecture.BuildingProgram | unused/dead | str | ninguna | ninguno | N | — | UNUSED | no exponer |
| placement | massing.generate_masses | unused/dead | str | front_setback es efectivo | ninguno por sí solo | V | — | DERIVED | flush/retiro se deduce de profundidad |
| language/familia | facade_program.resolve_family | RNG | 10 FAMILY_RULES | uso | vanos, relieve | V | M | THETA | quitar elección aleatoria; prior registrado |
| finish_profile | grammar._facade_body | explicit_input | standard/premium | facade.style | premium elimina zócalo | V | B | THETA | efecto real pequeño; no equivale a nivel económico |
| maintenance | roofscape.plan_roof | explicit_input | premium/otros | densidad props | solo densidad ×0.6 | P | B | UNUSED | descartar etiqueta engañosa; no deteriora paredes |
| construction_state | domain/architecture.BuildingProgram | unused/dead | str | ninguna | ninguno | V | — | FUTURE | lona/obra no implementadas por etiqueta |
| seed arquitectónico | grammar.generate_v4_mesh; massing | RNG | entero | casi todo | identidad mezclada | N | — | UNUSED | sustituir decisiones explícitas; no target seed |
| retiro frontal | massing.generate_masses | explicit_input | >=0 m | frentes | huella | V | M | THETA | rechazar colapso, no fallback silencioso |
| side_setback | domain/architecture.BuildingProgram | unused/dead | >=0 m | ninguna | ninguno | P | — | FUTURE | huellas explícitas permiten describirlo |
| patrón de masas | massing.choose_pattern | RNG | 6 PATTERNS | lote,uso,pisos | silueta/cuerpos | P | M | THETA | autoritativo; no choose_pattern después |
| elegibilidad y pesos de patrón | massing.choose_pattern | deterministic_rule | área/profundidad/uso | parcela | selección legacy | N | — | CONFIG | prior histórico, candidato usa fallback documentado |
| profundidad división frente/fondo | massing._front_rear | RNG | [0.38,0.55] profundidad clamp 5..12 | patrón front/rear | límites de cuerpos | P | B | THETA | front_depth_m condicional |
| pisos de cuerpo bajo | massing._front_rear | RNG | altura menos 1/2 pisos | pisos>=2 | altura posterior/frontal | P | M | THETA | low_floors condicional |
| pisos de podio | massing._podium_tower | RNG | 1/2 | patrón | cota división | V | A | THETA | podium_floors condicional |
| retiro de torre | massing._podium_tower | RNG | 2..4 m legacy | patrón | huella superior | P | M | THETA | upper_setback_m condicional |
| retiro de último piso | massing._stepped_back | RNG | 2.2..3.6 m legacy | patrón | huella superior | V | M | THETA | mismo control; branches excluyentes |
| altura del escalón | massing._stepped_back | deterministic_rule | último piso | altura,pisos | cuerpo superior | V | A | DERIVED | pisos superiores futuros; ahora un piso |
| alcance de mirador | massing._corner_accent | RNG | 4..7 m legacy | dos frentes | cuerpo de esquina | V | M | THETA | corner_reach_m condicional |
| altura adicional esquina | massing._corner_accent | deterministic_rule | +1 piso | patrón | supera altura principal | V | A | DERIVED | altura significa losa principal, no bbox |
| existencia ampliación azotea | massing._rooftop_addition | RNG | Bernoulli .45 | superficie | masa importante | P | B | THETA | explicit masses; nunca XI aunque esté oculta |
| huella/altura ampliación | massing._rooftop_addition | RNG | retiro .25.. .5; altura .8.. .95 piso | roof | masa importante | P | B | THETA | explicit masses, no muestreo implícito |
| huellas explícitas de cuerpos | domain/architecture.MassSpec | explicit_input | polígonos/base/roof/niveles | patrón explicit | geometría | P | M | THETA | unión discriminada, excluye parámetros de patrón |
| roles e IDs de masas | massing._volume | derived_geometry | rol + contador | patrón | identidad de ensamblaje | N | — | DERIVED | referencias por rol/índice canónico, sin UUID |
| soporte de masas | MassSpec.support_ids,parent_ids | unused/dead | tuplas | ninguna | ninguno | P | — | FUTURE | validar soporte geométrico, no exponer IDs decorativos |
| roof_spec de masa | MassSpec.roof_spec | unused/dead | Any | plan_roof ignora | ninguno | P | — | UNUSED | nuevo RoofControl autoritativo |
| holes de parcela | geometry_constraints.parcel_polygon | unused/dead | anillos | Polygon(context.polygon) | se ignoran | P | — | FUTURE | candidato rechaza holes; no prometer patios |
| neighbor_ids/terrain_datum | ParcelContext | unused/dead | tuple/float | ninguna | ninguno | P | — | FUTURE | pendiente soporte desnivel/vecinos reales |
| SitePlan.free_space | domain/architecture.SitePlan | unused/dead | tupla | build_site recalcula | ninguno | P | — | DERIVED | diferencia lote/masas, no input duplicado |
| SitePlan.access_nodes | domain/architecture.SitePlan | unused/dead | tupla | entradas derivadas de puertas | ninguno | P | — | FUTURE | grafo funcional pendiente |
| SitePlan.boundaries | domain/architecture.SitePlan | unused/dead | tupla | generate_boundaries recalcula | ninguno | V | — | UNUSED | candidato emite BoundarySpec explícitos |
| SitePlan.exclusion_zones | domain/architecture.SitePlan | unused/dead | tupla | ninguna | ninguno | P | — | FUTURE | pendiente interfaz de zonas |
| V4.facades y sus campos | grammar.generate_v4_mesh | unused/dead | FacadeSpecV4[] | compose_wall reconstruye | ninguno | V | — | UNUSED | nuevo camino debe consumir entidades reales |
| V4.components y sus campos | grammar.generate_v4_mesh | unused/dead | ComponentRecord[] | emitidos por MeshBuilder | ninguno | N | — | DERIVED | no predecir slices, transformaciones mesh |
| exposición y bandas Z | exposure.calculate_mass_exposures | derived_geometry | segmentos y superficies | masas | oculta paredes/techos | P | A con masas | DERIVED | reutilizado |
| orientación, tangente, normal | grammar._outward_normal | derived_geometry | vectores unitarios | polígono | local→mundo | N | — | DERIVED | reutilizado |
| frontalidad por orientación | grammar._is_front_edge | derived_geometry | cos>.85,dist<30 | P.frentes | composición | V | M | DERIVED | override explícito de fachada puede abrir lateral |
| tolerancia frontal/apron calle | grammar; geometry_constraints | deterministic_rule | .85,30m,1.35m | frentes | salientes admisibles | N | — | CONFIG | constantes congeladas, no norma urbana |
| bay axes | facade_program.bay_axes | deterministic_rule | centros métricos | longitud | columnas de vanos | V | A | THETA | count OR axes; nunca ambos |
| FAMILY_RULES.pitch | facade_program.bay_axes | unused/dead | 2.7..3.8 | usa 3.1 fijo | ninguno | N | — | UNUSED | hallazgo: pitch anunciado no consumido |
| ancho relativo ventana | facade_program._upper_openings | deterministic_rule | ratios familia | pitch | ancho | V | A | THETA | control o entidades explícitas |
| window_h/sill | facade_program | deterministic_rule | metros | familia,piso | alto/cota | V | A | THETA | repetición controlable; excepción por entidad |
| ground programme | facade_program._ground_openings | deterministic_rule | entrance/shopfront/garage/blind | familia | puertas/portones | V | A | THETA | editable; no derivarlo de uso obligatorio |
| upper programme | facade_program._upper_openings | deterministic_rule | repetitive/ribbon/gallery/balcony_column | familia | ritmo | V | A | THETA | familia y entidades resueltas |
| count vs axes | facade_program | derived_geometry | count=len(axes) | modo | mismo efecto | N | — | DERIVED | count es atajo; resuelto guarda axes |
| vano individual kind/u/v/w/h | grammar.facade; prefabs.build_opening | explicit_input | m positivos | fachada | hueco y carpintería | V | A | THETA | lista variable autoritativa |
| frame_width/recess | prefabs.build_opening | explicit_input | m positivos | vano | perfil/profundidad | V | M | THETA | explícito por entidad, defaults de familia |
| prefab | prefabs.build_opening | explicit_input | legacy/slim_window/wood_panel/metal_gate/roller/storefront/louver | vano | geometría carpintería | V | A | THETA | clases existentes |
| mullion_columns/rows | prefabs.build_opening | explicit_input | enteros>=1 | vano | subdivisiones | V | A | THETA | existente |
| grille/pattern | prefabs.build_opening | explicit_input | bool; vertical/grid/diamond | vano | rejas | V | A | THETA | no aleatorizar observado |
| opening.style | grammar.opening | explicit_input | casement/otros | solo prefab legacy | hoja abierta | V | M | THETA | candidato limita combinaciones activas |
| balcony existence/pattern | facade_program._upper_openings | deterministic_rule | every N | familia,piso | balcones | V | A | THETA | control opcional/entidad |
| balcony_depth | facade_program._upper_openings | RNG | .75..1.05 | balcón activo | profundidad | V | M | THETA | no seed arquitectónico |
| balcony railing style | prefabs_facade._balustrade | deterministic_rule | bars/balusters/solid | familia/label | baranda | V | A | THETA | projection.label existente |
| galería depth | facade_program._relief | RNG | 1..1.3 m | upper=gallery | galería | V | M | THETA | control explícito |
| awning depth | facade_program._relief | RNG | .9..1.25 m | awning | toldo | V | M | THETA | control explícito |
| projections kind/u/v/w/h/depth/border/label/material | grammar.projection; prefabs_facade | explicit_input | 16 tipos | fachada | relieve y volúmenes secundarios | V | A/M | THETA | lista explícita; valida ajuste |
| cornice/sill_band/pilasters/shutters/sign/crown | facade_program._relief | deterministic_rule | flags y tamaños familia | familia,pisos,LOD | ornamentos principales | V | A | THETA | defaults derivados; lista explícita reemplaza |
| letras soportadas | prefabs.sign_letters | deterministic_rule | LOCAL TALLER TIENDA | label | letras en relieve | V | A | CONFIG | vocabulario limitado; no OCR general |
| material regions | grammar._cell_finish | explicit_input | rectángulos + slot | fachada | límites cromáticos | V | A | THETA | prioridad orden de lista explícita |
| servicios | grammar.generate_v4_mesh | RNG | Bernoulli .3 | frente ancho>3.5 | AC/tubería | V | M | THETA | presencia explícita, posición legacy derivada |
| horizontal cladding | grammar.generate_v4_mesh | RNG | Bernoulli .2 | frente | juntas | V | A | THETA | stucco/horizontal |
| curtain coverage | facade_program._upper_openings | RNG | .2.. .55 con p=.6 | vidrio | interior | V | M | XI | objetivo de tesis no recupera configuración exacta |
| folds de cortina | prefabs.build_opening | deterministic_rule | coseno y pitch LOD | curtain | microgeometría | V | B | CONFIG | no era RNG; cobertura es XI |
| legacy balcony_window→window | facade_program.compose_wall | derived_geometry | reemplazo | projection balcony | evita duplicados | N | — | DERIVED | no dos fuentes de balcón |
| lateral raw/plastered | grammar.generate_v4_mesh | explicit_input | brick/concrete | no frontal | acabado lateral | P | M | THETA | hidden != nuisance |
| muro concreto/ladrillo y 15mm de inset | grammar._cell_finish | deterministic_rule | columnas .25m cada 4m | brick | relieve estructural aparente | V | M | CONFIG | plantilla V1 |
| planta baja retranqueada .12m | grammar._cell_finish | deterministic_rule | >=3 pisos | niveles | pared | V | M | CONFIG | limitación de primitiva V1 documentada |
| espesor pared .20m | grammar._emit_wall_shells | deterministic_rule | .20m | muro | volumen | P | B | CONFIG | desconocido físicamente; no target inicial |
| losas entre pisos/cornisa automática | grammar._facade_body | deterministic_rule | .15/.20m | niveles | bandas | V | M | CONFIG | sigue heredado incluso ornamented=False |
| stairs dimensiones/posición | grammar.exterior_stair | legacy_only | straight/switchback | fachada+espacio | escalera real | V | M | THETA | entidades opcionales; acceso funcional no garantizado |
| cubierta clase | roofscape.plan_roof | RNG | flat/tile_shed/corrugated | rol/uso/frente | silueta | P | M | THETA | plans explícitos, sin plan_roof aleatorio |
| tile depth | roofscape._tile_surface | RNG | 2.4..3.6 y límites | frente | faldón | V | M | THETA | candidato controla superficie inclinada completa |
| tile slope | roofscape.TILE_SLOPE_DEG | deterministic_rule |20 grados | tile_shed | pendiente | P | M | THETA | 1..45, solo activo en shed |
| eave overhang | roofscape._tile_surface | deterministic_rule | .38m | tile | voladizo | V | M | CONFIG | entes projection eave para override |
| parapet height | roofscape.plan_roof | RNG | .35.. .75, azotea=0 | cubierta | silueta | V | M | THETA | explícito, cero elimina |
| parapet profile | roofscape.build_roof | derived_geometry | none/cap | altura | remate | V | A | DERIVED | altura cero→none |
| props presence/class | roofscape.scatter_props | RNG | 11 BUILDERS | uso/área | tanque/caseta/etc | P | M | THETA | elementos importantes explícitos; lista vacía default |
| props position/rotation/scale | roofscape.scatter_props | RNG | XY,degrees,scale | techo libre | ubicación/volumen | P | B | THETA | no cambiar clases al variar ξ |
| prop interior rebar jitter | prefabs_roof.rebar_cluster | RNG | .55..1.15 | prop rebar | varillas | V | B | XI | seed por prop estable |
| prop plant shape | prefabs_roof.planter; mesh_builder.foliage | RNG | .9..1.1 radial | planta | follaje | V | B | XI | no cambia caseta/tanque |
| density/limits/clearances props | roofscape | deterministic_rule | PROP_* | techo/LOD | sampling legacy | N | — | CONFIG | candidato usa lista, valida contención/solape |
| has_fence/fence_type | boundaries.generate_boundaries | explicit_input | bool,5 estilos | perímetro libre | cerco | V | A | THETA | kind=none elimina; sin bool redundante |
| boundary height | boundaries.generate_boundaries | deterministic_rule | 2.1/2.4/2.6 | estilo | altura | V | A | THETA | altura directa salvo low fijo=1.2 |
| pedestrian gate position/width | boundaries.generate_boundaries | deterministic_rule | max(.25,.15L),1.1m | cerco | acceso | V | A | THETA | runs explícitos para excepciones |
| garage position/width | boundaries.generate_boundaries | deterministic_rule | gate_end+.4,2.9 | longitud | portón | V | A | THETA | valida que cabe; low sin garage |
| exterior perimeter free runs | boundaries.generate_boundaries | derived_geometry | diferencia poligonal | huellas | dónde cabe cerco | P | A | DERIVED | no inventar cerco dentro de masa |
| entrance positions/steps | site.entrance_step | derived_geometry | puertas+umbral | aberturas | accesos | V | A | DERIVED | soporte simplificado, no grafo funcional |
| garden presence | site.plant_garden | deterministic_rule | área libre >.8 | lote,masas,acceso | plantas | V | M | THETA | presencia es control; distribución exacta XI |
| garden positions/radii | site.plant_garden | RNG | jitter .3,radio .30.. .42 | jardín | plantas menores | V | B | XI | no invade accesos definidos |
| foliage jitter | mesh_builder.foliage | RNG | .90..1.10 | plantas | forma orgánica | V | B | XI | substream dedicado |
| main color | materials.appearance_for_style | explicit_input | sRGB 0..1 | plaster/accent | apariencia | V | M iluminación | THETA | no cuantización int255 ni jitter oculto |
| color jitter | materials.appearance_for_style | RNG | ±.018 | RGB | tono | V | B | XI | candidato omite por defecto, material principal estable |
| accent=.72 wall | materials.appearance_for_style | derived_geometry | multiplicación | primary | apariencia | V | A | THETA | override color por slot, default derivado |
| PBR slot/family | materials.resolve_materials | explicit_input | catálogo semántico | región | acabado | V | M | THETA | binding por slot; parámetros microfísicos CONFIG |
| roughness/metallic/opacity/normal/UV scale | materials; exporters | deterministic_rule | rangos PBR válidos | material | render | V | B | CONFIG | biblioteca versionada; no recuperar exactos inicialmente |
| weathering numeric | materials.material_to_dict | unused/dead |0..1 | ningún shader consume | ninguno | V | — | UNUSED | no confundir con decals |
| decals humedad/drips | grammar.generate_v4_mesh | deterministic_rule | cajas .005m | planta baja/vanos | suciedad | V | B | XI | candidato no añade automáticamente, futuro perfil |
| detail budget | detail.DetailBudget | explicit_input |1/2/3 | distancia | repeticiones/shutters/props | N | — | CONFIG | resolver arquitectura en LOD2 y render LOD configurable |
| tolerancias/snap/triangulación/UV | mesh_builder; geometry_constraints | deterministic_rule | constantes V1 | geometría | representación numérica | N | — | CONFIG | jamás θ |
| índices/corner_uv/component IDs | mesh_builder.finish | derived_geometry | arrays/registros | geometría | mesh | N | — | DERIVED | excluidos de resolved theta |
| semillas por stream | randomness.resolve_seed | deterministic_rule | SHA256→uint32 | ξ+propósito | reproducibilidad | N | — | CONFIG | nombres estables; no RNG global |
| layout/families/composition | layout; families; composition | legacy_only | ver contratos V1–3 | API vieja | solo camino viejo | V | — | UNUSED | conservar; nuevo camino no usa apply_family |
| programas anteriores | programs.generate_facade_openings | unused/dead | OpeningSpec | no caller V4 | ninguno | N | — | UNUSED | no conectarlo accidentalmente |
| evidencia/confianza/view IDs | domain.models; EvidenceValue | explicit_input | metadata | observaciones | no geometría | P | — | P | sidecar; unknown distinto de ausencia |

## RNG: cobertura de cada llamada

`audit_rng.py` recorre por AST todas las llamadas random/default_rng/resolve_seed
y métodos de rng del src actual; exporta ubicación, expresión, clasificación y
motivo a `rng_inventory.json` y `rng_inventory.md`. Incluye permutation (no solo
los métodos enumerados en el pedido). Las llamadas de layout/families y de
roof_details/boundary_and_garden/generate_mesh en grammar son legacy_only;
ninguna de ellas se usa para completar θ candidato.

En V4 el mismo RNG compartido consume familia, profundidad de balcón/cortina,
galería/toldo, servicios, cladding y jardín: una ventana extra desplaza decisiones
posteriores. El candidato resuelve arquitectura antes de ξ y usa streams por
propósito para cobertura de cortinas, jardín y microdetalle de props.

## Iteración theta_candidate_0

Vector de BuildingProgram + seed. Compacto, pero muchos campos no actúan y seed
codifica masas/vanos/techos conjuntamente. Una excepción de fachada es imposible;
una vista oculta fuerza inventar valores. Rechazado por falta de autoridad y
entrelazamiento de ξ/θ. Varias vistas no solucionan un contrato inefectivo.

## Iteración theta_candidate_1

Especificación completamente expandida de masas, paredes, aberturas y roofs.
Es fiel y editable, pero obliga a describir demasiados valores, repite
altura/pisos/niveles y liga anotaciones a IDs de segmentos que cambian al cortar
bandas. Una vista deja cientos de nulos; N vistas solo rellenan más entidades.
Rechazado como entrada principal, conservado como representación resuelta.

## Iteración theta_candidate_2 → theta-candidate-v0 (schema 0.1)

Entrada híbrida: height+floors o masas explícitas; patrón discriminado con campos
activos; fachada repetitiva por defecto y overrides por masa/arista geométrica,
incluyendo modo explicit para vanos irregulares. Cámaras/evidencia separadas.
`null`/omisión para unknown, `[]` para ausencia observada. Completar usa priors
deterministas versionados, no seed; se guardan requested+resolved+completion log.
Al expandir, los vanos y proyecciones se vuelven autoritativos y el emisor no
vuelve a componer. Las masas ocultas son θ incierto, jamás nuisance.

Pruebas para aprobar: geometría real cambia con cada intervención activa; ξ
preserva el plan y sus materiales; roundtrip incluye resolved, JSON inválido o
estado inactivo falla; GLB verificable y regresión source-mesh del freeze.

## Límites conscientes para Step 19

No hay θ-v1 congelado. Holes/patios, terreno no plano, colisiones funcionales de
escaleras, parking, perfiles curvos habitables y construcción con lona quedan
FUTURE. Una fachada explícita que cruza un límite de exposición necesita dividir
sus entidades; el adaptador debe rechazar pérdidas silenciosas. La gramática V1
conserva espesores, losas y detalles de prefabs como CONFIG. En vistas únicas,
altura sin escala, profundidad posterior y cubierta oculta no son identificables
unívocamente: guardar unknown y completed, no supuesto observado.
