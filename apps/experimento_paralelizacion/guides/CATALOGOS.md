# Catálogos, palabras clave y aspecto

Complemento de [Cómo escribir un theta](README.md). Las descripciones visuales se basan en perfiles, materiales y constructores del código; son **la apariencia implementada**, no definiciones históricas exhaustivas. Los nombres de archivos de las muestras no son necesariamente valores válidos de un campo.

## 1. Los cinco estilos

Se usan en `architectural_style` y en distintos controles locales. Escribir `clasico` sin tilde.

| Estilo | Ventana/moldura implementada | Otras señales del catálogo |
|---|---|---|
| `republicano` | Perfil con varios escalones y transiciones de relieve; moldura articulada | Hierro vertical con aros, pilastras de panel rehundido, cornisas escalonadas, puertas de cuarterones |
| `barroco` | Perfil ondulante muestreado, más curvas | Volutas, follaje, columnas torsionadas, ménsulas y frisos calados |
| `clasico` | Moldura escalonada de geometría ordenada | Balaustres pétreos, órdenes toscano/dórico/jónico/corintio, frontones |
| `madera` | Perfil de carpintería escalonado, material `wood` | Postes ochavados/torneados, cruces, celosías y balcones cajón |
| `moderno` | Perfil poco profundo, casi plano | Barras finas, vidrio, lamas horizontales, prismas/cilindros sin capitel |

El estilo **no fija por sí solo** color, cantidad de pisos, forma de ventana ni dimensiones. En `generar_ventanas.py` las muestras combinan estilos con anchos/profundidades distintos; esos ajustes son del script, no defaults generales del estilo.

## 2. Familias de composición (`theta.family`)

Fuente: `modeling/facade_program.py:FAMILY_RULES`, consumida por `facade_composition.py`.

| Familia | Lectura visual/predeterminados relevantes |
|---|---|
| `quiet_house` | Vivienda sobria: ventanas relativamente pequeñas, rejas, puerta inicial, cornisa discreta. |
| `ribbon_windows` | Ventanas anchas y bandas de antepecho, lectura horizontal. |
| `balcony_apartments` | Ventanas bajas/altas de acceso a balcón, balcones repetidos y base de piedra. |
| `mixed_use` | Planta baja con escaparates y superiores residenciales; toldos y letreros solo si se solicitan explícitamente. |
| `workshop` | Primer vano de cochera enrollable, ventanas más altas/pequeñas y concreto; no añade `TALLER`. |
| `brick_courtyard` | Vivienda con ladrillo en base y franja de coronación; no crea un patio automáticamente. |
| `republicano` | Proporciones altas, rejas, pilastras, bandas, cornisa denticulada y balcones; contraventanas solo explícitas. |
| `galeria_madera` | Galería continua en superiores y base comercial; toldos/contraventanas solo explícitos. |
| `esquina_comercial` | Escaparates, balcones de parapeto sólido y pilastras; no crea esquina, toldo ni letrero automáticamente. |
| `quinta` | Ventanas moderadas con rejas; contraventanas solo explícitas. No distribuye varias viviendas por sí sola. |
| `neoclasico` | Vanos altos relativamente estrechos, pilastras y cornisa denticulada prominente; no genera `BCP`. |
| `neoclasico_esquina` | Variante proporcional del anterior con cornisa mayor; la esquina depende del contexto/masas. |

Las reglas familiares aún pueden añadir ornamentación no observada, pero ya no rótulos, toldos ni contraventanas. Para reconstrucción fiel, seleccionar `projections=[]`, `material_regions=[]` y construir solo los elementos vistos. Arcos de las reglas V4 no se trasladan automáticamente al compositor theta; ver [guía](README.md).

## 3. Volúmenes, regiones y soportes

| `massing.pattern` | Forma | Controles particulares |
|---|---|---|
| `single_block` | Un prisma de varios pisos | `front_setback_m` |
| `stepped_back` | Cuerpo inferior y último piso retirado | `upper_setback_m`, ≥2 pisos |
| `podium_tower` | Podio ancho con torre retirada | `podium_floors`, `upper_setback_m` |
| `front_tall_rear_low` | Frente alto y cuerpo posterior bajo | `front_depth_m`, `low_floors` |
| `front_low_rear_tall` | Frente bajo y cuerpo posterior alto | Los mismos |
| `corner_accent` | Mirador/cuerpo alto en encuentro de dos frentes | `corner_reach_m`, ≥2 frentes y ≥2 pisos |
| `explicit` | Huellas y cotas suministradas | `theta.masses`; sustituye altura/pisos |
| `composition` | Regiones relativas al catastro | `massing.components`; se infiere si hay componentes |

