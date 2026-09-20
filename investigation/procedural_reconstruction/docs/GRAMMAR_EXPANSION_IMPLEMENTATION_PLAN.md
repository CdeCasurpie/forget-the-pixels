# Plan integral de expansión de la gramática urbana

Estado: propuesta de implementación; este documento no modifica el generador.
Base revisada: código actual de `investigation/procedural_reconstruction`, incluidas
las seis familias, prefabs, exportación PBR y experimentos de cuadra/ciudad.
Todas las rutas siguientes son relativas a ese directorio. Las firmas y contratos
marcados como propuestos todavía no existen. Las fases son incrementales y deben
dejar resultados exportables y comprobables antes de continuar.

## 1. Objetivo y reglas del proyecto

Generar edificios y espacios privados variados, coherentes y contenidos en el lote,
con geometría reutilizable y materiales PBR portables. El resultado debe poder
importarse en Blender u otro motor sin necesitar el programa original.

Reglas centrales:

1. El lote catastral no reserva automáticamente espacio para la vereda. La vereda
   pertenece al contexto urbano externo. Una fachada puede coincidir con el lindero.
   Un retiro privado existe solo si lo solicita el programa o está respaldado por datos.
   Esta es una regla del modelo solicitado, no una afirmación normativa universal.
2. El edificio puede tener varios cuerpos, distintas alturas, patios y terrazas.
3. Cada frente puede combinar muro, reja, zócalo, puerta peatonal y portón vehicular,
   o no tener ningún cerco. No cercar todas las aristas automáticamente.
4. La geometría completa, incluidos adornos, hojas abiertas, vegetación y lona,
   debe permanecer dentro del lote según la envolvente adoptada por el proyecto.
5. Diferenciar uso, implantación, lenguaje arquitectónico, nivel de acabados,
   mantenimiento y estado de construcción. Ninguna de esas variables sustituye
   a las demás.
6. Datos explícitos y observados prevalecen sobre reglas, y estas sobre valores
   aleatorios. Registrar origen y confianza; no inventar evidencia fotográfica.
7. No generar variación independiente por triángulo. Las decisiones se toman por
   edificio, cuerpo, fachada, piso, módulo y componente.
8. La generación no necesita Blender. Blender se usa para inspección y renders PBR.
9. Las dimensiones de ejemplos son parámetros de modelado, no certificación
   estructural, de accesibilidad ni de cumplimiento normativo.

## 2. Lectura de las doce referencias

| Ref. | Características visibles | Reglas/contratos a introducir |
| --- | --- | --- |
| 1 | Edificio medio, balcones apilados, una columna de ventanas, reja frontal y jardín | BaySpec con roles distintos; repetición vertical; balcón continuo; jardín tras cerco |
| 2 | Dos pisos, portón y puerta separados, muro coloreado con celosía, coronación con rejas | BoundaryRun por tramos; GateSpec independiente; perforación modular; paleta por zona |
| 3 | Vivienda baja con retiro ajardinado y reja sobre zócalo | Implantación con jardín frontal; muro bajo + barras; corredor de acceso reservado |
| 4 | Escalera exterior conectada a acceso superior, cuerpos de alturas diferentes, cubierta ligera | Grafo de accesos; StairSpec; varios MassSpec; canopy independiente |
| 5 | Fachada al ras, varias puertas altas, rejas ornamentales y cuerpos posteriores más altos | Zero-setback; múltiples accesos; carpintería tradicional; volumen bajo frontal |
| 6 | Comercio al ras, acceso abierto de hojas abatibles, cartel, borde de cubierta ondulado | ShopfrontSpec; DoorLeaf pose; SignSpec; remate de cubierta |
| 7 | Cerco y portón con hierro trabajado, desgaste localizado y vegetación privada | OrnamentProfile; weathering por exposición; GardenSpec y límites de copa |
| 8 | Casona de uso mixto, zócalos de colores distintos, balcón trabajado, cornisa y puertas ornamentadas | Patrimonio estilizado; regiones por local; perfiles de moldura; varios tenants |
| 9 | Comercio de gran abertura y carpintería ancha; posible retiro de acceso | Frente comercial; decisiones de estacionamiento solo con espacio y conexión comprobados |
| 10 | Edificio en obra, pantalla azul translúcida y cerramiento temporal | ConstructionSpec; soportes; lona con tensión, pliegues y holgura limitada |
| 11 | Torre alta, basamento comercial, repetición de balcones y paños ciegos laterales | Podio + torre; piso tipo; LOD y componentes compartidos; medianeras diferenciadas |
| 12 | Vivienda adaptada a comercio, cerco bajo, puerta sencilla, jardín y varios acabados | BoundaryRun bajo; uso mixto sin rehacer todo el edificio; jardín y accesos |

No reproducir autos, peatones, postes o cables como parte del edificio. Pueden
existir en una escena de contexto separada para evaluar escala y composición.
No asumir que el número total de pisos o la profundidad del lote se conoce por
una sola foto. Marcar como hipótesis las partes no visibles.

## 3. Auditoría de la implementación actual

### 3.1 Recorrido real

`layout.propose_building` deriva huella, niveles y fachadas; puede aplicar
`composition.compose_facade`, y luego `families.apply_family` sustituye varios
campos. `grammar.generate_mesh` ensambla muros, prefabs, cubierta y espacio libre
mediante `MeshBuilder`. `export_glb` resuelve imágenes de `MaterialLibrary` y escribe
GLB; `export_obj` escribe OBJ/MTL con UV y factores básicos. Exportar es una acción
separada de generar. `pipeline/contracts.py` contiene contratos, no una integración
completa de fotos → arquitectura detallada.

