# Recorrido archivo por archivo de `src/`

Inventario de **100 archivos Python** (14 875 líneas en la revisión), más los dos archivos de texto de la raíz. Se inspeccionaron contratos, funciones, relaciones de llamada y ramas de selección/validación; la ejecución de la demo recorre 44 módulos, no todas las combinaciones del catálogo.

Las rutas de las tablas son relativas a `house_grammar/src/`. **Theta** señala código utilizado por la ruta actual de solicitudes; **histórico** señala otra API todavía presente, no necesariamente código sin uso.

## 1. Contratos: `domain/` (9 archivos)

| Archivo | Qué entra/sale y responsabilidad |
|---|---|
| `domain/__init__.py` | Reexporta contratos de `models` y `architecture`. Importar desde aquí no selecciona por sí solo el pipeline theta. |
| `domain/theta.py` | Define `ReconstructionRequest`, `ThetaCandidate`, contexto, evidencia, masas/componentes, fachadas, techos básicos, trim y cercos. `decode` convierte JSON en dataclasses con tipos estrictos y rechazo de claves desconocidas. `canonical` serializa determinísticamente y omite varios defaults para compatibilidad histórica. **Es el contrato de entrada central.** |
| `domain/models.py` | Contratos compartidos de catastro, cámara, alturas, aberturas, puertas, proyecciones, materiales, especificación antigua y `MeshData`. Distinguir `Opening` (entrada reutilizada por theta) de `FacadeSpecification` (fachada resuelta) y `MeshData` (salida). UV por esquina y registros de componentes separan topología e identidad de render. |
| `domain/architecture.py` | `BuildingProgram`, `ParcelContext`, `MassSpec`, `SitePlan`, `RoofPlan`, `RoofSurface`, `RoofProp` y especificación V4. Theta reutiliza masas/planes, pero no toma todo `BuildingProgram` como entrada JSON. |
| `domain/balconies.py` | `BalconyControls` y `RailingControls`: anclaje, plataforma, rutas, cierre y baranda. La geometría y los presets viven en modeling. |
| `domain/vertical_members.py` | `MemberDesign` separa forma/estilo del miembro; `VerticalMemberControls` agrega posición en fachada. El diseño es reutilizable en portales, galerías y apoyos. |
| `domain/crowns.py` | `CrownDesign` (silueta/ornato), `CrownControls` (anclaje/hueco) y `EntablatureControls` (recorrido horizontal). Familia de frontón independiente de estilo. |
| `domain/entrances.py` | Contrato de acceso a una abertura: escalones, rampa o paso; cotas, rellano, peldaño y laterales. |
| `domain/roof_details.py` | `RoofDesign`, `EaveDesign`, `RoofAssemblyControls`, `CanopyControls`: separa forma, acabado, construcción, alero y encuentro con frontón. |

## 2. Orquestación pública: `pipeline/` (3 archivos)

| Archivo | Responsabilidad |
|---|---|
| `pipeline/__init__.py` | Exporta `reconstruct`, `generate_from_theta`, `ReconstructionResult` y contratos anteriores. |
| `pipeline/theta.py` | `reconstruct(request)` valida tipos y evidencia → `resolve_theta` → `generate_resolved`. Devuelve solicitud, arquitectura resuelta y malla. `_evidence_value` implementa los selectores estables. **Las imágenes no se procesan aquí.** |
| `pipeline/contracts.py` | Contratos `BuildingRequest/GenerationReport`; `propose_site` y `resolve_building` son stubs que lanzan `NotImplementedError`. No dirigir un nuevo prompt a esa supuesta API completa. |

## 3. Resolución arquitectónica y geometría base (16 archivos)