No existe `auto` como patrón válido de theta: `null` pide completado. `auto` sí aparece en el generador histórico `massing.py`.

Otras palabras:

- `MassComponent.kind`: `enclosed` (cerrado), `open` (losas/apoyos).
- `PlanRegion.fit`: `parcel` (intersección), `rectangle` (rectángulo completo validado).
- `PlanRegion.width_reference`: `parcel` (proyección total de parcela), `edge` (longitud del frente).
- `SupportControls.kind`: `bearing` (apoyo sobre volumen inferior), `columns` (columnas), `cantilever` (vuelo limitado; apoyo ≥25% del área).
- Orientaciones de bandas/zonas: `front`, `back`, `left`, `right`, `all`, relativas al marco de su componente.

## 4. Vanos: forma, relleno y moldura son decisiones separadas

`Opening.kind`: `window`, `door`, `gate`, `balcony_window`.

| `shape` | Cómo se ve | Condición |
|---|---|---|
| `rectangle` | Rectángulo | Sin `arch_rise_m` |
| `arch` | Jambas rectas y coronación curva | `arch_rise_m` >0 y menor que altura; default proporcional |
| `circle` | Óculo circular | Ancho = alto, sin `arch_rise_m` |
| `ellipse` | Óvalo | Ancho/alto independientes, sin `arch_rise_m` |

Puertas vinculadas solo permiten rectángulo/arco. `OpeningProgram.shape` permite únicamente rectángulo/arco; círculos/óvalos requieren aberturas explícitas o ediciones completas.

| `prefab` | Aspecto/función |
|---|---|
| `catalog` | Valor por defecto; ventana/puerta del catálogo vinculado. |
| `legacy` | Alias de serialización presente en las muestras originales; no ejecuta un constructor antiguo. |
| `slim_window`, `storefront` | Alias de vidrio de ventana normalizados a catálogo; no conservan sus prefabs antiguos. |
| `open` | Ventana de catálogo sin vidrio ni divisiones. En puertas es alias de puerta calada con sobreluz abierta. |
| `wood_panel`, `metal_gate`, `roller`, `storefront` (en puertas) | Alias de lectura con intención material: tablas/madera, paneles/metal, lamas/metal, vidriada. Se normalizan a `door` de catálogo. |
| `louver`, `screen` y nombres desconocidos | Sin equivalente en el catálogo; se rechazan. |

**Despacho único** (`grammar.opening` → `opening_catalog`): window/balcony_window → `window_assembly`; door/gate → `door_assembly`. Los emisores de prefabs y aberturas curvas antiguos están retirados.

`frame_profile`: uno de los cinco estilos; auto hereda estilo global y, sin este, usa moderno. `frame_width_m` ensancha el marco dentro del vano; `frame_depth_m` determina su relieve; `recess_m` hunde el relleno. `sill=true` añade alféizar siguiendo el contorno inferior.

`mullion_columns/rows`: divisiones del vidrio. `grid_spacing_m` selecciona subdivisión adaptativa en ventanas vinculadas. `grille=true` añade protección independiente con `grille_spacing_m` y `grille_pattern`:

- `vertical`: barras verticales.
- `grid`: retícula ortogonal.
- `diamond`: rombos/diagonales.

`Opening.style` no selecciona el catálogo. Las hojas abatidas, cortinas y ornamentos del fallback antiguo no se generan; usar los controles explícitos de los ensambles vinculados.

Muestras existentes: [catalogo_ventanas](../../steps/step23_fresh_theta/catalogo_ventanas): 5 perfiles × 4 formas × con/sin reja = 40 variantes generadas por el script.

## 5. Puertas y portones vinculados (`Opening.door`)

`model`: cinco estilos o `auto`. `leaves`: 0 automático (dos desde ancho libre 1.35 m), 1 o 2. `opening_angles_deg`: un ángulo por hoja, 0–110°, apertura hacia afuera.

| `construction` | Aspecto |
|---|---|
| `auto` | Republicano/barroco/clásico → panelled; madera → boards; moderno → louvers |
| `panelled` | Bastidor con cuarterones rehundidos y molduras; cantidad adapta al tamaño |
| `glazed` | Paños de vidrio dentro de bastidor |
| `grille` | Hoja calada de reja |
| `boards` | Tablas verticales con pequeñas juntas |
| `louvers` | Lamas horizontales |