### 3.2 Limitaciones concretas encontradas

- `layout.py`: usa `parcel.buffer(-0.20)` y retiro predeterminado de 2 m. Esto genera
  separación incluso cuando se necesita fachada al lindero. El buffer no es una vereda,
  pero su resultado visual introduce un espacio no solicitado.
- `BuildingSpecification`: una sola huella y `HeightEstimate`; no hay propiedad ni
  soporte explícito por cuerpo, piso o acceso.
- `families.py`: elección entre seis familias con umbral de pisos, modulación simple,
  puerta usualmente en primera bahía; hay jitter horizontal aleatorio en ciertas ventanas.
  No contiene una política económica ni comprueba usos compatibles con cada implantación.
- `apply_family` sustituye listas enteras. Si se vuelve a aplicar a especificaciones
  editadas, puede perder decisiones previas. Separar propuesta de resolución definitiva.
- `SetbackSpecification`: una superficie y una tipología de cerco para varios lados;
  no describe secuencias de tramos y portones con accesos propios.
- `boundary_and_garden`: acopla cercos, portones y plantas; ubica portón por una regla
  de ancho al extremo. Reserva corredores aproximados frente a puertas, sin verificar
  conectividad completa con el portón.
- `exterior_stair`: prototipo de escalones sólidos y descanso; no verifica llegada a
  una puerta, hueco superior, soporte, gálibo ni conflictos con otros cuerpos.
- `prefabs.py`: catálogo inicial, carteles con alfabeto restringido; faltan carpinterías
  tradicionales, ornamentación por perfiles y puertas con pose y volumen de barrido.
- `MeshBuilder`: recortar contra lote evita fugas, pero puede amputar un componente.
  Contención no demuestra que una escalera, puerta o balcón siga siendo utilizable.
- `validation.py`: valida finitud, índices, áreas, materiales y contención. La cadena
  `topology` del reporte describe el ensamblaje; no es una prueba automática de cierre,
  intersecciones, soportes, conectividad de accesos o UV.
- UV/materiales: existe una transición entre `real_scale_m` y escala de catálogo en
  el exportador. Hacer explícita la unidad UV antes de añadir más superficies y LOD.
- Experimentos `generate_city_block.py` y `step12_city_generation/generate_city.py`
  tienen ensamblaje propio. La unión por nombre de material puede mezclar colores
  distintos llamados `plaster`; consolidar por identidad completa de material.
- No basta comparar familias sobre un solo rectángulo. Faltan casos pequeños,
  irregulares, adyacentes y de altura variable con revisiones en Blender.

## 4. Arquitectura y contratos propuestos

```text
BuildingRequest (lote, contexto, evidencias, preferencias, seed)
    ↓ normalización, validación y prioridades
BuildingProgram (uso + implantación + estilo + acabados + estado)
    ↓ planificación espacial
SitePlan (cuerpos, espacio libre, accesos, cercos, zonas de exclusión)
    ↓ resolución por cuerpo/fachada/piso
BuildingSpecification v4 (todas las decisiones explícitas)
    ↓ compilación determinista
BuildingAssembly (componentes, soportes, transformaciones, materiales, UV)
    ↓ validación + nivel de detalle
MeshData / escena instanciada
    ↓ exportación explícita
GLB + specification.json + validation.json
```

### 4.1 Modelos de datos

Introducir gradualmente `src/domain/architecture.py`; mantener reexportaciones en
`domain/__init__.py` y compatibilidad con `models.py`. Evitar un único archivo enorme.

| Contrato propuesto | Campos mínimos y significado |
| --- | --- |
| EvidenceValue | value, source, confidence, view_ids, locked; permite distinguir observado de supuesto |
| BuildingProgram | use, occupancy, placement, architectural_language, finish_profile, maintenance, construction_state, seed |
| ParcelContext | polygon, holes, CRS, local_origin, neighbor_ids/geometries, explicit_fronts, terrain/base datum |
| EdgeRef | id estable, endpoints, ring_id, orientación; evita perder frentes al normalizar polígonos |
| MassSpec | id, footprint, base_z, roof_z, floor_levels, parent/support_ids, role, roof_spec |
| FacadeSpecV4 | mass_id, edge_ref, exposed_intervals, floor_ranges, bays, openings, material_regions |
| BoundaryRun | edge_ref, start_m, end_m, bottom/top_z, type, thickness, material_slots, modules |
| GateSpec | id, boundary_run_id, interval, pedestrian/vehicle, leaf_count, opening_mode, pose, material, ornament |
| AccessNode/Link | street_entry, gate, building_door, landing, parking; posición, ancho y reservas espaciales |
| StairSpec | origen/destino, footprint, flights, landings, risers, treads, structure, railings, headroom |
| GardenSpec | polygon, soil, plant palette, density, max_height, exclusions, seed |
| ParkingSpec | polygon, stall rectangles, aisle, driveway, gate_id, turning_template, markings |
| ConstructionSpec | stage, scaffold/support graph, screens, fence_runs, completion_by_mass |
| ClothSpec | support_ids, boundary curves, rest grid, sag, fold amplitude, clearance, material, seed |
| OrnamentSpec | style, profile, repeat spacing, depth, max_segments, budget |
| SignSpec | text/asset_id, panel, frame, lighting, local_id; geometría o decal según LOD |
| MaterialBinding | slot, texture_set_id, color_linear, tint_mode, physical_size_uv, rotation, weathering |
| ComponentRecord | id, semantic, mass_id, parent_id, support_ids, local transform, collision class, mesh slice |
| GenerationReport | accepted/rejected features, fallback reasons, tolerances, costs, validation and provenance |