| Archivo | Responsabilidad y relación con theta |
|---|---|
| `modeling/__init__.py` | Exporta API histórica: `generate_mesh` es alias de `generate_v4_mesh`, además de propuesta y exportadores. Importante evitarlo como entrada del theta actual. |
| `modeling/theta.py` | Núcleo actual. `_complete` fija defaults/rangos; `_masses` deriva masas; `_canonical_masses` crea IDs; `_facade_controls` y overrides validan programas; `resolve_theta` expande decisiones y registra completado; `generate_resolved` emite piezas sin replanificar; `generate_from_theta` combina ambas fases. |
| `modeling/assembly.py` | Convierte `PlanRegion` en polígonos de parcela, aplica cutouts y crea `MassSpec`; rechaza interpenetración. `resolve_supports` genera columnas/losas/sofito y comprueba apoyos. `resolve_zones` asigna suelo libre y sobrantes `unclassified`. |
| `modeling/base_massing.py` | Adaptador Python `compile_base/with_base`: retiros y mordidas (`Setback/Bite`) por piso se compilan a componentes existentes. No agrega un nuevo esquema JSON ni remapea referencias antiguas. |
| `modeling/top_composition.py` | `expand_roof_bodies`: cuerpos sobre azotea se vuelven componentes con base en el techo del padre. El override `RoofBody.trim` no se transfiere actualmente. |
| `modeling/geometry_constraints.py` | Grid catastral, normales, frentes, máscaras de retiro y envolvente que admite vuelo hacia calle. Funciones de reparación/snap se usan en varias rutas; no asumir que theta repara silenciosamente la parcela inválida. |
| `modeling/exposure.py` | Resta oclusión de masas a paredes y techos por bandas Z. `wall_domains` conserva coordenadas de la arista original y devuelve rectángulos visibles; no vuelve a componer vanos por cada fragmento. |
| `modeling/visibility.py` | `patch_domains` intersecta/sustrae rectángulos; `VisibleFacadeBuilder` recorta paneles, cajas, vigas y mallas en el marco original. Permite conservar ejes/IDs aun cuando una pared está parcialmente tapada. |
| `modeling/grammar.py` | Materializador compartido: perfora cascarones de muro; despacha aberturas a puertas/ventanas/prefabs; construye relieve/escaleras. `ZOffsetMeshBuilder` traslada primitivas de banda a Z global. Contiene además generadores históricos `generate_mesh/generate_v4_mesh`, que no son la ruta declarativa theta. |
| `modeling/mesh_builder.py` | Kernel de triangulación y sólidos: `solid`, `box`, `beam`, `panel`, `member_mesh`, `foliage`. Conserva índices de posición dentro de componente, UV por esquina, materiales y jerarquía assembly/component. Triangula concavidades/huecos y recorta al límite apropiado. `finish` entrega `MeshData`; no une todo mediante booleanos. |
| `modeling/detail.py` | `DetailBudget(1/2/3)` controla densidad y microgeometría según vista de manzana/calle/cerca. Algunas piezas nuevas tienen además detalle propio, por lo que no equivale a un LOD universal. |
| `modeling/randomness.py` | `resolve_seed` deriva semilla estable mediante SHA-256 de semilla/lote/masa/elemento/propósito. Theta tiene además `_rng` local para sus propias etiquetas. |
| `modeling/validation.py` | `validate_mesh`: números finitos, índices, áreas, materiales y contención de triángulos/aristas. `component_topology` y `analyze_topology`: conectividad, bordes abiertos/no manifold, orientación y duplicados por componente. Dos diagnósticos distintos. |
| `modeling/version.py` | `MATERIALIZER_VERSION='grammar-v1.1-dev'`; independiente del string histórico de configuración. |
| `modeling/materials.py` | Vocabulario PBR, validación, mezcla por slot, paleta antigua y conversión al material de malla. 16 defaults + 7 slots complementarios. |
| `modeling/boundaries.py` | Define `BoundarySpec`; `generate_boundaries` obtiene tramos libres del perímetro y distingue calle de medianera usando frentes, no posición en Y. Selecciona puerta/cochera del cerco automático. |

### Lectura del núcleo en orden

1. **Entrada:** `domain/theta.py` y `pipeline/theta.py`.
2. **Decisiones:** `modeling/theta.py:resolve_theta`, `assembly.py`, `facade_composition.py` y los resolvers especializados.
3. **Malla:** `modeling/theta.py:generate_resolved` llama a `grammar.facade`, constructores y barridos.
4. **Primitivas:** `mesh_builder.py` concentra índices, triangulación y atributos. No hacer que una IA escriba sus vértices directamente si el propósito es autoría de theta.

## 4. Fachadas y aberturas (11 archivos)