`portal`: `none`, `pilasters` (pilastras laterales), `columns` (columnas). `portal_member` personaliza esos soportes. `cornice` añade remate sobre el portal. `transom_height_m` reserva una sobreluz; `transom_infill=glass/open`; `transom_grille` añade reja en ella.

`grille_pattern`: `auto`, `vertical`, `grid`, `rings`, `scrolls`. Auto escoge volutas barrocas, aros republicanos o barras en los otros estilos. `leaf_grille` tiene efecto en construcción vidriada/calado, no convierte por sí solo una hoja panelada en reja.

Materiales de este constructor: `wood`, `metal`, `frame`, `stone`, `plaster`, `concrete`, `brick`, `glass`, `accent`; hoja/marco admiten `auto`. No todo slot de materiales es válido aquí.

Muestras: [catalogo_puertas](../../steps/step23_fresh_theta/catalogo_puertas), 5 estilos × rectángulo/arco × puerta/portón = 20. Los portales y sobreluces concretos de esas muestras los decide `generar_puertas.py`.

## 6. Balcones: 25 variantes

Fuente: `balcony_catalog.py`. `variant="auto"` elige la **primera** variante del estilo, no una inferencia visual.

| Estilo | `variant` | Apariencia y tipo recomendado/exigido |
|---|---|---|
| republicano | `iron_vertical` | Hierro con barras verticales; projecting |
| republicano | `iron_rings` | Barras y aros superiores; projecting |
| republicano | `turned_gallery` | Galería con balaustres torneados de madera; gallery/terrace |
| republicano | `open_lattice` | Galería con retícula de madera y franja superior calada; gallery/terrace |
| republicano | `sober_box` | Cajón de madera, paneles inferiores y vidrio arriba; box |
| barroco | `scroll_iron` | Hierro con espirales pareadas; projecting |
| barroco | `bowed_iron` | Barras de hierro abombadas hacia fuera; projecting |
| barroco | `ornate_balusters` | Balaustres de piedra y detalles ornamentales; projecting |
| barroco | `ornate_box` | Cajón panelado con vidrio y ornato calado; box |
| barroco | `fretwork_gallery` | Torneados de madera y friso calado; gallery/terrace |
| clasico | `single_baluster` | Balaustre pétreo de una panza; projecting |
| clasico | `double_baluster` | Balaustre pétreo de doble ondulación; projecting |
| clasico | `mixed_parapet` | Alterna paneles macizos y balaustres; projecting |
| clasico | `geometric` | Baranda metálica de cruces; projecting |
| clasico | `column_gallery` | Galería con balaustres y columnas toscanas por defecto; gallery/terrace |
| madera | `vertical_timber` | Palos verticales de madera; projecting |
| madera | `turned_timber` | Balaustres torneados de madera; projecting |
| madera | `cross_frames` | Bastidores de madera con aspa X; projecting |
| madera | `lattice_panels` | Celosía diagonal de madera; projecting |
| madera | `continuous_box` | Cajón con paneles abajo y celosía arriba; box |
| moderno | `slim_vertical` | Barras verticales finas metálicas; projecting |
| moderno | `horizontal_rods` | Varillas horizontales; projecting |
| moderno | `glass_posts` | Vidrio con postes y abrazaderas; projecting |
| moderno | `glass_channel` | Vidrio sin postes, sujeto por canal inferior; projecting |
| moderno | `louver_parapet` | Zócalo sólido y lamas horizontales; projecting |

`kind` no se cambia automáticamente al elegir variante:

- `projecting`: plataforma saliente.
- `terrace`: baranda sobre techo/piso existente; `slab=false`, comprobar `support_mass`.
- `juliet`: protección casi en el plano de la abertura, sin plataforma; `slab=false`.
- `gallery`: balcón continuo con columnas; `cover=true` añade cubierta.
- `box`: cajón cerrado en sus tres lados; necesita variante de cajón y baranda activa.
- `stair`: baranda derivada de una escalera existente por `stair_index`; `slab=false`.