`floor_levels` contiene cotas explícitas; no asumir alturas iguales para local
comercial, lobby y pisos residenciales. `height_reference` especifica si la medida
observada corresponde a losa, parapeto o punto más alto, para evitar sumarle altura
sin justificación. Mantener altura medida original e incertidumbre.

### 4.2 Perfiles de acabados y variación económica

La interfaz puede ofrecer «económico», «estándar» y «premium» como presupuesto de
acabados solicitado. Internamente usar `finish_profile`, no una etiqueta sobre los
habitantes. No inferir ingresos personales por imágenes. La apariencia se descompone:

| Eje | Opciones de ejemplo | Controla |
| --- | --- | --- |
| Acabados | básico, estándar, premium | carpintería, revestimientos, precisión de detalles, profundidad de conjuntos |
| Mantenimiento | cuidado, desgaste ligero, envejecido | máscaras y reparaciones, no posición arbitraria de ventanas |
| Desarrollo | unitario, ampliado por etapas | discontinuidades entre cuerpos y materiales |
| Lenguaje | tradicional, moderno, popular contemporáneo, industrial | proporciones y catálogo de componentes |
| Uso | vivienda, departamentos, comercio, mixto, taller | accesos y distribución por piso |
| Estado | terminado, en construcción, remodelación | pantallas, estructura visible y zonas incompletas |

Una casona ornamentada puede estar envejecida; una vivienda económica puede estar
recién pintada. Un edificio alto no implica necesariamente acabados premium.
No correlacionar automáticamente más color, suciedad, graffiti o rejas con un perfil
económico. Los presets son pesos configurables, no reglas sobre personas.

### 4.3 API objetivo y compatibilidad

Firmas propuestas:

```python
plan = propose_site(request: BuildingRequest, config: GrammarConfig) -> SitePlan
spec = resolve_building(plan: SitePlan, evidence: BuildingEvidence) -> BuildingSpecificationV4
assembly = build_assembly(spec: BuildingSpecificationV4, lod: int) -> BuildingAssembly
mesh = flatten_assembly(assembly: BuildingAssembly) -> MeshData
report = validate_building(spec, assembly, context) -> GenerationReport
export_glb(mesh_or_assembly, output_path, library=library)
```

Mantener `propose_building(...)` como adaptador de conveniencia y `generate_mesh(spec)`
como entrada compatible; documentar qué produce en cada versión. Nunca llamar
`apply_family` otra vez sobre una especificación resuelta salvo solicitud explícita.
Guardar spec resuelta, versión de gramática, versión del catálogo y seed.

## 5. Fases de implementación

### Fase 0 — Congelar evidencia y establecer una línea base

**Archivos:** ampliar `tests/fixtures/architecture/` (nuevo), añadir experimento
`steps/step13_grammar_expansion/` con `run.py`, `cases.py` y `README.md` nuevos.
No renumerar pasos existentes. Leer antes cualquier plan previo en `docs/`.

1. Guardar casos serializados del generador actual: seis familias y una torre.
2. Preparar geometrías de prueba: rectángulo, estrecho, esquina, L, patio interior,
   ángulo agudo, frente segmentado, dos vecinos adyacentes y lote sin frente conocido.
3. Guardar hashes de entradas, número de componentes/triángulos, tiempo, memoria,
   tamaño GLB, materiales y bounds. Comparar en el mismo entorno.
4. No declarar cerrada la forma solo por el texto del reporte actual: comprobarla
   por componente en una copia soldada, preservando la malla original para render.

**Salida:** fixtures y comparación reproducible. **Puerta de salida:** el mismo
input produce la misma especificación y geometría; todo fallo actual queda listado.

### Fase 1 — Contratos v4, procedencia y semillas estables

**Modificar:** `domain/models.py`, `domain/__init__.py`, `procedural_modeling/io.py`,
`specification.py`, `pipeline/contracts.py`. **Crear:** `domain/architecture.py`,
`procedural_modeling/migration.py`, `randomness.py`, `tests/test_architecture_schema.py`.

1. Añadir MassSpec, EdgeRef, BuildingProgram, ComponentRecord y planes de sitio.
2. Migrar JSON v1–v3: un cuerpo con altura/huella originales; conservar source y
   familias, no regenerar sus aberturas. Rechazar versiones desconocidas claramente.
3. Resolver semilla por hash estable de `(seed, lot_id, mass_id, feature_id, purpose)`;
   no usar `hash()` de Python. Separar flujos de ventanas, plantas, materiales y lona.
4. Definir prioridades: locked/observado > inferido > perfil > default. Las opciones
   incompatibles producen diagnóstico, no sustitución silenciosa de evidencia.
5. Reemplazar listas completas solo durante propuesta inicial; la resolución final
   conserva ids y cambios manuales. Validar finitud y dimensiones positivas.

**Pruebas:** migración round-trip, locked opening intacto, cambiar una cortina no
cambia cuerpos ni cercos; orden de procesamiento de lotes no altera cada resultado.
**Visual:** regenerar fixtures migrados y comparar silueta con la línea base.