| Archivo | Responsabilidad |
|---|---|
| `modeling/facade_composition.py` | Compositor **theta** puro en coordenadas de pared. Distribuye crujías/grupos, aplica programas y ediciones, valida solapes, agrega orden/motivos/coronas, reutiliza relieve familiar. No recibe fotografía, parcela ni posición mundial. |
| `modeling/facade_program.py` | `FAMILY_RULES` contiene 12 familias. `compose_wall` es compositor usado por V4; `compose_relief` se comparte con theta para balcones, pilastras, bandas, toldos y materiales. Distinguir atributos consultados por cada compositor. |
| `modeling/facade_depth.py` | Materializa desplazamientos locales de pared y retornos laterales. `section_geometry/emit_section` construyen espacio retranqueado, losa y columnas sin inventar una nueva masa. |
| `modeling/facade_top.py` | Valida polilínea de coronación, construye dominio de pared, extiende visibilidad superior y añade moldura. Resta techo en derrames de vanos que cruzan su cota. |
| `modeling/apertures.py` | Contornos rectangle/arch/circle/ellipse, componentes de arco, rellenos abiertos/perforados y rejas simples. La misma forma se usa para perforar muro y rellenar vano. |
| `modeling/window_assembly.py` | Cinco perfiles de ventana; valida dimensiones y compatibilidad de relleno. Genera derrame, moldura por bandas concéntricas, vidrio, montantes, reja recortada y alféizar. No dibuja cortinas. |
| `modeling/door_assembly.py` | Puerta vinculada a hueco: bastidor, hojas paneladas/vidriadas/caladas/tablas/lamas, sobreluz, herrajes, umbral y portal. `layout` divide hueco; `validate_door` limita combinaciones; `build_door` rota hojas alrededor de jambas. |
| `modeling/prefabs.py` | Rellenos tradicionales `slim_window/wood_panel/metal_gate/roller/storefront/louver`; fondo interior/cortinas y reja. `sign_letters` dibuja glifos en relieve; omite texto completo con caracteres no soportados. |
| `modeling/prefabs_facade.py` | Tabla de despacho de proyecciones y constructores de paneles, toldos, balcones, galerías, miradores, bajantes y remates. Algunos nombres antiguos adaptan a motores nuevos de miembros/frontones/aleros. |
| `modeling/ornaments.py` | Plantillas clásicas: molduras huecas, cornisa con dentículos, balaustre torneado y cartel oval. Reutiliza/adapta el motor de miembro para pilastras. |
| `modeling/elevation_sweep.py` | Barre una sección cerrada siguiendo una ruta en el plano `(u,z)` de fachada; produce molduras inclinadas/curvas con volumen. Se usa en frontones y perfiles superiores. |

## 5. Balcones y barandas (4 archivos)

| Archivo | Responsabilidad |
|---|---|
| `modeling/balcony_catalog.py` | Datos de 25 presets: patrón, material, tipo, cierre superior y ornato. `preset` resuelve auto o rechaza una variante fuera de su estilo. |
| `modeling/balcony_resolver.py` | Valida tipo/variante, nivel existente, tramo, envolvente, apoyo, esquinas y conflictos con vanos/otros balcones. Deriva rutas de escalera y busca posiciones de ménsulas libres de aberturas. Devuelve `ResolvedBalcony`. |
| `modeling/balcony_assembly.py` | Emite plataforma, fascia, baranda, ménsulas, jardineras, cubierta, columnas y paneles altos de cajón/galería. Separa función geométrica de la elección de preset. |
| `modeling/railing_assembly.py` | Barandas por rutas 3D: postes verticales aun en pendiente; vidrio, cruces, celosías, paneles, barrotes, cables y balaustres. `lathe` genera balaustres cerrados de revolución. |

## 6. Miembros verticales (6 archivos)

| Archivo | Responsabilidad |
|---|---|
| `modeling/vertical_member_catalog.py` | 25 presets de sección, fuste, capitel, base y taper. Auto elige primera variante del estilo. |
| `modeling/vertical_member_profiles.py` | Secciones rectangulares/redondeadas/achaflanadas/octogonales/circulares/elípticas, acanaladuras cóncavas reales y perfiles de basa/capitel. |
| `modeling/vertical_member_assembly.py` | Valida diseño/dimensiones y construye anillos de fuste, pedestal, basa y capitel. Genera piezas mediante loft y añade ornato. `facade_member` traduce proyecciones antiguas. |
| `modeling/vertical_member_sweep.py` | Une anillos y tapa extremos; recorta mallas contra planos de visibilidad/envolvente y escribe atributos/componentes. Mantiene el perfil en recortes. |
| `modeling/vertical_member_ornaments.py` | Volutas barridas, hojas volumétricas curvas y zapatas de madera. El detalle cambia muestreo, no el nombre del estilo. |
| `modeling/vertical_member_resolver.py` | Resuelve miembros sobre una banda expuesta inequívoca, aplica estilo global, valida materiales/colisiones y calcula transformación local. `u_m` es eje; esquina exige encuentro ortogonal. |