Patrones completos de `railing.pattern`: `auto`, `vertical`, `rings`, `turned`, `grid`, `panels`, `scrolls`, `bowed`, `vase`, `double_vase`, `mixed`, `cross`, `lattice`, `horizontal`, `glass`, `frameless`, `louvers`, `cables`. `cables` dibuja hilos horizontales finos y tensores; los demás corresponden a la tabla.

Controles de aspecto: `brackets` ménsulas inferiores; `fascia` borde moldurado; `cover` cubierta; `curved_front_m` curvatura del frente; `corner_return_m` vuelta por esquina ortogonal; `planters` jardineras; `column_member` diseño de postes. `sides` combina `left/front/right`. `path` es ruta local de baranda sobre soporte existente: no sintetiza una losa ni una escalera.

Muestras: [catalogo_balcones](../../steps/step23_fresh_theta/catalogo_balcones).

## 7. Pilastras, columnas y postes: 25 variantes

Fuente: `vertical_member_catalog.py`. Los diseños se reutilizan en `vertical_members`, portales de puertas, galerías, apoyos y secciones retranqueadas.

| Estilo | `variant` | Apariencia implementada |
|---|---|---|
| republicano | `smooth_moulded` | Fuste rectangular liso, base y capitel moldurados |
| republicano | `recessed_panel` | Pilastra con panel rehundido longitudinal |
| republicano | `restrained_fluted` | Pilastra rectangular con acanaladuras |
| republicano | `rusticated` | Fuste de relieve modulado tipo almohadillado |
| republicano | `portico_column` | Columna circular con estrechamiento hacia arriba |
| barroco | `scroll_pilaster` | Panel rehundido y capitel con volutas |
| barroco | `leaf_pilaster` | Pilastra lisa con hojas en capitel |
| barroco | `salomonic` | Fuste circular torsionado y capitel compuesto |
| barroco | `estipite` | Sección rectangular de anchura cambiante/invertida y volutas |
| barroco | `composite_column` | Columna circular acanalada, hojas y volutas |
| clasico | `tuscan` | Circular lisa, base y capitel sobrios |
| clasico | `doric` | Circular acanalada, capitel dórico; sin base por defecto |
| clasico | `ionic` | Circular acanalada, capitel de volutas |
| clasico | `corinthian` | Circular acanalada, capitel de hojas |
| clasico | `panel_pilaster` | Rectangular con panel rehundido |
| madera | `chamfered_post` | Poste de esquinas achaflanadas, sin base/capitel |
| madera | `turned_post` | Poste circular torneado |
| madera | `octagonal_post` | Poste octagonal de sección constante |
| madera | `joinery_pilaster` | Pilastra rectangular con panel de carpintería |
| madera | `saddle_post` | Poste achaflanado con zapata ensanchada superior |
| moderno | `plain_prism` | Prisma rectangular liso sin base/capitel |
| moderno | `plain_cylinder` | Cilindro liso sin base/capitel |
| moderno | `oval_column` | Columna elíptica lisa |
| moderno | `grooved_pilaster` | Rectangular acanalada, sin capitel ornamental |
| moderno | `tapered_column` | Sección redondeada que se estrecha marcadamente |

`section`: `auto`, `rectangle`, `rounded`, `chamfered`, `octagon`, `circle`, `ellipse`. Circular exige ancho=profundidad; salomónica requiere circular/elíptica; panel rehundido requiere rectangular/achaflanada/redondeada.

`placement`: `attached` adosada, `embedded` embebida según `embed_ratio`, `freestanding` separada con `offset_m`, `corner` en extremo de esquina ortogonal. **Aquí `u_m` es el eje del miembro**, no su borde izquierdo.

`base/capital` activan o anulan partes; `collar/abacus` controlan collarín/ábaco; `base_profile=auto/attic/simple/minimal`; `pedestal_m` añade pedestal; `taper` estrechamiento; `entasis` abombamiento del fuste; `turns` vueltas; `flute_count` acanaladuras; `ornament` activa hojas/volutas/zapata; `detail=1/2/3` muestreo geométrico.

Muestras: [catalogo_pilastras](../../steps/step23_fresh_theta/catalogo_pilastras).

## 8. Frontones y coronamientos

`theta.crowns[].design.family` permite estas 10 formas y `auto`:

| Familia | Silueta |
|---|---|
| `triangular` | Dos pendientes rectas que se encuentran en ápice |
| `segmental` | Arco circular rebajado; flecha ≤ mitad de ancho |
| `semicircular` | Medio círculo; altura exactamente ancho/2 |
| `stepped` | Hombros escalonados y meseta central |
| `stepped_segmental` | Escalones laterales con arco central |
| `curved_pointed` | Dos ramas curvas que llegan a una punta |
| `concave_shoulders` | Hombros cóncavos que ascienden a bloque central |
| `compound_curve` | Curvas suaves con cambios de curvatura y bloque central |
| `broken` | Dos ramas separadas, centro abierto |
| `rectangular_attic` | Ático central rectangular elevado sobre hombros bajos |

Clasificación automática, en orden: `open_center` → broken; `concave_shoulders` → homónimo; `stepped` + curved/mixed → stepped_segmental, si no stepped; `central_block` → rectangular_attic; finalmente `silhouette=angular/curved/pointed/mixed` → triangular/segmental/curved_pointed/compound_curve. `family` explícita prevalece.

No confundir familia de frontón con estilo: un frontón triangular puede tener molduras modernas o republicanas.

`anchor`: `wall_top`, `opening_top`, `facade`. En sobrevano `opening_index` centra automáticamente el frontón respecto a la abertura; `base_m` desplaza su base.

`aperture`: `none`, `oculus` (óvalo/círculo vidriado), `roundhead` (vano con arco), `pointed` (vano apuntado). Requiere frontón sobre muro y espacio interior; `broken` no admite ese hueco central. Es una perforación real del cuerpo, con derrame y vidrio.

`ornament`: `none`, `keystone` (clave central), `cartouche` (cartela oval), `volutes` (espirales laterales), `dentils` (dentículos).

`thickness_m` da cuerpo; `recess_m` hunde el campo; `moulding_width_m` y `projection_m` dimensionan moldura; `base` añade cornisa inferior; materiales separados para cuerpo, campo y moldura.

Muestras: [catalogo_frontones](../../steps/step23_fresh_theta/catalogo_frontones), diez familias y seis composiciones de `generar_frontones.py`.

## 9. Cornisas, zócalos, entablamentos y silueta continua

- `trim.cornice.profile`: cinco estilos o `auto`. Perfiles continuos en perímetro: moderno rectangular; madera escalonado; clásico/republicano moldurado; barroco curvilíneo.
- Cornisa: `anchor=wall_top/parapet_top`, `scope=exposed/street`, `courtyards`, `offset_m`, altura/proyección/material. Parapet_top exige parapeto.
- `trim.plinth.design`: `smooth` superficie lisa; `horizontal_joints` hiladas con juntas horizontales; `stepped` tres alturas de relieve; `blocks` hiladas con juntas verticales alternadas.
- Zócalo: altura, relieve, altura de hilada, ancho de bloque y junta. Se corta en accesos y continúa en esquinas.
- `entablatures`: arquitrabe inferior + friso + cornisa, `anchor=wall_top/absolute`, `scope=street/exposed`, `ornament=none/dentils`. `mass_refs=[]` selecciona masas cerradas.
- `FacadeControls.order`: pilastras `none/group_boundaries/bay_boundaries/explicit`, ejes, pares por crujía, zócalo, bandas y alturas de entablamento/cornisa.
- `FacadeControls.crowns`: perfiles simples `triangular/stepped` por intervalo `u`.
- `FacadeControls.top_profile`: polilínea `(u, elevación)` de la pared por encima de su coronación; hasta 64 puntos, de u=0 a u=1; elevaciones 0–4 m; repetir u permite tramos verticales. Se puede perforar con vanos. Alternativo a `facade.crowns`.

Muestras: [catalogo_remates](../../steps/step23_fresh_theta/catalogo_remates).

## 10. Techos: losa estructural y catálogo único de cubiertas

### Techo básico (`roof` y `roofs`)

`kind=flat` (o `null` para completar a plano) es la única base permitida: losa estructural, parapeto 0–2 m y objetos. `slope_deg` debe ser `null`. Lo mismo rige para `component.roof`, `roof_bodies[].roof` y `roofs`. Las cubiertas inclinadas y corrugadas se escriben exclusivamente en `roof_assemblies`; los valores básicos antiguos se rechazan con instrucciones de migración. Véase [CATALOGO_TECHOS.md](../../../CATALOGO_TECHOS.md).

### Cubierta detallada (`roof_assemblies[].design`)