### Fase 2 — Implantación sin separación artificial para vereda

**Modificar:** `layout.py`, `block.py`, `cadastral_geometry/street_fronts.py`.
**Crear:** `procedural_modeling/site_plan.py`, `geometry_constraints.py`,
`tests/test_site_plan.py`.

1. Normalizar CRS/unidades y trasladar a origen local; conservar origen geográfico.
2. Quitar el buffer universal de 20 cm del modo nuevo. Aplicar retiros explícitos por
   tramo, medidos hacia el interior; no erosionar medianeras por defecto.
3. Modos: `flush`, `front_setback`, `courtyard`, `detached`, `explicit_footprint`.
   En modo explícito respetar huella; no volver a aplicar retiros ya representados.
4. Construir máscaras privadas de ocupación, libre y acceso. Ninguna es «vereda».
5. En fachada al lindero, hacer marcos/revelados hacia adentro. Si un balcón no cabe,
   proponer retranqueo local del cuerpo superior o balcón tipo francés compatible;
   no recortar baranda y dejar una plataforma incompleta.
6. Borde sin vecino no equivale a vía pública. Guardar `exposed` separado de
   `street_front`; usar frente confirmado cuando exista y mantener ambigüedad.
7. Si un retiro divide un polígono, devolver varios candidatos de cuerpo; no
   conectar fragmentos artificialmente. Si no se admite fragmentación, explicar fallo.

**Pruebas:** área de huella flush igual al lote cuando corresponde; lateral
medianero sin franja; frente hacia pista estable al invertir winding; contexto de
vecinos incluye los necesarios, no solo los 10 lotes seleccionados para exportar.
**Visual:** planta coloreada lote/huella/libre/accesos y frente a nivel de calle.

### Fase 3 — Varios cuerpos y alturas en un lote

**Modificar:** `grammar.py`, `specification.py`, `mesh_builder.py`.
**Crear:** `massing.py`, `exposure.py`, `tests/test_multimass.py`.

1. Separar masa principal, anexo bajo, torre, podio y cuarto de azotea. Asignar
   footprint, base_z, roof_z y niveles independientes; conservar altura observada.
2. Si no hay huella observada, generar particiones 2D con restricciones de área y
   ancho mínimo: frente bajo + fondo alto, L con patio, podio + torre, ampliación.
   Puntuar factibilidad, exposición y programa; reintentar con límite explícito.
3. Para masa superior, exigir soporte: su huella debe caer dentro de soportes o
   contar con vigas/columnas resueltas. No permitir volumen flotante por omisión.
4. Calcular exposición por bandas Z. Para cada intervalo entre alturas/niveles,
   obtener unión 2D de masas presentes y su contorno exterior. Etiquetar aristas
   con el cuerpo propietario; eliminar muros interiores coincidentes.
5. En cubierta a cota h, restar huellas de masas que continúan por encima de h.
   Mantener losa de contacto solo si se requiere; no superponer dos tapas coplanares.
6. Diferenciar terraza accesible, techo no transitable y hueco. Parapetos únicamente
   en bordes expuestos que los requieran, no atravesando cuerpos superiores.
7. Evitar booleanas 3D repetidas: resolver en 2D por bandas y extruir. Para masas
   inclinadas/especiales usar superficies explícitas con validación dedicada.

**Pruebas:** dos cuerpos contiguos, uno sobre otro, solape parcial, patio, alturas
distintas, soporte ausente rechazado. Área expuesta analítica y ausencia de caras
coplanares duplicadas. **Visual:** vista explotada, planta por nivel y cuatro lados.

### Fase 4 — Motor de programas y perfiles arquitectónicos

**Modificar:** `families.py`, `layout.py`, `composition.py`.
**Crear:** `programs.py`, `profiles.py`, `data/grammar_profiles.json`,
`tests/test_program_resolution.py`.

1. Separar las seis familias actuales en decisiones reutilizables: uso, implantación,
   ritmo de fachada, planta baja, coronación y accesorios.
2. Añadir perfiles: vivienda compacta, vivienda ampliada, casona, departamentos medios,
   torre residencial, torre mixta, comercio bajo, comercio con patio/estacionamiento,
   taller y obra. Un comercio grande no se deduce solo del área: requiere uso definido.
3. Cada perfil especifica condiciones y pesos, no código duplicado de geometría.
4. Pisos altos repiten bays con roles: ventana, balcón, paño ciego, circulación.
   Planta baja tiene configuración independiente: lobby, locales, vivienda o cochera.
5. Retirar jitter horizontal general como recurso de realismo. Usar alineaciones
   persistentes y excepciones explícitas de ampliación o remodelación.
6. Seleccionar materiales y nivel ornamental con finish_profile; mantenimiento va aparte.

**Pruebas:** misma huella con programas distintos; impedir taller aleatorio en torre
de 20 pisos; cambios de acabado no alteran huella ni accesos. **Visual:** matriz
de programas y perfiles con cámara y luz idénticas.

### Fase 5 — Cercos, muros bajos y portones por tramos

**Modificar:** `SetbackSpecification` mediante migración, `grammar.boundary_and_garden`.
**Crear:** `boundaries.py`, `gates.py`, `tests/test_boundaries.py`.

1. Dividir cada frente en intervalos sin solapamiento. Roles: muro, zócalo con reja,
   reja completa, celosía, puerta peatonal, portón vehicular, abertura libre.