## 7. Frontones y remates (8 archivos)

| Archivo | Responsabilidad |
|---|---|
| `modeling/crown_catalog.py` | Diez familias geométricas y reglas de clasificación de atributos; devuelve familia y motivo auditable. |
| `modeling/crown_paths.py` | Construye rutas métricas de silueta y polígonos de cuerpo; valida proporciones, espesor y moldura. No deforma una malla prefab. |
| `modeling/crown_assembly.py` | Cuerpo grueso, campo rehundido, molduras barridas, perforación real vidriada y ornamentos. Adaptadores `legacy_crown/CrownBuilder` permiten coronamientos tradicionales. |
| `modeling/crown_resolver.py` | Anclaje superior/sobrevano/fachada, estilo y clasificación; verifica soporte visible, perforación, envolvente y ausencia de duplicados/conflictos. Devuelve razón de clasificación. |
| `modeling/trim_profiles.py` | Secciones de las cinco cornisas y definición de hiladas de zócalo. Produce datos de sección/profundidad, no malla. |
| `modeling/trim_sweep.py` | Barrido perimetral cerrado con esquinas compartidas y mitras acotadas; rechaza contornos auto-intersectados o fuera de envolvente. |
| `modeling/trim_resolver.py` | Resuelve recorridos expuestos, patios y frentes; corta zócalos por accesos, combina tramos por cota/diseño y coordina reemplazos por entablamentos/tapas. Produce `ResolvedTrim` y luego los emite. |
| `modeling/entablature_resolver.py` | Divide entablamento en arquitrabe, friso y cornisa; resuelve recorridos comunes y dentículos. Migra bandas de `ArchitecturalOrder` para evitar dibujarlas como placas duplicadas. |

## 8. Techos, accesos y sitio (7 archivos)

| Archivo | Responsabilidad |
|---|---|
| `modeling/roofscape.py` | Planifica techo histórico y dispersa props; construye losas, parapetos y cubiertas básicas. Theta reutiliza `build_roof`, huellas de props y división gable, sin llamar al planificador aleatorio V4 completo. |
| `modeling/prefabs_roof.py` | Once constructores de objetos de azotea y huellas nominales: tanque, antena, ducto, caseta, tendal, etc. Trabajan en XY local y Z absoluta. |
| `modeling/roof_planes.py` | Resuelve superficies mediante planos afines/intersecciones de semiplanos; hip/pavilion usan huella convexa, compound combina lóbulos gable por envolvente superior. Merge evita superposición incorrecta de cubiertas unidas. |
| `modeling/roof_detail_resolver.py` | Reemplaza techo por cubierta detallada, valida forma/acabado, alero, límites y cuerpos bloqueantes; coordina frontones, join_group y props; deriva marquesinas ligadas a fachada. |
| `modeling/roof_assembly.py` | Emite sustrato, vigas, módulos de cubierta, cumbreras/valles, cierres, fascia, canaleta, canes/ménsulas, parapetos y tapas. Presupuesto de 18 000 piezas de recubrimiento; `legacy_eave` adapta aleros antiguos. |
| `modeling/entrances.py` | Desde una puerta existente calcula desnivel, escalones/rampa/paso; comprueba acceso libre y envolvente. Materializa sección lateral extruida, nariz y laterales; no crea puertas. |
| `modeling/site.py` | Construye cercos exclusivamente mediante `modeling/fences.py`, pequeños peldaños automáticos y vegetación en suelo libre respetando puertas/cercos. `build_site` sirve a ruta histórica; theta llama funciones específicas. |

### Cerco vinculado (1 archivo)

| Archivo | Responsabilidad |
|---|---|
| `modeling/fences.py` | Cinco estilos de cerramiento, hojas coherentes de puerta/cochera, postes y bases. Dibuja aros/espirales, paneles, lamas o estacas; incorpora zócalo y jardineras modernas. Los cercos no heredan automáticamente `architectural_style`. |