| `form` | Apariencia |
|---|---|
| `flat` | Plano horizontal |
| `shed` | Una pendiente |
| `gable` | Dos pendientes con cumbrera |
| `hip` | Pendientes hacia los bordes de una huella convexa |
| `pavilion` | Pabellón sobre huella convexa; comparte el algoritmo de hip en esta implementación |
| `band` | Banda inclinada de tejas con resto plano |
| `compound` | Unión de lóbulos rectangulares de cubierta, para plantas L/T |

`covering`: `none` sin acabado añadido; `curved_tile` tejas curvas; `flat_tile` tejas planas; `corrugated` plancha con ondas; `panel` panel continuo; `slats` listones abiertos tipo sol y sombra.

`construction`: `solid` sustrato continuo, `frame` estructura abierta; tejas requieren solid. `detail=light/medium/full` cambia representación/densidad del recubrimiento. `slope_deg` se valida 1–45° incluso si la forma plana no usa esa inclinación. `rotation_deg` orienta los planos en XY; `ridge_fraction` mueve la cumbrera; `tile_width_m/tile_length_m/overlap_m` controlan módulos.

En shed/gable, `rotation_deg` es la dirección XY ascendente del primer faldón, desde +X en sentido antihorario; la cumbrera gable es perpendicular. No es un ángulo respecto de la calle ni del norte geográfico. Un recorte por cuerpo superior/frontón conserva los planos. Un `RoofBody` se referencia por `<id>:0`, igual que otro componente: no necesita un campo design adicional.

`eave.kind`:

| Valor | Aspecto |
|---|---|
| `auto` | republicano→profiled, barroco/clasico→cornice, madera→exposed, moderno→clean |
| `clean` | Borde sobrio; fascia depende de su booleano |
| `closed` | Alero cerrado inferiormente |
| `exposed` | Canes/vigas visibles |
| `profiled` | Canes con perfil escalonado |
| `braces` | Tornapuntas diagonales |
| `curved` | Ménsulas curvas |
| `cornice` | Cornisa perfilada continua |

`overhang_m`, `spacing_m`, `beam_width_m/height_m` dimensionan alero; `fascia` tabla frontal, `soffit` cierre inferior, `gutter` canaleta.

`cap`: `none`, `flat`, `bevel`, `pitched`, `moulded`, `metal`: coronación de parapeto plana, biselada, inclinada, moldurada o chapa. `cap_drip` solo con metal. Parapeto solo en cubierta plana.

`junction=none/behind/gable`: independiente, detrás de frontón, o encuentro estructural con frontón triangular de todo el ancho. Requiere `crown_ref` en los dos últimos. `join_group` une cubiertas contiguas a igual cota y acabados compatibles. `props_mode=preserve/auto/off`: conserva objetos, distribuye objetos automáticamente (solo plano), o los quita.

`canopies` usa `RoofDesign` con `form=flat/shed`, dimensiones de tramo y vuelo; `posts` añade apoyos. Es distinto de `FacadeProjection.kind=canopy`.

Muestras: [catalogo_techos](../../steps/step23_fresh_theta/catalogo_techos); el script incluye 20 casos: azotea con tapa, una/dos/cuatro aguas, pabellón, banda, compuesto L, canes rectos/perfilados, tornapuntas, ménsulas, alero cerrado, sol y sombra, tres encuentros con frontones, alero interrumpido, casona compuesta y moderno sin alero ornamental.

### Objetos de azotea (`roof.props[].kind`)

`water_tank`: tanque negro sobre base; `tank_elevated`: tanque en estructura metálica elevada; `antenna`: mástil con antena Yagi; `hvac`: condensadora con rejillas; `duct_run`: ducto con codo; `skylight`: lucernario bajo; `caseta`: cuarto de servicio con puerta y cobertura; `laundry`: postes y tendales; `planter`: maceta con vegetación; `stair_bulkhead`: salida de escalera con caseta; `rebar_cluster`: fierros de espera.

Ubicación explícita `xy`, `mass_role`, giro y escala. La huella debe caber en techo libre con separación. No añadir props a una cubierta inclinada detallada conservando props: esa combinación se rechaza.

## 11. Proyecciones de fachada: vocabulario completo

Fuente: `prefabs_facade.py:FACADE_PROJECTIONS`. Son piezas en `(u_m,v_m,width_m,height_m,depth_m)`, con material y controles opcionales. Muchas tienen un sucesor más completo como ensamble independiente.

