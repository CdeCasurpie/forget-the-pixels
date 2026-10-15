# Referencia completa de campos de entrada

**52 contratos · 502 campos declarados.** Inventario generado; no es un JSON Schema de validación semántica.

Generada desde dataclasses alcanzables por `ReconstructionRequest`; no incluye contratos internos resueltos ni V4.

Tipos con `| None` permiten `null`. Arrays JSON se decodifican a tuplas. **Obligatorio** indica ausencia de default; los demás campos se pueden omitir, sujeto a validación semántica.

Los defaults de objetos se muestran por clase; consultar su tabla. Los enums y las restricciones entre campos están en [CATALOGOS.md](CATALOGOS.md) y [README.md](README.md). `decode()` rechaza claves desconocidas y tipos incorrectos; los resolvers/constructores añaden restricciones geométricas.

## ReconstructionRequest

Fuente: [`src/domain/theta.py:409`](../../src/domain/theta.py#L409).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `context` | `ReconstructionContext` | `OBLIGATORIO` | Contexto catastral métrico inmutable de la solicitud. |
| `theta` | `ThetaCandidate` | `OBLIGATORIO` | Decisiones arquitectónicas solicitadas. |
| `nuisance` | `NuisanceParameters` | `NuisanceParameters()` | Variación secundaria separada de la arquitectura. |
| `config` | `GrammarConfig` | `GrammarConfig()` | Versiones/política del generador y nivel de detalle. |
| `observations` | `tuple[Observation, ...]` | `[]` | Referencias de evidencia visual; no se interpretan automáticamente. |
| `evidence` | `dict[str, Evidence]` | `{}` | Mapa de rutas theta a procedencia/confianza. |

## ReconstructionContext

Fuente: [`src/domain/theta.py:24`](../../src/domain/theta.py#L24).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `parcel` | `tuple[tuple[float, float], ...]` | `OBLIGATORIO` | Vértices XY de la parcela en metros. |
| `fronts` | `tuple[int, ...]` | `OBLIGATORIO` | Índices de aristas declaradas como frente a calle. |
| `crs` | `str` | `"EPSG:32718"` | Identificador del sistema de referencia. |
| `metric_origin` | `tuple[float, float, float]` | `[0.0, 0.0, 0.0]` | Origen métrico registrado; no aplica una traslación automática. |
| `locked_height_m` | `float &#124; None` | `null` | Altura exterior conocida que debe coincidir con la de las masas. |

## ThetaCandidate

Fuente: [`src/domain/theta.py:366`](../../src/domain/theta.py#L366).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `roof_assemblies` | `tuple[RoofAssemblyControls, ...]` | `[]` | Cubiertas detalladas que reemplazan superficies básicas. |
| `canopies` | `tuple[CanopyControls, ...]` | `[]` | Marquesinas/coberturas ligadas a fachada. |
| `entrances` | `tuple[EntranceControls, ...]` | `[]` | Accesos ligados a puertas ya existentes. |
| `crowns` | `tuple[CrownControls, ...]` | `[]` | En theta: frontones completos. En fachada: perfiles simples. |
| `entablatures` | `tuple[EntablatureControls, ...]` | `[]` | Entablamentos continuos. |
| `vertical_members` | `tuple[VerticalMemberControls, ...]` | `[]` | Columnas/pilastras/postes anclados independientes. |
| `balconies` | `tuple[BalconyControls, ...]` | `[]` | En ThetaCandidate: ensambles. En FacadeControls: booleano de repetición. |
| `trim` | `TrimControls &#124; None` | `null` | Cornisa/zócalo; override de componente sustituye el bloque completo. |
| `architectural_style` | `str &#124; None` | `null` | Lenguaje de piezas: cinco estilos del catálogo. |
| `roof_bodies` | `tuple[RoofBody, ...]` | `[]` | Cuerpos elevados apoyados en un componente padre. |
| `schema_version` | `str` | `"0.2"` | Versión del contrato theta; pedir 0.3 para composición extendida. |
| `height_m` | `float &#124; None` | `null` | Altura en metros de la entidad; en theta, coronación de masas. |
| `floors` | `int &#124; None` | `null` | Cantidad de pisos; puede derivarse de levels_m. |
| `family` | `str &#124; None` | `null` | Familia de composición; en CrownDesign es familia geométrica del frontón. |
| `massing` | `MassingControls` | `MassingControls()` | Patrón volumétrico o composición por componentes. |
| `facade` | `FacadeControls` | `FacadeControls()` | Programa base de fachada; null de componente significa ciega. |
| `facades` | `tuple[FacadeOverride, ...]` | `[]` | Overrides por masa y arista. |
| `roof` | `RoofControls` | `RoofControls()` | Techo básico; en componente, override local. |
| `roofs` | `tuple[RoofOverride, ...]` | `[]` | Overrides de techo básico por masa. |
| `site` | `SiteControls` | `SiteControls()` | Cercos, jardín y zonas libres. |
| `primary_color` | `tuple[float, float, float] &#124; None` | `null` | RGB 0–1 del revoque principal. |
| `side_material` | `str &#124; None` | `null` | Material base de laterales/fondo: slot existente o declarado en theta.materials; default plaster. |
| `masses` | `tuple[ArchitecturalMass, ...] &#124; None` | `null` | Masas explícitas con huella y niveles; sustituyen altura/pisos. |
| `materials` | `tuple[MaterialControl, ...]` | `[]` | Overrides de slots físicos/de textura y color. |
| `finish` | `str &#124; None` | `null` | Acabado de fachada standard/premium; no estilo arquitectónico. |

## RoofAssemblyControls

Fuente: [`src/domain/roof_details.py:44`](../../src/domain/roof_details.py#L44).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `id` | `str` | `OBLIGATORIO` | Nombre estable y único dentro de la colección. |
| `mass_ref` | `str` | `OBLIGATORIO` | ID canónico de masa resuelta. |
| `design` | `RoofDesign` | `RoofDesign()` | Diseño de pieza; en PlinthControls es un nombre de patrón. |
| `regions` | `tuple[tuple[tuple[float, float], ...], ...]` | `[]` | Lóbulos rectangulares XY de cubierta compound. |
| `crown_ref` | `str &#124; None` | `null` | ID de frontón con el que se encuentra la cubierta. |
| `junction` | `str` | `"none"` | none/behind/gable para encuentro cubierta-frontón. |
| `enabled` | `bool` | `true` | Activación de la pieza/control. |
| `join_group` | `str &#124; None` | `null` | Grupo de cubiertas contiguas a igual cota y acabado compatible. |
| `props_mode` | `str` | `"preserve"` | preserve/auto/off en objetos de techo detallado. |

## RoofDesign

Fuente: [`src/domain/roof_details.py:20`](../../src/domain/roof_details.py#L20).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `form` | `str` | `"gable"` | Forma geométrica de cubierta detallada. |
| `covering` | `str` | `"curved_tile"` | Acabado modular de cubierta. |
| `construction` | `str` | `"solid"` | Construcción de puerta o cubierta, según contrato. |
| `style` | `str` | `"auto"` | Selector local; Opening.style es carpintería legacy, no lenguaje global. |
| `slope_deg` | `float` | `22.0` | Inclinación en grados. |
| `rotation_deg` | `float` | `0.0` | Giro en planta en grados. |
| `ridge_fraction` | `float` | `0.5` | Fracción de ubicación de cumbrera en cubierta a dos aguas. |
| `thickness_m` | `float` | `0.14` | Espesor de cuerpo de frontón/cubierta. |
| `band_depth_m` | `float` | `2.4` | Profundidad de banda inclinada, dejando resto plano. |
| `tile_width_m` | `float` | `0.22` | Ancho de módulo de teja/recubrimiento. |
| `tile_length_m` | `float` | `0.4` | Longitud de módulo de teja. |
| `overlap_m` | `float` | `0.08` | Solape longitudinal de módulos. |
| `detail` | `str` | `"full"` | Resolución local/global; techo usa light/medium/full, otros entero 1–3. |
| `material` | `str` | `"roof_tile"` | Slot de material principal. |
| `substrate_material` | `str` | `"wood"` | Material del soporte continuo de cubierta. |
| `eave` | `EaveDesign` | `EaveDesign()` | Diseño del alero. |
| `parapet_m` | `float` | `0.0` | Altura de parapeto sobre techo. |
| `cap` | `str` | `"none"` | Perfil de tapa de parapeto. |
| `cap_material` | `str` | `"stone"` | Material de tapa de parapeto. |
| `cap_drip` | `bool` | `false` | Pliegue goterón de tapa metálica. |

## EaveDesign

Fuente: [`src/domain/roof_details.py:6`](../../src/domain/roof_details.py#L6).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `kind` | `str` | `"auto"` | Selector de tipo; su vocabulario depende del contrato. |
| `overhang_m` | `float` | `0.35` | Vuelo del alero. |
| `spacing_m` | `float` | `0.55` | Separación métrica de elementos repetidos. |
| `beam_width_m` | `float` | `0.08` | Ancho de viga/can. |
| `beam_height_m` | `float` | `0.14` | Canto de viga/can. |
| `fascia` | `bool` | `true` | Tabla/frente de borde de losa o alero. |
| `soffit` | `bool` | `false` | Cierre inferior del alero. |
| `material` | `str` | `"wood"` | Slot de material principal. |
| `fascia_material` | `str` | `"wood"` | Material de tabla frontal. |
| `gutter` | `bool` | `false` | Añadir canaleta en bordes compatibles. |

## CanopyControls

Fuente: [`src/domain/roof_details.py:58`](../../src/domain/roof_details.py#L58).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `id` | `str` | `OBLIGATORIO` | Nombre estable y único dentro de la colección. |
| `mass_ref` | `str` | `OBLIGATORIO` | ID canónico de masa resuelta. |
| `edge` | `int` | `OBLIGATORIO` | Índice de arista canónica de la masa/parcela según contexto. |
| `u_m` | `float` | `OBLIGATORIO` | Posición horizontal métrica; borde izquierdo salvo miembro vertical (eje). |
| `width_m` | `float` | `OBLIGATORIO` | Ancho métrico; cero puede heredar en controles que lo explicitan. |
| `depth_m` | `float` | `OBLIGATORIO` | Profundidad métrica; en PlanRegion es un intervalo. |
| `height_m` | `float` | `OBLIGATORIO` | Altura en metros de la entidad; en theta, coronación de masas. |
| `design` | `RoofDesign` | `RoofDesign()` | Diseño de pieza; en PlinthControls es un nombre de patrón. |
| `opening_index` | `int &#124; None` | `null` | Índice del vano de anclaje en la fachada resuelta. |
| `posts` | `bool` | `false` | Columnas de apoyo para marquesina. |

## EntranceControls

Fuente: [`src/domain/entrances.py:6`](../../src/domain/entrances.py#L6).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `id` | `str` | `OBLIGATORIO` | Nombre estable y único dentro de la colección. |
| `mass_ref` | `str` | `OBLIGATORIO` | ID canónico de masa resuelta. |
| `edge` | `int` | `OBLIGATORIO` | Índice de arista canónica de la masa/parcela según contexto. |
| `opening_index` | `int` | `OBLIGATORIO` | Índice del vano de anclaje en la fachada resuelta. |
| `kind` | `str` | `"steps"` | Selector de tipo; su vocabulario depende del contrato. |
| `ground_z_m` | `float` | `0.0` | Cota absoluta local del suelo de acceso. |
| `width_m` | `float` | `0.0` | Ancho métrico; cero puede heredar en controles que lo explicitan. |
| `landing_m` | `float` | `0.9` | Profundidad de rellano. |
| `tread_m` | `float` | `0.3` | Huella de peldaño. |
| `max_riser_m` | `float` | `0.18` | Contrahuella máxima; deriva número de escalones. |
| `run_m` | `float` | `3.0` | Desarrollo horizontal de escalera/acceso. |
| `transition_m` | `float` | `0.4` | Longitud de transición de rampa. |
| `nosing_m` | `float` | `0.025` | Vuelo de nariz de peldaño. |
| `slab_m` | `float` | `0.12` | Espesor de losa/plataforma. |
| `cheek_height_m` | `float` | `0.0` | Altura de laterales de acceso. |
| `side_width_m` | `float` | `0.12` | Espesor/ancho de laterales de acceso. |
| `material` | `str` | `"stone"` | Slot de material principal. |
| `side_material` | `str` | `"plaster"` | Material base de laterales/fondo: slot existente o declarado en theta.materials; default plaster. |

## CrownControls

Fuente: [`src/domain/crowns.py:27`](../../src/domain/crowns.py#L27).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `id` | `str` | `OBLIGATORIO` | Nombre estable y único dentro de la colección. |
| `mass_ref` | `str` | `OBLIGATORIO` | ID canónico de masa resuelta. |
| `edge` | `int` | `OBLIGATORIO` | Índice de arista canónica de la masa/parcela según contexto. |
| `u_m` | `float` | `OBLIGATORIO` | Posición horizontal métrica; borde izquierdo salvo miembro vertical (eje). |
| `width_m` | `float` | `OBLIGATORIO` | Ancho métrico; cero puede heredar en controles que lo explicitan. |
| `height_m` | `float` | `OBLIGATORIO` | Altura en metros de la entidad; en theta, coronación de masas. |
| `design` | `CrownDesign` | `CrownDesign()` | Diseño de pieza; en PlinthControls es un nombre de patrón. |
| `anchor` | `str` | `"wall_top"` | Referencia de cota: valores dependen del tipo de ensamble. |
| `opening_index` | `int &#124; None` | `null` | Índice del vano de anclaje en la fachada resuelta. |
| `base_m` | `float` | `0.0` | Cota relativa o desplazamiento desde el anclaje del frontón. |
| `enabled` | `bool` | `true` | Activación de la pieza/control. |
| `aperture` | `str` | `"none"` | Perforación none/oculus/roundhead/pointed del frontón. |
| `aperture_width_m` | `float` | `0.55` | Ancho de perforación del frontón. |
| `aperture_height_m` | `float` | `0.7` | Altura de perforación del frontón. |
| `aperture_sill_m` | `float` | `0.3` | Base de perforación relativa al frontón. |

## CrownDesign

Fuente: [`src/domain/crowns.py:6`](../../src/domain/crowns.py#L6).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `family` | `str` | `"auto"` | Familia de composición; en CrownDesign es familia geométrica del frontón. |
| `style` | `str` | `"auto"` | Selector local; Opening.style es carpintería legacy, no lenguaje global. |
| `silhouette` | `str` | `"angular"` | Atributo angular/curved/pointed/mixed para clasificar frontón. |
| `stepped` | `bool` | `false` | Solicitar hombros escalonados en clasificación automática. |
| `concave_shoulders` | `bool` | `false` | Solicitar hombros cóncavos. |
| `central_block` | `bool` | `false` | Solicitar ático central elevado. |
| `open_center` | `bool` | `false` | Solicitar frontón partido. |
| `thickness_m` | `float` | `0.3` | Espesor de cuerpo de frontón/cubierta. |
| `recess_m` | `float` | `0.055` | Rehundimiento del relleno/campo. |
| `moulding_width_m` | `float` | `0.16` | Ancho de moldura del frontón. |
| `projection_m` | `float` | `0.16` | Vuelo exterior de moldura/entablamento. |
| `base` | `bool` | `true` | Base del miembro o cornisa inferior de frontón. |
| `ornament` | `str` | `"none"` | Booleano de ornato en miembro; nombre de ornato en frontón/entablamento. |
| `material` | `str` | `"plaster"` | Slot de material principal. |
| `moulding_material` | `str` | `"cornice"` | Slot de molduras del frontón. |
| `field_material` | `str &#124; None` | `null` | Material opcional del campo rehundido. |
| `detail` | `int` | `2` | Resolución local/global; techo usa light/medium/full, otros entero 1–3. |

## EntablatureControls

Fuente: [`src/domain/crowns.py:46`](../../src/domain/crowns.py#L46).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `id` | `str` | `OBLIGATORIO` | Nombre estable y único dentro de la colección. |
| `mass_refs` | `tuple[str, ...]` | `[]` | IDs de masas; en entablamento vacío selecciona todas las cerradas. |
| `anchor` | `str` | `"wall_top"` | Referencia de cota: valores dependen del tipo de ensamble. |
| `top_m` | `float` | `0.0` | Cota absoluta o desplazamiento superior del entablamento. |
| `height_m` | `float` | `0.55` | Altura en metros de la entidad; en theta, coronación de masas. |
| `projection_m` | `float` | `0.18` | Vuelo exterior de moldura/entablamento. |
| `style` | `str` | `"auto"` | Selector local; Opening.style es carpintería legacy, no lenguaje global. |
| `material` | `str` | `"cornice"` | Slot de material principal. |
| `frieze_material` | `str` | `"plaster"` | Material del friso. |
| `scope` | `str` | `"street"` | exposed o street para recorridos perimetrales. |
| `ornament` | `str` | `"none"` | Booleano de ornato en miembro; nombre de ornato en frontón/entablamento. |
| `enabled` | `bool` | `true` | Activación de la pieza/control. |

## VerticalMemberControls

Fuente: [`src/domain/vertical_members.py:30`](../../src/domain/vertical_members.py#L30).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `id` | `str` | `OBLIGATORIO` | Nombre estable y único dentro de la colección. |
| `mass_ref` | `str` | `OBLIGATORIO` | ID canónico de masa resuelta. |
| `edge` | `int` | `OBLIGATORIO` | Índice de arista canónica de la masa/parcela según contexto. |
| `u_m` | `float` | `OBLIGATORIO` | Posición horizontal métrica; borde izquierdo salvo miembro vertical (eje). |
| `bottom_m` | `float` | `OBLIGATORIO` | Cota inferior de miembro respecto a base de masa. |
| `height_m` | `float` | `OBLIGATORIO` | Altura en metros de la entidad; en theta, coronación de masas. |
| `width_m` | `float` | `0.45` | Ancho métrico; cero puede heredar en controles que lo explicitan. |
| `depth_m` | `float` | `0.3` | Profundidad métrica; en PlanRegion es un intervalo. |
| `placement` | `str` | `"attached"` | attached/embedded/freestanding/corner. |
| `offset_m` | `float` | `0.0` | Desplazamiento del anclaje/plano; en zona, positivo exterior. |
| `embed_ratio` | `float` | `0.5` | Fracción de profundidad embebida en la pared. |
| `enabled` | `bool` | `true` | Activación de la pieza/control. |
| `design` | `MemberDesign` | `MemberDesign()` | Diseño de pieza; en PlinthControls es un nombre de patrón. |

## MemberDesign

Fuente: [`src/domain/vertical_members.py:6`](../../src/domain/vertical_members.py#L6).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `style` | `str` | `"moderno"` | Selector local; Opening.style es carpintería legacy, no lenguaje global. |
| `variant` | `str` | `"auto"` | Variante del catálogo del estilo; auto elige primera entrada. |
| `section` | `str` | `"auto"` | En zona: sección espacial; en miembro: forma de sección transversal. |
| `base` | `bool &#124; None` | `null` | Base del miembro o cornisa inferior de frontón. |
| `capital` | `bool &#124; None` | `null` | Activar capitel; null usa preset. |
| `collar` | `bool` | `true` | Activar collarín del capitel. |
| `abacus` | `bool` | `true` | Activar ábaco superior del capitel. |
| `base_profile` | `str` | `"auto"` | Perfil de basa: auto/attic/simple/minimal. |
| `pedestal_m` | `float` | `0.0` | Altura del pedestal bajo la basa. |
| `base_height_m` | `float &#124; None` | `null` | Altura de base maciza de cerco o base de miembro según contrato. |
| `capital_height_m` | `float &#124; None` | `null` | Altura explícita de capitel; null usa proporciones. |
| `taper` | `float &#124; None` | `null` | Fracción de estrechamiento del fuste. |
| `entasis` | `float` | `0.025` | Abombamiento del fuste. |
| `turns` | `float` | `1.5` | Vueltas de fuste torsionado. |
| `flute_count` | `int` | `12` | Cantidad de acanaladuras. |
| `ornament` | `bool` | `true` | Booleano de ornato en miembro; nombre de ornato en frontón/entablamento. |
| `detail` | `int` | `2` | Resolución local/global; techo usa light/medium/full, otros entero 1–3. |
| `material` | `str` | `"plaster"` | Slot de material principal. |
| `base_material` | `str &#124; None` | `null` | Material opcional de basa. |
| `capital_material` | `str &#124; None` | `null` | Material opcional de capitel. |

## BalconyControls

Fuente: [`src/domain/balconies.py:20`](../../src/domain/balconies.py#L20).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `id` | `str` | `OBLIGATORIO` | Nombre estable y único dentro de la colección. |
| `mass_ref` | `str` | `OBLIGATORIO` | ID canónico de masa resuelta. |
| `edge` | `int` | `OBLIGATORIO` | Índice de arista canónica de la masa/parcela según contexto. |
| `floor_m` | `float` | `OBLIGATORIO` | Cota del balcón respecto a base de masa; debe coincidir con un nivel. |
| `u_m` | `float` | `OBLIGATORIO` | Posición horizontal métrica; borde izquierdo salvo miembro vertical (eje). |
| `width_m` | `float` | `OBLIGATORIO` | Ancho métrico; cero puede heredar en controles que lo explicitan. |
| `enabled` | `bool` | `true` | Activación de la pieza/control. |
| `style` | `str` | `"auto"` | Selector local; Opening.style es carpintería legacy, no lenguaje global. |
| `variant` | `str` | `"auto"` | Variante del catálogo del estilo; auto elige primera entrada. |
| `kind` | `str` | `"projecting"` | Selector de tipo; su vocabulario depende del contrato. |
| `depth_m` | `float` | `0.85` | Profundidad métrica; en PlanRegion es un intervalo. |
| `slab` | `bool` | `true` | Crear plataforma nueva; false para terrace/juliet/stair. |
| `slab_m` | `float` | `0.18` | Espesor de losa/plataforma. |
| `slab_material` | `str` | `"plaster"` | Material de plataforma. |
| `brackets` | `bool` | `false` | Ménsulas inferiores de balcón. |
| `cover` | `bool` | `false` | Crear cubierta del balcón/galería. |
| `enclosure_height_m` | `float` | `2.5` | Altura desde plataforma hasta cubierta/cierre superior. |
| `railing` | `RailingControls` | `RailingControls()` | Controles de baranda. |
| `sides` | `tuple[str, ...]` | `["left", "front", "right"]` | Lados de baranda: left/front/right. |
| `path` | `tuple[tuple[float, float, float], ...]` | `[]` | Ruta de baranda (u, profundidad exterior, delta Z). |
| `curved_front_m` | `float` | `0.0` | Abombamiento en planta del frente de balcón. |
| `corner_return_m` | `float` | `0.0` | Longitud de vuelta por la siguiente arista ortogonal. |
| `planters` | `bool` | `false` | Añadir jardineras en balcón o cerco compatible. |
| `fascia` | `bool` | `true` | Tabla/frente de borde de losa o alero. |
| `opening_index` | `int &#124; None` | `null` | Índice del vano de anclaje en la fachada resuelta. |
| `support_mass` | `str &#124; None` | `null` | Masa cuyo techo soporta una baranda sin plataforma. |
| `stair_index` | `int &#124; None` | `null` | Índice de escalera existente para derivar su baranda. |
| `column_member` | `MemberDesign &#124; None` | `null` | Diseño de postes/columnas de galería. |

## RailingControls

Fuente: [`src/domain/balconies.py:7`](../../src/domain/balconies.py#L7).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `enabled` | `bool` | `true` | Activación de la pieza/control. |
| `pattern` | `str` | `"auto"` | Selector de patrón; consultar catálogo del contrato correspondiente. |
| `height_m` | `float` | `1.05` | Altura en metros de la entidad; en theta, coronación de masas. |
| `spacing_m` | `float` | `0.14` | Separación métrica de elementos repetidos. |
| `post_spacing_m` | `float` | `1.6` | Paso máximo entre postes de baranda. |
| `post_width_m` | `float` | `0.075` | Ancho de poste de baranda. |
| `handrail` | `bool` | `true` | Activar pasamanos superior. |
| `material` | `str` | `"auto"` | Slot de material principal. |
| `glass_material` | `str` | `"glass"` | Material del vidrio. |

## TrimControls

Fuente: [`src/domain/theta.py:323`](../../src/domain/theta.py#L323).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `cornice` | `CorniceControls` | `CorniceControls()` | En puerta: activar remate; en TrimControls: controles de cornisa. |
| `plinth` | `PlinthControls` | `PlinthControls()` | Controles de zócalo. |

## CorniceControls

Fuente: [`src/domain/theta.py:296`](../../src/domain/theta.py#L296).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `enabled` | `bool` | `true` | Activación de la pieza/control. |
| `profile` | `str` | `"auto"` | Nombre de perfil de cornisa, o auto. |
| `height_m` | `float` | `0.24` | Altura en metros de la entidad; en theta, coronación de masas. |
| `projection_m` | `float` | `0.18` | Vuelo exterior de moldura/entablamento. |
| `anchor` | `str` | `"wall_top"` | Referencia de cota: valores dependen del tipo de ensamble. |
| `offset_m` | `float` | `0.0` | Desplazamiento del anclaje/plano; en zona, positivo exterior. |
| `material` | `str` | `"cornice"` | Slot de material principal. |
| `scope` | `str` | `"exposed"` | exposed o street para recorridos perimetrales. |
| `courtyards` | `bool` | `false` | Incluir perímetros de patios/huecos interiores. |

## PlinthControls

Fuente: [`src/domain/theta.py:309`](../../src/domain/theta.py#L309).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `enabled` | `bool` | `true` | Activación de la pieza/control. |
| `design` | `str` | `"smooth"` | Diseño de pieza; en PlinthControls es un nombre de patrón. |
| `height_m` | `float` | `0.6` | Altura en metros de la entidad; en theta, coronación de masas. |
| `relief_m` | `float` | `0.025` | Espesor de relieve del zócalo. |
| `material` | `str` | `"plinth"` | Slot de material principal. |
| `course_height_m` | `float` | `0.2` | Altura de cada hilada de zócalo. |
| `block_width_m` | `float` | `0.5` | Ancho de bloques de zócalo. |
| `joint_width_m` | `float` | `0.012` | Ancho de juntas de zócalo. |
| `scope` | `str` | `"exposed"` | exposed o street para recorridos perimetrales. |
| `courtyards` | `bool` | `false` | Incluir perímetros de patios/huecos interiores. |

## RoofBody

Fuente: [`src/domain/theta.py:141`](../../src/domain/theta.py#L141).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `id` | `str` | `OBLIGATORIO` | Nombre estable y único dentro de la colección. |
| `parent` | `str` | `OBLIGATORIO` | ID del componente padre de un cuerpo sobre azotea. |
| `region` | `PlanRegion` | `OBLIGATORIO` | Región relativa a un frente de parcela. |
| `height_m` | `float` | `2.4` | Altura en metros de la entidad; en theta, coronación de masas. |
| `roof` | `RoofControls &#124; None` | `null` | Techo básico; en componente, override local. |
| `facade` | `FacadeControls &#124; None` | `null` | Programa base de fachada; null de componente significa ciega. |
| `trim` | `TrimControls &#124; None` | `null` | Cornisa/zócalo; override de componente sustituye el bloque completo. |

## PlanRegion

Fuente: [`src/domain/theta.py:62`](../../src/domain/theta.py#L62).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `front_edge` | `int &#124; None` | `null` | Arista del anillo canónico usada como marco; null elige frente más largo. |
| `u` | `tuple[float, float]` | `[0.0, 1.0]` | Intervalo normalizado de 0 a 1. |
| `depth` | `tuple[float, float]` | `[0.0, 1.0]` | Intervalo fraccional de profundidad de parcela. |
| `depth_m` | `tuple[float, float] &#124; None` | `null` | Profundidad métrica; en PlanRegion es un intervalo. |
| `fit` | `str` | `"parcel"` | parcel recorta la región; rectangle conserva y valida el rectángulo. |
| `width_reference` | `str` | `"parcel"` | Referencia horizontal: proyección de parcela o longitud de arista. |

## RoofControls

Fuente: [`src/domain/theta.py:271`](../../src/domain/theta.py#L271).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `kind` | `str &#124; None` | `null` | Selector de tipo; su vocabulario depende del contrato. |
| `parapet_m` | `float &#124; None` | `null` | Altura de parapeto sobre techo. |
| `slope_deg` | `float &#124; None` | `null` | Inclinación en grados. |
| `props` | `tuple[RoofObject, ...] &#124; None` | `null` | Objetos de azotea explícitos. |

## RoofObject

Fuente: [`src/domain/theta.py:287`](../../src/domain/theta.py#L287).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `mass_role` | `str` | `OBLIGATORIO` | Referencia de masa; preferir ID canónico rol:índice. |
| `kind` | `str` | `OBLIGATORIO` | Selector de tipo; su vocabulario depende del contrato. |
| `xy` | `tuple[float, float]` | `OBLIGATORIO` | Punto XY local de ubicación de objeto de techo. |
| `rotation_deg` | `float` | `0.0` | Giro en planta en grados. |
| `scale` | `float` | `1.0` | Escala uniforme de objeto de azotea. |

## FacadeControls

Fuente: [`src/domain/theta.py:235`](../../src/domain/theta.py#L235).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `mode` | `str` | `"repeat"` | repeat genera por ritmo; explicit usa entidades suministradas. |
| `bay_count` | `int &#124; None` | `null` | Número de crujías/ejes repetidos. |
| `bay_axes_m` | `tuple[float, ...] &#124; None` | `null` | Centros métricos de ejes; alternativo a cantidad/grupos. |
| `window_ratio` | `float &#124; None` | `null` | Ancho de vano como fracción del paso entre ejes. |
| `window_height_m` | `float &#124; None` | `null` | Altura solicitada de ventana repetida. |
| `sill_m` | `float &#124; None` | `null` | Altura de antepecho dentro del piso. |
| `balconies` | `bool &#124; None` | `null` | En ThetaCandidate: ensambles. En FacadeControls: booleano de repetición. |
| `balcony_depth_m` | `float &#124; None` | `null` | Vuelo del balcón tradicional asociado al vano. |
| `gallery_depth_m` | `float &#124; None` | `null` | Vuelo de galería de familia compatible. |
| `awning_depth_m` | `float &#124; None` | `null` | Vuelo del toldo de familia compatible. |
| `cladding` | `str &#124; None` | `null` | stucco o juntas horizontal. |
| `services` | `bool &#124; None` | `null` | Añadir servicios visibles como condensadora/bajante. |
| `openings` | `tuple[Opening, ...] &#124; None` | `null` | Lista completa de aberturas en modo explicit. |
| `projections` | `tuple[FacadeProjection, ...] &#124; None` | `null` | Relieves/objetos sobre pared; [] anula los derivados de familia. |
| `material_regions` | `tuple[FacadeMaterialRegion, ...] &#124; None` | `null` | Rectángulos de acabado en coordenadas de fachada. |
| `stairs` | `tuple[ExteriorStairSpecification, ...] &#124; None` | `null` | Escaleras exteriores ancladas a fachada. |
| `opening_edits` | `tuple[OpeningEdit, ...] &#124; None` | `null` | Ediciones puntuales por piso/crujía. |
| `added_openings` | `tuple[Opening, ...] &#124; None` | `null` | Vanos adicionales al programa repetitivo. |
| `bay_groups` | `tuple[BayGroup, ...]` | `[]` | Grupos ordenados de crujías dentro de intervalos u. |
| `motifs` | `tuple[ArchitecturalMotif, ...]` | `[]` | Decoración opt-in de vanos ya existentes. |
| `crowns` | `tuple[CrownProfile, ...]` | `[]` | En theta: frontones completos. En fachada: perfiles simples. |
| `order` | `ArchitecturalOrder &#124; None` | `null` | Orden arquitectónico: pilastras y bandas horizontales. |
| `opening_programs` | `tuple[OpeningProgram, ...]` | `[]` | Programa por grupo/piso de tipo, forma y proporciones de vano. |
| `top_profile` | `FacadeTopProfile &#124; None` | `null` | Silueta continua de pared sobre la cota superior. |
| `wall_material` | `str &#124; None` | `null` | Slot de material base de fachada, o del tramo macizo del cerco según contrato. |

## Opening

Fuente: [`src/domain/models.py:121`](../../src/domain/models.py#L121).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `kind` | `str` | `OBLIGATORIO` | Selector de tipo; su vocabulario depende del contrato. |
| `u_m` | `float` | `OBLIGATORIO` | Posición horizontal métrica; borde izquierdo salvo miembro vertical (eje). |
| `v_m` | `float` | `OBLIGATORIO` | Base vertical relativa a la pared/banda actual. |
| `width_m` | `float` | `OBLIGATORIO` | Ancho métrico; cero puede heredar en controles que lo explicitan. |
| `height_m` | `float` | `OBLIGATORIO` | Altura en metros de la entidad; en theta, coronación de masas. |
| `frame_width_m` | `float` | `0.06` | Ancho de moldura/marco dentro del contorno del vano. |
| `recess_m` | `float` | `0.08` | Rehundimiento del relleno/campo. |
| `source` | `str` | `"assumed"` | Procedencia descriptiva de la entidad; algunas rutas internas la usan. |
| `view_id` | `str &#124; None` | `null` | ID de una vista de evidencia. |
| `score` | `float` | `0.0` | Puntuación de evidencia asociada al elemento. |
| `style` | `str` | `"sliding"` | Selector local; Opening.style es carpintería legacy, no lenguaje global. |
| `grille` | `bool` | `false` | Protección con reja en la ventana. |
| `mullion_columns` | `int` | `2` | Número de subdivisiones horizontales del vidrio. |
| `mullion_rows` | `int` | `2` | Número de subdivisiones verticales del vidrio. |
| `balcony_depth_m` | `float` | `0.75` | Vuelo del balcón tradicional asociado al vano. |
| `prefab` | `str` | `"legacy"` | Relleno/constructor de vano. |
| `curtain` | `float` | `0.0` | Cobertura lateral de cortina; theta explícito exige 0 y delega a nuisance. |
| `grille_pattern` | `str` | `"vertical"` | Patrón de reja; vocabulario distinto en puertas y ventanas. |
| `shape` | `str` | `"rectangle"` | Contorno del hueco; consultar restricciones según ruta. |
| `arch_rise_m` | `float &#124; None` | `null` | Flecha de arco sobre arranque; solo shape=arch. |
| `frame_profile` | `str &#124; None` | `null` | Perfil vinculado de ventana; cinco estilos o auto resuelto globalmente. |
| `frame_depth_m` | `float` | `0.1` | Profundidad/relieve de marco. |
| `sill` | `bool` | `false` | Añadir alféizar vinculado al contorno inferior. |
| `grid_spacing_m` | `float &#124; None` | `null` | Separación adaptativa de montantes; null usa columnas/filas. |
| `grille_spacing_m` | `float` | `0.14` | Separación de barras de seguridad. |
| `door` | `DoorControls &#124; None` | `null` | Ensamble de puerta/portón vinculado a este vano. |

## DoorControls

Fuente: [`src/domain/models.py:93`](../../src/domain/models.py#L93).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `model` | `str` | `"auto"` | Estilo del ensamble de puerta, o auto con estilo global. |
| `leaves` | `int` | `0` | 0 automático, 1 o 2 hojas. |
| `construction` | `str` | `"auto"` | Construcción de puerta o cubierta, según contrato. |
| `leaf_material` | `str` | `"auto"` | Slot de material de hoja; auto hereda del modelo. |
| `frame_material` | `str` | `"auto"` | Slot de marco de puerta; auto según modelo. |
| `portal_material` | `str` | `"plaster"` | Material de soportes/portal. |
| `metal_material` | `str` | `"metal"` | Material de herrajes/reja. |
| `glass_material` | `str` | `"glass"` | Material del vidrio. |
| `threshold_material` | `str` | `"stone"` | Material del umbral. |
| `portal` | `str` | `"none"` | none/pilasters/columns alrededor de la puerta. |
| `portal_member` | `MemberDesign &#124; None` | `null` | Diseño personalizado de los soportes del portal. |
| `portal_width_m` | `float` | `0.24` | Ancho de soportes del portal. |
| `portal_gap_m` | `float` | `0.1` | Separación del vano al soporte. |
| `portal_depth_m` | `float` | `0.2` | Relieve/profundidad del portal. |
| `cornice` | `bool` | `false` | En puerta: activar remate; en TrimControls: controles de cornisa. |
| `transom_height_m` | `float` | `0.0` | Altura de sobreluz dentro del vano. |
| `transom_infill` | `str` | `"glass"` | glass u open en la sobreluz. |
| `transom_grille` | `bool` | `false` | Activar reja de sobreluz. |
| `grille_pattern` | `str` | `"auto"` | Patrón de reja; vocabulario distinto en puertas y ventanas. |
| `grille_spacing_m` | `float` | `0.16` | Separación de barras de seguridad. |
| `leaf_grille` | `bool` | `false` | Reja adicional en hoja vidriada/calado. |
| `threshold` | `bool` | `true` | Activar umbral de puerta. |
| `opening_angles_deg` | `tuple[float, ...]` | `[]` | Ángulo exterior por hoja, entre 0 y 110 grados. |

## FacadeProjection

Fuente: [`src/domain/models.py:164`](../../src/domain/models.py#L164).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `kind` | `str` | `OBLIGATORIO` | Selector de tipo; su vocabulario depende del contrato. |
| `u_m` | `float` | `OBLIGATORIO` | Posición horizontal métrica; borde izquierdo salvo miembro vertical (eje). |
| `v_m` | `float` | `OBLIGATORIO` | Base vertical relativa a la pared/banda actual. |
| `width_m` | `float` | `OBLIGATORIO` | Ancho métrico; cero puede heredar en controles que lo explicitan. |
| `height_m` | `float` | `OBLIGATORIO` | Altura en metros de la entidad; en theta, coronación de masas. |
| `depth_m` | `float` | `OBLIGATORIO` | Profundidad métrica; en PlanRegion es un intervalo. |
| `material_slot` | `str` | `"accent"` | Slot de material del elemento/zona. |
| `border_width_m` | `float` | `0.18` | Ancho del borde de marco aplicado. |
| `source` | `str` | `"assumed"` | Procedencia descriptiva de la entidad; algunas rutas internas la usan. |
| `score` | `float` | `0.0` | Puntuación de evidencia asociada al elemento. |
| `label` | `str` | `""` | Texto de relieve; alfabeto limitado. |
| `arch_rise_m` | `float &#124; None` | `null` | Flecha de arco sobre arranque; solo shape=arch. |
| `member` | `MemberDesign &#124; None` | `null` | Diseño común de columna/pilastra en este elemento. |
| `crown` | `CrownDesign &#124; None` | `null` | Diseño volumétrico de frontón reutilizado por una proyección. |

## FacadeMaterialRegion

Fuente: [`src/domain/models.py:151`](../../src/domain/models.py#L151).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `u_m` | `float` | `OBLIGATORIO` | Posición horizontal métrica; borde izquierdo salvo miembro vertical (eje). |
| `v_m` | `float` | `OBLIGATORIO` | Base vertical relativa a la pared/banda actual. |
| `width_m` | `float` | `OBLIGATORIO` | Ancho métrico; cero puede heredar en controles que lo explicitan. |
| `height_m` | `float` | `OBLIGATORIO` | Altura en metros de la entidad; en theta, coronación de masas. |
| `material_slot` | `str` | `OBLIGATORIO` | Slot de material del elemento/zona. |
| `source` | `str` | `"assumed"` | Procedencia descriptiva de la entidad; algunas rutas internas la usan. |
| `score` | `float` | `0.0` | Puntuación de evidencia asociada al elemento. |

## ExteriorStairSpecification

Fuente: [`src/domain/models.py:184`](../../src/domain/models.py#L184).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `u_m` | `float` | `OBLIGATORIO` | Posición horizontal métrica; borde izquierdo salvo miembro vertical (eje). |
| `base_z_m` | `float` | `OBLIGATORIO` | Cota inferior de escalera respecto a su pared. |
| `target_z_m` | `float` | `OBLIGATORIO` | Cota superior de escalera respecto a su pared. |
| `flight_width_m` | `float` | `1.15` | Ancho de un tramo de escalera. |
| `run_m` | `float` | `3.0` | Desarrollo horizontal de escalera/acceso. |
| `step_count` | `int` | `18` | Cantidad de escalones. |
| `switchback` | `bool` | `true` | Dos tramos con retorno en vez de un tramo recto. |
| `material_slot` | `str` | `"accent"` | Slot de material del elemento/zona. |
| `railing_material_slot` | `str` | `"metal"` | Slot para baranda de escalera tradicional. |
| `source` | `str` | `"assumed"` | Procedencia descriptiva de la entidad; algunas rutas internas la usan. |
| `score` | `float` | `0.0` | Puntuación de evidencia asociada al elemento. |
| `railing_enabled` | `bool` | `true` | Activar baranda tradicional de escalera. |

## OpeningEdit

Fuente: [`src/domain/theta.py:168`](../../src/domain/theta.py#L168).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `floor` | `int` | `OBLIGATORIO` | Índice de piso desde 0; null en OpeningProgram abarca los pisos del grupo. |
| `bay` | `int` | `OBLIGATORIO` | Índice de crujía desde 0. |
| `action` | `str` | `OBLIGATORIO` | suppress elimina; replace sustituye con opening. |
| `opening` | `Opening &#124; None` | `null` | Abertura de reemplazo; necesaria solo para replace. |

## BayGroup

Fuente: [`src/domain/theta.py:177`](../../src/domain/theta.py#L177).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `u` | `tuple[float, float]` | `OBLIGATORIO` | Intervalo normalizado de 0 a 1. |
| `count` | `int` | `OBLIGATORIO` | Cantidad de crujías en el grupo. |
| `ground_role` | `str` | `"inherit"` | Programa en planta baja: inherit/entrance/garage/shopfront/blind. |
| `role` | `str &#124; None` | `null` | Rol descriptivo; en masa explícita también origina su referencia. |

## ArchitecturalMotif

Fuente: [`src/domain/theta.py:190`](../../src/domain/theta.py#L190).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `kind` | `str` | `OBLIGATORIO` | Selector de tipo; su vocabulario depende del contrato. |
| `bay` | `int` | `OBLIGATORIO` | Índice de crujía desde 0. |
| `floor` | `int` | `0` | Índice de piso desde 0; null en OpeningProgram abarca los pisos del grupo. |
| `opening_shape` | `str &#124; None` | `null` | Cambio opcional a arch para motivo monumental. |
| `pediment` | `bool` | `true` | Añadir frontón al motivo de portada. |

## CrownProfile

Fuente: [`src/domain/theta.py:200`](../../src/domain/theta.py#L200).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `u` | `tuple[float, float]` | `OBLIGATORIO` | Intervalo normalizado de 0 a 1. |
| `kind` | `str` | `OBLIGATORIO` | Selector de tipo; su vocabulario depende del contrato. |
| `height_m` | `float` | `OBLIGATORIO` | Altura en metros de la entidad; en theta, coronación de masas. |
| `depth_m` | `float` | `0.2` | Profundidad métrica; en PlanRegion es un intervalo. |

## ArchitecturalOrder

Fuente: [`src/domain/theta.py:222`](../../src/domain/theta.py#L222).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `pilaster_mode` | `str` | `"none"` | Ubicación de pilastras por bordes de grupos/crujías o ejes explícitos. |
| `pilaster_width_m` | `float` | `0.3` | Ancho de pilastra del orden. |
| `pilaster_depth_m` | `float` | `0.16` | Relieve de pilastra del orden. |
| `pilaster_axes_u` | `tuple[float, ...]` | `[]` | Ejes normalizados para pilastras explícitas. |
| `paired_bays` | `tuple[int, ...]` | `[]` | Crujías a flanquear con pilastras pareadas. |
| `plinth_height_m` | `float` | `0.0` | Altura del zócalo del orden. |
| `belt_courses_m` | `tuple[float, ...]` | `[]` | Cotas de bandas horizontales. |
| `entablature_height_m` | `float` | `0.0` | Altura reservada al entablamento del orden. |
| `cornice_height_m` | `float` | `0.0` | Altura reservada a cornisa del orden. |

## OpeningProgram

Fuente: [`src/domain/theta.py:209`](../../src/domain/theta.py#L209).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `group` | `int` | `OBLIGATORIO` | Índice de BayGroup desde 0. |
| `floor` | `int &#124; None` | `null` | Índice de piso desde 0; null en OpeningProgram abarca los pisos del grupo. |
| `kind` | `str &#124; None` | `null` | Selector de tipo; su vocabulario depende del contrato. |
| `shape` | `str &#124; None` | `null` | Contorno del hueco; consultar restricciones según ruta. |
| `width_ratio` | `float &#124; None` | `null` | Ancho del vano respecto al paso del grupo. |
| `height_m` | `float &#124; None` | `null` | Altura en metros de la entidad; en theta, coronación de masas. |
| `sill_m` | `float &#124; None` | `null` | Altura de antepecho dentro del piso. |
| `prefab` | `str &#124; None` | `null` | Relleno/constructor de vano. |
| `grille` | `bool &#124; None` | `null` | Protección con reja en la ventana. |

## FacadeTopProfile

Fuente: [`src/domain/models.py:202`](../../src/domain/models.py#L202).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `points` | `tuple[tuple[float, float], ...]` | `OBLIGATORIO` | Puntos ordenados (u normalizado, elevación métrica) de la silueta. |
| `depth_m` | `float` | `0.3` | Profundidad métrica; en PlanRegion es un intervalo. |
| `trim_width_m` | `float` | `0.16` | Ancho de moldura sobre silueta. |
| `trim_depth_m` | `float` | `0.12` | Relieve de moldura sobre silueta. |
| `trim_material_slot` | `str` | `"frame"` | Material de moldura sobre silueta. |
| `trim_profile` | `str &#124; None` | `null` | Estilo de perfil para la moldura superior. |

## MassingControls

Fuente: [`src/domain/theta.py:49`](../../src/domain/theta.py#L49).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `pattern` | `str &#124; None` | `null` | Selector de patrón; consultar catálogo del contrato correspondiente. |
| `front_setback_m` | `float &#124; None` | `null` | Retiro desde los frentes. |
| `upper_setback_m` | `float &#124; None` | `null` | Retiro adicional del cuerpo superior. |
| `podium_floors` | `int &#124; None` | `null` | Pisos del podio, menor que el total. |
| `front_depth_m` | `float &#124; None` | `null` | Profundidad de la franja frontal. |
| `low_floors` | `int &#124; None` | `null` | Pisos del cuerpo bajo en una división frente/fondo. |
| `corner_reach_m` | `float &#124; None` | `null` | Alcance de las bandas que definen el acento de esquina. |
| `components` | `tuple[MassComponent, ...]` | `[]` | Componentes en regiones del catastro. |
| `parcel_tolerance_m` | `float` | `0.0` | Tolerancia exterior de composición (0–2 m). |

## MassComponent

Fuente: [`src/domain/theta.py:125`](../../src/domain/theta.py#L125).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `id` | `str` | `OBLIGATORIO` | Nombre estable y único dentro de la colección. |
| `region` | `PlanRegion` | `OBLIGATORIO` | Región relativa a un frente de parcela. |
| `levels_m` | `tuple[float, ...]` | `OBLIGATORIO` | Cotas de base, entrepisos y techo; no alturas individuales. |
| `kind` | `str` | `"enclosed"` | Selector de tipo; su vocabulario depende del contrato. |
| `cutouts` | `tuple[PlanRegion, ...]` | `[]` | Regiones a sustraer de la huella del componente. |
| `support` | `SupportControls` | `SupportControls()` | Reglas de apoyo geométrico del componente. |
| `facade` | `FacadeControls &#124; None` | `null` | Programa base de fachada; null de componente significa ciega. |
| `faces` | `tuple[FaceBand, ...]` | `[]` | Bandas por orientación de cara. |
| `roof` | `RoofControls &#124; None` | `null` | Techo básico; en componente, override local. |
| `slab_m` | `float` | `0.18` | Espesor de losa/plataforma. |
| `zones` | `tuple[FacadeZone, ...]` | `[]` | Zonas independientes: fachada o suelo según contrato. |
| `trim` | `TrimControls &#124; None` | `null` | Cornisa/zócalo; override de componente sustituye el bloque completo. |

## SupportControls

Fuente: [`src/domain/theta.py:78`](../../src/domain/theta.py#L78).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `kind` | `str` | `"bearing"` | Selector de tipo; su vocabulario depende del contrato. |
| `spacing_m` | `float` | `4.0` | Separación métrica de elementos repetidos. |
| `column_width_m` | `float` | `0.25` | Ancho de columnas de apoyo/sección. |
| `inset_m` | `float` | `0.4` | Separación de apoyos respecto al borde. |
| `max_cantilever_m` | `float` | `0.0` | Vuelo máximo permitido respecto a apoyo inferior. |
| `member` | `MemberDesign &#124; None` | `null` | Diseño común de columna/pilastra en este elemento. |

## FaceBand

Fuente: [`src/domain/theta.py:88`](../../src/domain/theta.py#L88).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `face` | `str` | `OBLIGATORIO` | Orientación local: front/back/left/right/all. |
| `controls` | `FacadeControls` | `OBLIGATORIO` | Programa de fachada de la banda/zona. |
| `z_m` | `tuple[float, float] &#124; None` | `null` | Intervalo vertical relativo a la base del componente. |

## FacadeZone

Fuente: [`src/domain/theta.py:105`](../../src/domain/theta.py#L105).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `face` | `str` | `OBLIGATORIO` | Orientación local: front/back/left/right/all. |
| `controls` | `FacadeControls` | `OBLIGATORIO` | Programa de fachada de la banda/zona. |
| `u` | `tuple[float, float]` | `[0.0, 1.0]` | Intervalo normalizado de 0 a 1. |
| `z_m` | `tuple[float, float] &#124; None` | `null` | Intervalo vertical relativo a la base del componente. |
| `role` | `str &#124; None` | `null` | Rol descriptivo; en masa explícita también origina su referencia. |
| `offset_m` | `float` | `0.0` | Desplazamiento del anclaje/plano; en zona, positivo exterior. |
| `section` | `FacadeSection &#124; None` | `null` | En zona: sección espacial; en miembro: forma de sección transversal. |

## FacadeSection

Fuente: [`src/domain/theta.py:95`](../../src/domain/theta.py#L95).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `back_wall` | `bool` | `true` | Conservar pared al fondo de un espacio retranqueado. |
| `column_axes_u` | `tuple[float, ...]` | `[0.08, 0.92]` | Ejes normalizados de columnas de la sección. |
| `column_width_m` | `float` | `0.25` | Ancho de columnas de apoyo/sección. |
| `slab_m` | `float` | `0.2` | Espesor de losa/plataforma. |
| `member` | `MemberDesign &#124; None` | `null` | Diseño común de columna/pilastra en este elemento. |

## FacadeOverride

Fuente: [`src/domain/theta.py:264`](../../src/domain/theta.py#L264).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `mass_role` | `str` | `OBLIGATORIO` | Referencia de masa; preferir ID canónico rol:índice. |
| `edge` | `int` | `OBLIGATORIO` | Índice de arista canónica de la masa/parcela según contexto. |
| `controls` | `FacadeControls` | `OBLIGATORIO` | Programa de fachada de la banda/zona. |

## RoofOverride

Fuente: [`src/domain/theta.py:279`](../../src/domain/theta.py#L279).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `mass_ref` | `str` | `OBLIGATORIO` | ID canónico de masa resuelta. |
| `kind` | `str &#124; None` | `null` | Selector de tipo; su vocabulario depende del contrato. |
| `parapet_m` | `float &#124; None` | `null` | Altura de parapeto sobre techo. |
| `slope_deg` | `float &#124; None` | `null` | Inclinación en grados. |

## SiteControls

Fuente: [`src/domain/theta.py:351`](../../src/domain/theta.py#L351).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `fence` | `str &#124; None` | `null` | Tipo de cerco automático. |
| `garden` | `bool &#124; None` | `null` | Plantar espacio libre automáticamente si no hay zonas explícitas. |
| `runs` | `tuple[FenceRun, ...] &#124; None` | `null` | Tramos explícitos de cerco; sustituyen cercos automáticos. |
| `zones` | `tuple[SiteZone, ...]` | `[]` | Zonas independientes: fachada o suelo según contrato. |

## FenceRun

Fuente: [`src/domain/theta.py:330`](../../src/domain/theta.py#L330).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `edge` | `int` | `OBLIGATORIO` | Índice de arista canónica de la masa/parcela según contexto. |
| `start_m` | `float` | `OBLIGATORIO` | Comienzo del cerco sobre la arista de parcela. |
| `end_m` | `float` | `OBLIGATORIO` | Final del cerco sobre la arista de parcela. |
| `kind` | `str` | `OBLIGATORIO` | Selector de tipo; su vocabulario depende del contrato. |
| `height_m` | `float` | `OBLIGATORIO` | Altura en metros de la entidad; en theta, coronación de masas. |
| `gate_u` | `float &#124; None` | `null` | Distancia métrica de puerta desde inicio del tramo, no fracción. |
| `gate_width` | `float` | `0.0` | Ancho métrico de acceso peatonal. |
| `garage_u` | `float &#124; None` | `null` | Distancia métrica de cochera desde inicio del tramo. |
| `garage_width` | `float` | `0.0` | Ancho métrico de acceso vehicular. |
| `height_mode` | `str` | `"high"` | high/low modifica base y remates del cerco. |
| `wall_material` | `str` | `"plaster"` | Slot de material base de fachada, o del tramo macizo del cerco según contrato. |
| `gate_mode` | `str` | `"auto"` | auto dibuja hojas; open deja acceso vacío. |
| `garage_mode` | `str` | `"auto"` | auto dibuja hojas; open deja acceso vacío. |
| `openness` | `float` | `0.3` | Fracción de huecos en lamas/estacas compatibles. |
| `planters` | `bool` | `false` | Añadir jardineras en balcón o cerco compatible. |
| `plinth` | `PlinthControls &#124; None` | `null` | Controles de zócalo. |
| `base_height_m` | `float &#124; None` | `null` | Altura de base maciza de cerco o base de miembro según contrato. |

## SiteZone

Fuente: [`src/domain/theta.py:153`](../../src/domain/theta.py#L153).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `id` | `str` | `OBLIGATORIO` | Nombre estable y único dentro de la colección. |
| `kind` | `str` | `OBLIGATORIO` | Selector de tipo; su vocabulario depende del contrato. |
| `region` | `PlanRegion` | `PlanRegion()` | Región relativa a un frente de parcela. |
| `slope_deg` | `float` | `0.0` | Inclinación en grados. |

## ArchitecturalMass

Fuente: [`src/domain/theta.py:161`](../../src/domain/theta.py#L161).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `role` | `str` | `OBLIGATORIO` | Rol descriptivo; en masa explícita también origina su referencia. |
| `footprint` | `tuple[tuple[float, float], ...]` | `OBLIGATORIO` | Vértices XY explícitos de una masa. |
| `levels_m` | `tuple[float, ...]` | `OBLIGATORIO` | Cotas de base, entrepisos y techo; no alturas individuales. |

## MaterialControl

Fuente: [`src/domain/theta.py:359`](../../src/domain/theta.py#L359).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `slot` | `str` | `OBLIGATORIO` | Nombre de slot existente a reemplazar o nombre nuevo derivado de una plantilla. |
| `template` | `str` | `OBLIGATORIO` | Slot existente del que copiar propiedades PBR/textura. |
| `color` | `tuple[float, float, float] &#124; None` | `null` | Tinte RGB normalizado 0–1. |

## NuisanceParameters

Fuente: [`src/domain/theta.py:395`](../../src/domain/theta.py#L395).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `seed` | `int` | `0` | Semilla determinista de variación secundaria. |
| `curtains` | `bool` | `true` | Solicitar variación de cortinas donde el constructor la admite. |

## GrammarConfig

Fuente: [`src/domain/theta.py:401`](../../src/domain/theta.py#L401).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `implementation` | `str` | `"theta-candidate-v0"` | Identificador de implementación admitida. |
| `grammar_reference` | `str` | `"grammar-v1.0"` | Referencia histórica de gramática, independiente del materializador. |
| `completion_policy` | `str` | `"conservative-0.2"` | Política de completado admitida. |
| `detail` | `int` | `2` | Resolución local/global; techo usa light/medium/full, otros entero 1–3. |

## Observation

Fuente: [`src/domain/theta.py:33`](../../src/domain/theta.py#L33).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `view_id` | `str` | `OBLIGATORIO` | ID de una vista de evidencia. |
| `image_path` | `str` | `OBLIGATORIO` | Ruta de imagen de observación; no ejecuta visión al reconstruir. |
| `camera_xyz` | `tuple[float, float, float] &#124; None` | `null` | Posición métrica opcional de cámara. |
| `heading_pitch_roll_deg` | `tuple[float, float, float] &#124; None` | `null` | Orientación opcional de cámara en grados. |
| `timestamp` | `str &#124; None` | `null` | Marca temporal de observación. |

## Evidence

Fuente: [`src/domain/theta.py:42`](../../src/domain/theta.py#L42).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `state` | `str` | `OBLIGATORIO` | observed/inferred/prior/unknown/externally_known. |
| `confidence` | `float &#124; None` | `null` | Confianza nula o de 0 a 1. |
| `view_ids` | `tuple[str, ...]` | `[]` | IDs de observaciones que respaldan el valor. |