## 9. Ruta histórica/propuesta y adaptación (8 archivos)

| Archivo | Responsabilidad y diferencia respecto de theta |
|---|---|
| `modeling/layout.py` | `propose_building`: a partir de parcela/frentes/altura produce `BuildingSpecification` con hipótesis repetitivas. Usa estilos `narrow/courtyard/corner`, distintos de los cinco lenguajes actuales. Puede llamar `families.apply_family`. |
| `modeling/composition.py` | Composición antigua de acentos desde vanos existentes; verifica que sus huellas quepan. No confundir su `compose_facade` con el de `facade_composition.py`. |
| `modeling/families.py` | Seis familias de propuesta antigua, paletas y variación sembrada de vanos. El catálogo vigente para theta está en `FAMILY_RULES`, no solo en esta tupla de seis nombres. |
| `modeling/massing.py` | Planificador V4 de seis patrones, selección aleatoria ponderada y posibles adiciones de azotea; cae a prisma si no cabe un patrón. Theta resuelve sus propios patrones con controles explícitos y rechazos; no hereda esos fallbacks. |
| `modeling/programs.py` | Prototipo simple `generate_facade_openings`: vanos residenciales o escaparates comerciales. Su `OpeningSpec` no es el `Opening` completo ni el compositor actual. |
| `modeling/migration.py` | `migrate_to_v4` convierte especificación antigua preservando huella/vanos y prioridad de color. No convierte una solicitud theta en V4; tampoco implica que V4 conserve todos los controles al regenerar. |
| `modeling/io.py` | Lector de especificaciones antiguas schema 1/2/3; reconstruye objetos anidados. No usar para `ReconstructionRequest` 0.3. |
| `modeling/specification.py` | Traduce paquete de reconstrucción y ajuste de altura a especificación neutral LOD1; regulariza pisos y conserva diagnósticos. Escritor de `BuildingSpecification` schema 3. |

### Procesamiento territorial (1 archivo)

| Archivo | Responsabilidad |
|---|---|
| `modeling/block.py` | Lee alturas por objectid, selecciona entorno de una parcela y produce especificaciones antiguas por lote en coordenadas locales. Los lotes sin altura/frentes se reportan como omitidos. No es una cola de estimación IA ni el botón de B. |

## 10. Exportación y texturas (6 archivos)

| Archivo | Responsabilidad |
|---|---|
| `modeling/exporters/__init__.py` | Contenedor de paquete; su docstring dice “Future”, pero hay exportadores reales. |
| `modeling/exporters/glb_exporter.py` | GLB con PBR, conversión Z-up→Y-up y división de vértices solo por costuras de atributos. Authoring conserva identidad por componente; runtime agrupa por edificio/semántica. Conecta imágenes PBR y anota versión. |
| `modeling/exporters/obj_exporter.py` | OBJ/MTL con asignación de materiales, posiciones y UV por esquina; Z-up por defecto, con conversión opcional `y_up=True`. No comparte todas las prestaciones PBR de GLB. |
| `modeling/texturing/__init__.py` | Describe área de texturización futura; no implica que exista rectificación completa de fachada desde fotos. |
| `modeling/texturing/contracts.py` | `FacadeTextureRequest`: contrato reservado para una etapa de textura posterior a geometría. |
| `modeling/texturing/library.py` | Localiza catálogo PBR, comprueba archivos, escalas positivas, dimensiones y hashes cuando hay metadata; registra la convención de normales y cachea imágenes. Carga ORM si está disponible, sin empaquetar canales. Catálogo e imágenes reales son independientes de un nombre de estilo arquitectónico. |

## 11. Geometría territorial: `spatial/` (2 archivos)

| Archivo | Responsabilidad |
|---|---|
| `spatial/__init__.py` | CRS de Barranco, rumbos, ángulos, puntos medios y búsqueda de lote por coordenadas. Usa GeoPandas/PyProj/Shapely. |
| `spatial/street_fronts.py` | Clasifica candidatos a frente público por separación respecto de vecinos, muestreando aristas. Default actual 3/5 muestras libres; no es una verdad cartográfica de calles. Devuelve `StreetEdge`/anotaciones. |

## 12. Adquisición y selección de cámaras (4 archivos)