2. Altura independiente por tramo; transición mediante pilar solo donde corresponde.
   Reutilizar el mismo pilar en unión de tramos o esquina.
3. Catálogo: metal de barras verticales, cuadrícula, hierro ornamental, madera sobre
   bastidor, chapa lisa, portón enrollable, corredera y abatible de una/dos hojas.
4. Celosía: celdas perforadas con material entre huecos, no plano opaco con dibujo
   salvo LOD distante. Rejas bajas y sus puertas mantienen la escala del cerramiento.
5. Resolver hoja y barrido: corredera requiere bolsillo lateral; abatible requiere
   arco libre interior. Si no cabe, cambiar mecanismo o rechazar la propuesta.
6. Puerta peatonal y vehicular pueden coexistir, con accesos conectados. El modo
   `none` elimina cerco completo; no deja zócalos fantasma.
7. Materiales separados para muro, coronación, pilar, barras y hojas. Pintura sobre
   ladrillo usa su propio binding; no cambia necesariamente a estuco.

**Pruebas:** cerco bajo, muro+reja, dos accesos, esquina compartida, corredera sin
bolsillo, cerco inexistente y tramo corto. **Visual:** elevación frontal y planta
con volumen barrido; revisar puertas cerradas y abiertas.

### Fase 6 — Planificación de accesos y escaleras expuestas

**Modificar:** `ExteriorStairSpecification`, `grammar.exterior_stair` como adaptador.
**Crear:** `access.py`, `stairs.py`, `tests/test_access_and_stairs.py`.

1. Crear grafo calle→portón→sendero→puerta y puerta inferior→escalera→descanso→puerta
   superior. Nodos con cota, normal de entrada y área de aproximación.
2. Reservar espacio antes de plantar vegetación o añadir coches. Usar navegación
   2D por polígonos libres y conectividad entre cotas mediante escaleras.
3. Para desnivel H y contrahuella objetivo r, probar enteros próximos a H/r;
   fijar r_real=H/n. Huella de escalón, ancho y gálibo son parámetros configurables.
4. Probar escalera recta, L o U. Desarrollo = número de huellas × profundidad;
   descansos aparte, sin superponerlos sobre escalones como sucede en prototipos.
5. Generar zancas o losa inclinada con peldaños, estructura/soportes y barandas;
   una escalera metálica debe permitir vacío bajo los tramos.
6. Reservar paso vertical y hueco de llegada. Una puerta superior debe abrir al
   descanso; retirar/ajustar ventana incompatible antes de resolver la fachada final.
7. Comprobar colisiones 3D con losas, cercos, balcones y cabezas de acceso; si no
   cabe, intentar otra posición autorizada y finalmente registrar rechazo.

**Pruebas:** llega exactamente a cota, no atraviesa losa, descanso accesible, vano
correcto, ancho constante, trayectoria completa y escalera imposible rechazada.
**Visual:** sección lateral, planta, vista bajo escalera y cámara en el descanso.

### Fase 7 — Carpinterías y ornamentación tradicional

**Modificar:** `Opening`, `prefabs.py`, `grammar.opening`.
**Crear:** `openings.py`, `ornaments.py`, `signage.py`, `tests/test_opening_profiles.py`.

1. Separar hueco, revelado, marco fijo, hojas, vidrio, cortina, reja y decoración.
   La ornamentación no debe engrosar obligatoriamente todos los marcos.
2. Puertas: panel simple, cuarterones altos, doble hoja, sobreluz, arco superior,
   moldura clásica, ventilación y herrajes. Perfilar molduras por barrido de secciones.
3. Ventanas: corrediza, abatible, paño fijo, sobreluz, celosía, ventana alta tradicional,
   ventanal corrido y puerta-ventana. Determinar ancho de perfiles por prefab.
4. Arcos: polígono de abertura curvo segmentado, diferencia 2D con muro y jambas
   siguiendo el contorno. No dibujar un arco encima de un hueco rectangular sin resolverlo.
5. Rejas ornamentales mediante curvas muestreadas y tubos de sección configurable;
   volutas, arcos y rombos dentro de una celda repetible. LOD reduce segmentos.
6. Hojas abiertas con pivote real y barrido validado dentro del lote; paso peatonal
   comprobado. Cortinas e interiores simplificados se colocan detrás del vidrio.
7. Carteles: ampliar texto mediante fuente con licencia registrada y extrusión de
   contornos; alternativa decal/atlas para texto pequeño. Manejar huecos de letras.

**Pruebas:** formas cóncavas de letras y marcos, arco sin caras degeneradas, paneles
sin z-fighting, hojas dentro del lote, ornamentación que no tapa acceso. **Visual:**
lámina de prefabs a escala real, primer plano y vista a distancia de calle.

### Fase 8 — Jardines privados y estacionamiento

**Modificar:** `boundary_and_garden`, `MeshBuilder.foliage` como backend inicial.
**Crear:** `landscape.py`, `parking.py`, `tests/test_site_uses.py`.

1. Partir de área libre real: lote menos unión de huellas a nivel de suelo, accesos,
   escaleras, barridos de puertas y zonas de servicio.
2. Jardín solo si está solicitado y cabe. Dividir suelo/jardinera/maceta; mantener
   variantes sin vegetación. No producir una hilera de macetas por defecto.
3. Muestreo de plantas con separación según radio de copa, tamaños jerárquicos y
   semilla por planta. Validar tronco y copa completa, no solo punto de inserción.