| `kind` | Apariencia |
|---|---|
| `panel` | Placa rectangular aplicada |
| `frame` | Marco rectangular hueco |
| `ledge` | Repisa horizontal |
| `canopy` | Losa plana saliente |
| `curved_canopy` | Marquesina de contorno curvo |
| `cornice` | Remate escalonado |
| `denticulated_cornice`, `denticulated` | Cornisa con dentículos/modillones; segundo es alias |
| `classical_cornice` | Cornisa clásica con corona y dentículos separados |
| `sill_band` | Banda horizontal de antepecho |
| `pilaster` | Pilastra adosada |
| `classical_pilaster`, `composite_pilaster` | Adaptadores de pilastra al motor común de miembros; comparten dispatcher |
| `moulded_surround`, `segmental_surround` | Molduras huecas alrededor del vano; arco si se suministra `arch_rise_m` |
| `balcony` | Losa y baranda simple |
| `gallery` | Galería continua con cubierta y apoyos |
| `awning` | Toldo inclinado con brazos y faldón |
| `bay_window` | Mirador saliente con tres caras y cubierta |
| `eave` | Alero adaptado al motor común de cubiertas |
| `shutter` | Contraventanas de lamas junto al vano |
| `downpipe` | Bajante con abrazaderas |
| `sign_box` | Caja de letrero con relieve de letras |
| `oval_sign` | Cartel ovalado |
| `pediment`, `crown_triangular` | Frontón triangular; el segundo extiende el ámbito de coronación |
| `crown_stepped` | Coronamiento escalonado |
| `vertical_fins` | Aletas verticales repetidas |

`label` es texto de relieve, no un modelo de lenguaje. Alfabeto real: A–Z, 0–9, espacio, `. - / : ( )`; sin Ñ ni tildes. Si aparece un carácter no contemplado, la función omite el texto completo.

`motifs[].kind` solo admite `monumental_portal`: decora una puerta/portón existente del primer piso con pilastras, marco, cornisa y frontón opcional. No crea otro vano.

`cladding=stucco/horizontal`: revestimiento liso o juntas horizontales. `services` activa detalles de servicios. `finish=standard/premium` sigue admitido por el contrato, pero ya no suprime zócalo, bandas ni pilastras; no confundir con los cinco estilos.

## 12. Cercos y suelo

Los cercos y sus hojas de acceso se generan **exclusivamente con el catálogo**.
`site.fence` admite `none` o uno de los cinco estilos de la tabla. `site.runs[].kind`
admite únicamente esos cinco estilos; los runs sustituyen los cercos automáticos.

Los valores antiguos `reja`, `concreto`, `ladrillos`, `concreto_bajo`, `solid_wall`,
`wall` y `fence` se rechazan: no se convierten a otro diseño. En solicitudes antiguas
hay que seleccionar explícitamente un estilo del catálogo y, para tramos, su altura,
modo y material. `site.fence="none"` sin runs desactiva los cercos.

En el modo automático, el frente usa el estilo elegido a 2.1 m; los linderos libres
usan el cerramiento macizo `clasico`, material `brick`, a 2.6 m y sin puertas.
Para controlar alturas, materiales y variantes `high/low`, utiliza `site.runs`.
Las entradas históricas `BuildingProgram.fence_type` y `propose_building(boundary=...)`
usan el mismo catálogo (`none` y `open`, respectivamente, indican ausencia).

| `kind` | Aspecto del cerco vinculado |
|---|---|
| `republicano` | Base de albañilería, barrotes, aros y puntas en modo alto |
| `barroco` | Base y hierro con espirales pareadas y puntas |
| `clasico` | Cerramiento macizo; hojas de acceso paneladas |
| `madera` | Estacas/tablas verticales de punta, travesaños y diagonal en puerta |
| `moderno` | Lamas horizontales sobre base; jardineras opcionales |

`height_mode=high/low` cambia remates/base; no reemplaza `height_m`. `gate_u/garage_u` son **distancias métricas desde el comienzo del run**, pese al sufijo `_u`. `gate_mode/garage_mode=auto/open` dibujan hojas o dejan paso libre. `openness` controla huecos en lamas/estacas; no afecta de igual forma a los cinco estilos. `wall_material=plaster/brick/stone/concrete`; `base_height_m` ajusta base maciza; `plinth` aplica zócalo a estilos compatibles, no al cerco de estacas de madera. `planters` solo moderno.