| Archivo | Responsabilidad |
|---|---|
| `vision/acquisition/__init__.py` | Reexporta construcción/lectura/escritura de paquetes de reconstrucción. |
| `vision/acquisition/acquisition.py` | Descarga panoramas con streetlevel por coordenada/recorrido y registra orientación. La conversión de unidad angular es heurística por magnitud, no calibración garantizada. Separado del motor de theta. |
| `vision/acquisition/reconstruction_package.py` | Une manifiesto de cámaras y parcela del objectid en `ReconstructionInput`, valida imágenes disponibles y persiste schema 2. No confundir con solicitud arquitectónica theta 0.3. |
| `vision/cameras/__init__.py` | Pruebas 2D de visibilidad por rayos, auto-oclusión y ángulo frontal; ranking final por distancia métrica. Devuelve cámaras candidatas y arista objetivo, no una segmentación exacta del edificio. |

## 13. Proyección (6 archivos)

| Archivo | Responsabilidad |
|---|---|
| `vision/projection/__init__.py` | Exporta extracción de franja y cámara rectilínea. |
| `vision/projection/cylindrical.py` | Extrae franja angular de panorama de nadir a cenit con OpenCV; muestreo vertical lineal angular, no cilindro tangente clásico. |
| `vision/projection/rectilinear.py` | `PinholeCamera`, intrínsecos y remapeo de equirectangular 2:1 a perspectiva. Valida FOV/dimensiones y presupone panorama verticalmente orientado. |
| `vision/projection/spherical.py` | Cámara ENU con heading/pitch/roll; proyección a equirectangular, conversión a franja y muestreo/dibujo de aristas de prisma. No elimina líneas ocultas automáticamente. |
| `vision/projection/reprojection.py` | Reproyección de prisma métrico a panorama usando geodesia WGS84; devuelve curvas de píxeles, sin dibujar ni estimar arquitectura. |
| `vision/projection/experiment.py` | Runner offline que consume manifiesto de cámaras, genera perspectivas/comparaciones y metadata. Su ruta default usa un ancestro `src` que conviene revisar antes de reutilizar tras la reorganización. |

## 14. Segmentación y altura (7 archivos)

| Archivo | Responsabilidad |
|---|---|
| `vision/segmentation/__init__.py` | Exporta detector heurístico de borde de techo. |
| `vision/segmentation/roof_boundary.py` | Busca transición ordenada cielo/fachada en una franja mediante coste en Lab; produce fila de corte y separación, no certeza semántica. |
| `vision/segmentation/sam3_backend.py` | Adaptador SAM3: carga diferida de Torch/modelo, requiere checkpoint y CUDA; devuelve máscaras y scores. No se llama desde reconstrucción theta. |
| `vision/segmentation/selection.py` | Selecciona máscaras booleanas que intersectan una banda vertical real; no usa solo bbox y no establece identidad catastral. |
| `vision/estimation/__init__.py` | Reexporta ajuste/regularización de altura y alineación explícita. |
| `vision/estimation/height.py` | Ajusta altura por reproyección multivista robusta (`least_squares`, soft_l1), conserva RMSE y regulariza opcionalmente a pisos. Medición continua separada de convención de piso. |
| `vision/estimation/footprint_alignment.py` | Traslación explícita este/norte de la huella con Shapely, sin mutar fuente. |

## 15. Utilidades y textos de raíz (1 Python + 2 textos)

| Archivo | Responsabilidad |
|---|---|
| `dump_codebase.py` | Recorre `.py/.md`, excluye cachés y produce árbol más contenido. Exportador para lectura; no modifica ni genera theta. |
| `README.md` | Mapa arquitectónico histórico que conserva rutas antiguas (`procedural_modeling`, `gsv_acquisition`, etc.). Para nombres actuales consultar este inventario. |
| `codebase_dump.txt` | Copia agregada del código, susceptible de quedar desactualizada. La referencia de esta revisión son los archivos `.py` individuales, no el dump como fuente normativa. |

## Consecuencia para el futuro flujo IA

El modelo debe escribir **contratos de dominio**; el resolver debe decidir referencias y comprobar compatibilidad; los constructores deben encargarse del detalle repetitivo. Un prompt que enumere funciones internas como si fueran palabras JSON mezclará tres niveles distintos. Usar [campos](REFERENCIA_CAMPOS.md) para estructura, [catálogos](CATALOGOS.md) para elecciones y [prompt](PROMPT.md) para secuencia de autoría.