4. Setos como bandas dentro del cerco; árboles pequeños solo con volumen disponible.
   Respetar vistas/accesos según el programa y no invadir al vecino.
5. Para estacionamiento, ubicar rectángulos de plazas y pasillo; usar plantillas
   dimensionadas por vehículo de referencia y margen configurable. El área total
   sola no prueba que quepa una plaza accesible.
6. Probar conexión con portón y corredor de giro mediante volumen barrido. Rechazar
   plazas encerradas. Separar ruta peatonal y destino de entrada.
7. Pintura de plazas en decal o geometría con offset controlado. Coches opcionales
   en contexto/preview; no integrarlos obligatoriamente a la malla del edificio.

**Pruebas:** jardín sin retiro no aparece; vegetación no tapa puertas; plaza cabe
pero no tiene acceso debe rechazarse; copas contenidas; lote estrecho sin plaza.
**Visual:** planta de zonas, vista desde puerta y escena con vehículos de referencia.

### Fase 9 — Torres y grandes edificios repetitivos

**Modificar:** `families.py`, `massing.py`, `grammar.py`, `block.py`.
**Crear:** `floor_patterns.py`, `lod.py`, `tests/test_tower_patterns.py`.

1. Definir basamento, pisos tipo y coronación; cada banda tiene programa propio.
2. Pisos tipo comparten módulos, pero pueden variar cortinas y hojas de forma
   controlada sin mover ejes estructurales. Incluir paños ciegos y núcleo aparente.
3. Balcón continuo o por bahía: losa, separación entre departamentos, baranda de
   barras/vidrio y puertas. No dejar losa sin baranda por recorte de parcela.
4. Torre sobre podio con techo-terraza descubierto calculado por diferencia 2D.
5. Mantener submallas compartidas por prefab+material+LOD; nodos con transformaciones.
   Ofrecer flatten para consumidores sin instanciación. No duplicar texturas por piso.
6. Medir 5, 10 y 20 pisos; registrar crecimiento de tiempo/memoria/triángulos y nodos.
   Presupuesto configurable: bajar detalle secundario antes de truncar estructura.

**Pruebas:** coherencia vertical, podio distinto, UV con escala constante al duplicar
pisos, mismos assets compartidos, estructura completa en todos los LOD. **Visual:**
torre desde calle, esquina, fachada ortográfica y skyline junto a viviendas bajas.

### Fase 10 — Estado de obra y lona azul procedural

**Crear:** `construction.py`, `cloth.py`, `tests/test_construction_screen.py`.
**Modificar:** `materials.py`, `grammar.py`, contratos de MassSpec y exportadores.

1. Estados explícitos: obra nueva, ampliación y remodelación. Seleccionar cuerpos y
   tramos afectados; no tapar aleatoriamente todo edificio terminado.
2. Crear soportes/postes/travesaños dentro del lote. La lona se sujeta a esos puntos,
   no flota a una distancia arbitraria del edificio.
3. Primera versión determinista: superficie paramétrica de cuadrícula entre soportes,
   caída gravitatoria aproximada y pliegues de baja amplitud. Reducir amplitud hasta
   satisfacer holguras. No es obligatorio simular física de tela.
4. Si la envolvente admite desplazamiento, combinar caída suave entre anclajes y
   ondulación correlacionada, fijando los bordes sujetos. Sin espacio al frente,
   colocar pantalla sobre soporte retranqueado; no invadir calle para hacer pliegues.
5. Validar todos los triángulos contra lote y cuerpos; detectar autointersecciones y
   limitar pliegues donde cambia la curvatura. Si falla, usar lona plana tensada y
   reportar fallback. No recortar tela de modo que pierda sus anclajes.
6. Material azul apagado configurable, roughness alta y variación leve; combinar
   transparencia con soporte del visor. Tejido fino por normal/alpha, no miles de hilos.
   Añadir costuras/ojales solo en LOD cercano.
7. Añadir cerramiento temporal y portón de obra en tramos explícitos. Estructura
   incompleta opcional, con soportes resueltos y sin mallas flotantes.

**Pruebas:** anclajes inmóviles, cota mínima válida, no atraviesa balcones, lote al
ras, semilla reproducible, fallback estable. **Visual:** contraluz y luz frontal,
mostrar edificio parcialmente visible y silueta desde tres ángulos. Probar GLB en
Blender y el visor destino: transparencia ordenada puede diferir entre motores.

### Fase 11 — Materiales, colores y desgaste localizado

**Modificar:** `materials.py`, `texturing/library.py`, `exporters/glb_exporter.py`.
**Crear:** `texturing/bindings.py`, `texturing/weathering.py`, `tests/test_material_bindings.py`.

1. Mantener color por edificio/cuerpo/local/zócalo/cerco; no solo un `accent` global.
2. Política de tinte explícita: estuco neutralizado pintable, material natural sin
   tinte o combinación autorizada. Evitar oscurecer ladrillo/madera dos veces.
3. Canonicalizar escala UV en metros y aplicar tamaño de repetición una vez. La
   migración conserva escala anterior de specs existentes.
4. Definir máscaras por altura, exposición a lluvia, proximidad a suelo, bajo
   alféizares y juntas. Añadir pintura reparada como región con historial, no ruido global.
5. Atlas/decal o bake por superficie para manchas únicas. Normales, AO y roughness
   no llevan corrección sRGB; comprobar convenios al exportar.