`site.zones[].kind`: `garden` tierra/plantas; `patio`, `terrace`, `parking`, `driveway`, `corridor`, `paved` pavimento con etiqueta semántica; `unclassified` espacio libre sin malla de acabado. Solo parking/driveway pueden tener `slope_deg` (0–15°). Esas etiquetas no añaden automóviles ni mobiliario automáticamente. Las zonas se intersectan con el suelo libre.

Muestras: [catalogo_cercos](../../steps/step23_fresh_theta/catalogo_cercos).

## 13. Entradas y escaleras

- `entrances.kind=steps`: rellano y peldaños calculados a partir de altura de puerta y `max_riser_m`; `tread_m` huella, `nosing_m` nariz.
- `ramp`: rampa con transiciones, `run_m`, `transition_m`, pendiente resultante ≤15°.
- `passage`: paso horizontal; suelo y umbral deben estar a igual cota.
- `width_m=0` hereda ancho de puerta; `cheek_height_m` y `side_width_m` producen laterales.
- `FacadeControls.stairs`: escalera exterior por `base_z_m/target_z_m`, `flight_width_m/run_m/step_count`, recta o retorno (`switchback`). Distinta del acceso corto `entrances`.

Muestras: [catalogo_entradas](../../steps/step23_fresh_theta/catalogo_entradas).

## 14. Materiales: 23 slots existentes

Fuente: `materials.resolve_materials(BuildingAppearance())`.

| Slot | Apariencia predeterminada |
|---|---|
| `plaster` | Revoque claro; recibe primary_color |
| `accent` | Revoque de acento, inicialmente más oscuro que primary_color |
| `stone` | Gris pétreo/concreto |
| `frame` | Marco claro de aluminio pintado; cambiar template a plaster para moldura de revoque |
| `glass` | Vidrio oscuro frío, transparente |
| `metal` | Acero pintado oscuro |
| `wood` | Madera marrón veteada |
| `brick` | Ladrillo rojizo, textura de aparejo |
| `roof` | Metal corrugado galvanizado |
| `roof_tile` | Teja de arcilla rojiza |
| `leaf` | Vegetación verde |
| `soil` | Tierra oscura |
| `concrete` | Concreto gris |
| `pavement` | Pavimento gris |
| `decal_moisture` | Máscara/textura de humedad |
| `decal_drip` | Máscara/textura de escurrimiento |
| `interior` | Fondo interior casi negro |
| `curtain` | Tela clara |
| `sign` | Pintura de cartel azul verdoso oscuro |
| `plastic` | Plástico negro |
| `rebar` | Metal oxidado |
| `cornice` | Revoque claro cálido |
| `plinth` | Revoque gris cálido de zócalo |

`theta.materials[]` toma `slot`, `template`, `color` RGB 0–1. `slot` puede reemplazar un material o crear un nombre propio; `template` debe existir en el catálogo base y copia sus propiedades físicas/textura. `color` tiñe. `side_material` selecciona un slot existente/declarado y por defecto es `plaster` (tarrajeado); `brick` y `concrete` representan acabados vistos sin añadir estructura. `wall_material` en controles de fachada permite elegir el material de todo un plano. `material_regions` subdivide su superficie sin espesor ni coatings; la última región gana. Véase [materiales de muros](../../../MATERIALES_MUROS.md).

`config.detail`: 1 manzana, 2 calle, 3 detalle cercano. Es diferente de `RoofDesign.detail` textual y del detalle local de miembros/frontones. No asumir que un único LOD controla todos los ensambles.

## 15. Evidencia y configuración

- `evidence.state`: `observed`, `inferred`, `prior`, `unknown`, `externally_known` (el comentario de la dataclass omite `prior`, pero el validador lo acepta).
- `confidence`: null o número entre 0 y 1; `view_ids` debe referenciar `observations` existentes.
- `unknown` exige valor theta nulo; `observed/externally_known` exige valor no nulo.
- Selectores implementados: `facades[masa:0,edge:0]`, `roofs[masa:0]`, `components[id]`, `zones[id]`, `opening_edits[floor:0,bay:1]`, `masses[rol:0]`; se pueden encadenar nombres de campos. No todos los arrays aceptan selectores por ID.
- `config.implementation="theta-candidate-v0"`; `grammar_reference="grammar-v1.0"`; `completion_policy="conservative-0.1"` o `"conservative-0.2"`. El materializador tiene su propia versión independiente.
- `nuisance.seed`: entero 0 ≤ seed < 2^63; `curtains`: booleano.