6. Capas painted-metal dieléctricas y metal expuesto diferenciadas; vidrio con IOR/
   transmisión solo donde el formato/visor lo soporte, con fallback documentado.
7. Registrar licencia y hashes de cualquier nuevo asset. Descarga separada del motor.

**Pruebas:** tintes sin alterar normales, material natural conserva color, escala
constante, mapas compartidos, round-trip GLB. **Visual:** mismo edificio cuidado y
envejecido bajo la misma luz; blanco/azul/terracota; comprobar de cerca y desde calle.

### Fase 12 — Integración de cuadra, exportación y aceptación

**Modificar:** `block.py`, `exporters/glb_exporter.py`, `exporters/obj_exporter.py`,
`steps/step10_procedural_generation_test/run.py`, `family_gallery.py`,
`steps/step12_city_generation/generate_city.py` y el experimento de cuadra step10.
**Crear:** `procedural_modeling/assembly.py`, `pipeline/generation.py`,
`tests/test_block_assembly.py`.

1. Unificar los ensamblajes experimentales en una función de producción con id de lote.
2. Fusionar materiales por contenido completo (color, mapas, escala, transparencia,
   roughness, metallic), no solo nombre. Mantener nombres legibles con namespace.
3. Mantener origen por lote y transformaciones de escena; no cocinar coordenadas UTM
   grandes en cada vértice. Convertir Z-up→Y-up una sola vez al exportar.
4. Compartir catálogo e imágenes a nivel de batch. No descargar ni verificar todos
   los recursos repetidamente por cada ventana o cuerpo.
5. Exportar edificios individualmente y escena conjunta; JSON resuelto y validación
   por lote permiten regenerar solo el fallido. Fallo de un lote no borra resultados previos.
6. OBJ declara sus limitaciones; GLB es la referencia PBR. Reabrir ambos para verificar
   bounds/orientación y GLB para mapas, UV, normales y materiales.
7. Suite final con las doce referencias reinterpretadas, diez semillas por tipología
   y lote, más una cuadra heterogénea y una torre de 20 pisos. Limitar la muestra si
   el presupuesto lo exige, registrando exactamente lo que se revisó.

**Puerta de salida:** todas las restricciones duras pasan, cada fallback queda visible
en reporte, comparaciones en Blender revisadas y ninguna regresión bloqueante respecto
de fixtures migrados. No llamar fotorealista al resultado solo por pasar pruebas numéricas.

## 6. Reglas geométricas transversales

### 6.1 Precisión y orientación

- Coordenadas locales en metros, Z vertical, origen/datum explícitos. Tolerancias
  distintas para aritmética, coincidencia geométrica y holgura constructiva.
- Propuesta inicial: epsilon numérico relativo a extensión local, con suelo pequeño;
  configurar umbral geométrico submilimétrico para este dominio. No usar buffers de
  centímetros como sustituto silencioso de corrección topológica.
- Normalizar contorno exterior e interiores con winding coherente. EdgeRef mantiene
  identidad al invertir o segmentar aristas; actualizar `u` de aberturas y componentes.
- Validar y diagnosticar polígonos inválidos. No aplicar buffer(0) sin registrar qué
  cambió ni aceptar silenciosamente pérdida de patios o fragmentos.

### 6.2 Planificar antes de recortar

- Componente completo: construir su envolvente y reservar espacio antes de emitir mesh.
- Muros/suelos pueden intersectarse con su dominio; escaleras, hojas, balcones y plantas
  requieren aceptación completa o fallback. Un recorte no equivale a un diseño válido.
- Colisiones en dos pasos: índice espacial/AABB y prueba detallada de candidatos.
  Para prismas, intersección XY + intervalo Z; para curvas/lonas usar BVH de triángulos.
- Matriz de colisiones permitidas: marco-muro empotrado sí; puerta-cortina no; baranda-
  losa anclada sí; escalera-muro de llegada solo en conexión definida. Evitar rechazar
  todas las intersecciones intencionales del ensamblaje.

### 6.3 Topología, UV y normales

- Componentes sólidos cerrados cuando su rol lo requiere; pantallas/decal/tela pueden
  ser superficies abiertas declaradas. El edificio completo no necesita unión booleana.
- Cierre geométrico se prueba en copia soldada con tolerancia; no soldar costuras UV
  ni bordes duros de la malla de render. Comprobar volumen y winding de cada sólido.
- Triangulación restringida de polígonos con huecos. Una diagonal nunca debe cruzar
  un patio o concavidad aunque su centroide esté dentro.
- UV por cara/origen estable: tangente-altura, profundidad-altura en retornos, base
  métrica sobre cubiertas inclinadas. Barridos usan longitud acumulada del perfil.
- Evitar triángulos UV de área cero donde se use normal mapping. Documentar costuras
  de cilindros y superficies cerradas; tangentes consistentes con normal map.
- Z-fighting: quitar caras internas/coincidentes; offsets pequeños y explícitos para
  decals. No resolver todas las coincidencias empujando objetos fuera del lote.

### 6.4 Límites y degradación controlada

- Reintentos acotados con razones: no cabe puerta, falta soporte, acceso bloqueado,
  radio de giro insuficiente, lote sin frente, UV inválida.
- Si falla un elemento obligatorio, rechazar la propuesta; si es decorativo, omitirlo
  con reporte. No devolver silenciosamente una escalera truncada o un comercio inaccesible.
- Definir presupuesto por lote/cuerpo/LOD. Reducir segmentos de ornamento, follaje y
  herrajes antes que vanos, cuerpos, cercos principales o rutas.
- Guardar estadísticas y fallo mínimo reproducible con spec y seed.

## 7. Protocolo de visualización usando Blender

Crear `steps/step13_grammar_expansion/blender_review.py` como automatización de
Blender, no un renderizador nuevo. Importar el GLB exportado; evaluar ese artefacto,
no solo la malla interna. Guardar versión de Blender y ajustes de escena.

Por caso:

1. Planta ortográfica: lote, cuerpos y alturas, áreas libres, puertas, recorridos,
   barridos, escaleras, plantas y estacionamiento con colores de diagnóstico.
2. Cuatro vistas exteriores de arcilla y una sección de accesos; detectar flotación,
   volúmenes extraños, marcos sobredimensionados y ausencia de soportes.
3. Checker métrico aplicado al GLB real; revisar frente, retornos, arcos, inclinados
   y barandas. No sustituir por color único por triángulo o gráfico UV aislado.
4. Render PBR a altura de peatón, perspectiva y luz exterior; mantener HDRI/sol,
   exposición, color management y cámara fijos entre variantes comparadas.
5. Primer plano de puerta/ventana/cerco y render de conjunto a distancia de calle.
   El detalle no debe dominar la fachada desde lejos.
6. Escena opcional con vecinos/vereda pública separados, para comprobar contexto.
   Medir por separado calidad del edificio y efecto de añadir contexto.
7. Para lona y vidrio: luz frontal y contraluz, revisar transparencia y ordenación.

Artefactos por caso: `spec.json`, `model.glb`, `validation.json`, `manifest.json`,
`plan.png`, `clay.png`, `checker.png`, `street_pbr.png`, `detail_pbr.png`.
Guardar una `comparison.png` por fase y notas humanas: aceptado, problema, corrección.
La revisión debe abrir y mirar imágenes; un archivo generado no prueba calidad visual.
No requiere IA generativa de imágenes: las imágenes de aceptación son renders de malla.

## 8. Matriz mínima de pruebas y criterios

| Área | Positivo | Negativo / fallo que debe detectarse |
| --- | --- | --- |
| Lote | vivienda flush y casa con retiro explícito | franja universal o geometría fuera del lote |
| Cuerpos | podio+torre y casa baja+anexo alto | cubierta interna duplicada, cuerpo flotante |
| Cercos | bajo, alto, mixto y ninguno | portón sobre puerta, pilares duplicados |
| Accesos | calle→portón→puerta→escalera | puerta inaccesible, descanso atravesando losa |
| Puertas | cuarterones, corredera, abatible | barrido invade muro/vecino o arco mal recortado |
| Vegetación | seto y macetas en área disponible | copa invade calle o tapa circulación |
| Aparcamiento | plaza con entrada y giro | cabe rectángulo pero no puede entrar vehículo |
| Obra | lona anclada y tela plana fallback | tela flotante, autointersección, corte de anclajes |
| Materiales | múltiples colores de plaster en cuadra | fusión por nombre borra diferencias |
| UV | checker métrico en todas superficies | degeneración, escala duplicada, seams arbitrarias |
| Reproducibilidad | mismas ids+seed, distinto orden batch | añadir planta cambia todas las ventanas |
| Exportación | GLB reabierto conserva texturas | UV desalineadas, doble rotación o recursos externos perdidos |

Aceptar una fase exige pruebas de comportamiento, no pruebas que únicamente copien
las constantes de la implementación. Usar fixtures pequeños analíticos para áreas,
alturas, conectividad y escala; usar casos de referencia para apariencia.

Presupuestos de rendimiento se fijan tras fase 0 en el equipo real. Informar mediana
y percentil alto de generación/exportación, pico de memoria, imágenes únicas, nodos
y triángulos. No imponer una promesa de tiempo sin medir. La exportación por cuadra
debe evitar una copia de cada textura por ventana o piso.

## 9. Orden de integración recomendado

```text
0 baseline → 1 contratos → 2 implantación → 3 masas → 4 programas
                                           ↓
                         5 cercos → 6 accesos/escaleras
                                           ↓
                       7 prefabs → 8 jardín/parking
                                           ↓
                          9 torres → 10 construcción
                                           ↓
                        11 apariencia → 12 cuadra/exportación
```

UV/validación y renders acompañan todas las fases, no se posponen hasta el final.
La librería de prefabs puede desarrollarse en paralelo después de contratos, pero
su colocación definitiva espera al plan de accesos. Materiales base existentes se
usan desde el principio; fase 11 añade control de acabados/desgaste más elaborado.

Hitos concretos:

- A: vivienda al ras y casa con retiro, sin franja artificial ni pérdida de metadata.
- B: vivienda con dos alturas, cerco mixto y escalera conectada a puerta superior.
- C: casona/comercio con carpintería tradicional, jardín y parking solo si caben.
- D: torre con podio y edificio en obra con lona azul contenida y anclada.
- E: cuadra variada, exportada y revisada en Blender con materiales consistentes.

Cada hito entrega una escena pequeña revisable antes de aumentar combinaciones.
La calidad esperada se evalúa por composición, proporciones, accesibilidad geométrica,
materiales y consistencia visual. «Más compleja» significa más decisiones resueltas y
combinaciones válidas, no simplemente más polígonos o ruido aleatorio.
