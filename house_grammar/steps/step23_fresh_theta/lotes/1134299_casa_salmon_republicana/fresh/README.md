# 1134299 casa salmón republicana — fresh theta (step23)

Reconstrucción nueva razonada **solo** desde las 4 `*_lot.jpg` de esta carpeta
(el recuadro amarillo identifica el edificio objetivo), más la estructura
parcela/frentes/cámaras heredada de `after/` (no sus decisiones de fachada).
Metodología: algoritmo de `step23_fresh_theta/GRAMATICA_CAPACIDADES_Y_USO.md`
§0–§7. Validación geométrica pasada (`envelope_test: passed`, 7936 tris);
la fidelidad se juzgó en los 4 `compare_*.jpg` contra la foto original.

## Lectura de fotos (lo visible)
- Casa exenta de **2 pisos** (~3.5 m/piso, ~7 m), color **salmón/terracota** con
  carpintería y molduras **blancas**. Fachada principal simétrica de **3 ejes**:
  - PB: ventana en **arco** (izq, con reja), **puerta-portón en arco** (centro,
    reja metálica blanca calada, más alta ~2.65 m) con **guardapolvo horizontal**
    encima, ventana **rectangular** (der, con reja).
  - PA: 3 ventanas rectangulares con reja y alféizar blanco; la central más
    angosta.
  - Remate: **cornisa** blanca corrida; **bajante** vertical fina a la derecha
    del portal; zócalo y losa de entrepiso sutiles. No hay pilastras de altura
    completa, ni persianas de madera, ni zócalo de piedra, ni letreros, ni teja.
- **Ala este retranqueada** (~5 m, hueco para el auto rojo): PB con **cocherón/
  portón metálico**, PA con **balcón con baranda metálica** y ventana detrás.
- **Cerco**: murete salmón bajo + reja blanca con pilares; portón peatonal al
  eje de la puerta y acceso vehicular al este. Antepatio pavimentado + entrada
  de autos (no jardín bajo el auto). Cubierta no visible (árboles) → plana con
  parapeto bajo, **sin props inventados**.

## Theta (`fresh/request.json`) — capacidades usadas y por qué
- `schema_version: "0.3"`, `family: "republicano"` (lenguaje, no copia de defaults).
- **Masas** (`massing.components`, `PlanRegion` sin XY): `main` (u 0–0.72,
  `depth_m` 1.4–15, frente 1) + `rear_wing` (u 0.72–1, `depth_m` 5–15),
  `levels_m: [0, 3.5, 7]`, `kind: enclosed`, `support: bearing`. Laterales y
  fondo quedan **ciegos** (sin programa), como se ve.
- **Fachada principal** (`main:0`, edge 1, `mode: repeat`):
  - `bay_groups` 3×count 1 (`inherit` / `entrance` / `inherit`) → ritmo asimétrico
    con puerta solo al centro; huecos ciegos fuera de grupos.
  - `opening_programs` 6 (grupo×piso): arco PB izq (`legacy`, reja), puerta arco
    (`open` + reja → portón calado, no hoja maciza), rectangular PB der
    (`slim_window`), 3 rectangulares PA (`legacy`/`slim_window`, reja).
  - `motifs: [monumental_portal bay 1 floor 0, arch, pediment False]` → marco +
    pilastras del portal + cornisa/guardapolvo sobre la puerta. No crea el vano.
  - `projections` propias (sustituyen el relieve familiar): `denticulated_cornice`
    corrida, 3 `sill_band` bajo cada ventana PA, 2 `moulded_surround` en ventana
    arco y ventana recta PB, `downpipe`. Coordenadas en chart local (u desde
    `vertex_a`, v desde base, profundidad +hacia calle).
  - `material_regions: []` (suprime el zócalo de piedra familiar; el muro queda
    salmón continuo) y `order: None` (iteración 1 con `group_boundaries` daba
    franjas blancas de altura completa que **la foto no muestra** → se retiró).
- **Ala este** (`rear_wing:0`, edge 1, `mode: explicit`): `gate` cocherón
  (`metal_gate`) + `window` PA (`slim_window`, reja); `balcony` (`bars`),
  `cornice` simple y `sill_band`. Demuestra la ruta explícita (vanos полностью
  enumerados; `[]` = ausencia).
- **Cubierta**: `roof: {flat, parapet_m 0.4}`, `props: []` (ausencia observada,
  no se inventa tanque/antena). Losas, parapeto, zócalo y escalón de puerta los
  emite la gramática automáticamente.
- **Sitio**: `fence: concreto_bajo` (murete + reja del módulo `site`, con portón
  1.1 m y cochera 2.9 m automáticos); `zones`: `entry/patio` (u 0–0.72,
  `depth_m` 0–1.4) + `drive/driveway` (u 0.72–1, `depth_m` 0–5). El jardín
  automático queda desactivado (`garden: False`) para no plantar bajo el auto.
- **Color/materiales**: `primary_color: [0.73, 0.42, 0.33]` (salmón),
  `side_material: plaster`; overrides `frame` y `metal` a blanco hueso. Sin
  `sign_box` (nada que rotular; `neoclasico` habría puesto "BCP").
- **Ruido/config**: `seed: 12`, `curtains: true`, `detail: 2` (STREET).
- **Evidencia**: `inferred` para niveles, grupos, programas, motivo y vanos del
  ala, con sus `view_ids`; nunca modifica geometría.

## Capacidades deliberadamente NO usadas (y por qué)
- `RoofBody` (cuerpo grande 2.2–6 m): no hay volumen sobre cubierta visible.
- `crowns` / `top_profile`: remate plano, no hay frontones ni silueta escalonada
  (el motivo ya aporta el único frontón… desactivado con `pediment: False`).
- `order` (pilastras de orden): se probó y se retiró — la foto muestra paño
  liso; las pilastras del motivo bastan.
- `bay_window`, `gallery`, `awning`, `shutter`, `sign_box`/`oval_sign`,
  `eave`, `vertical_fins`, `canopy`: ningún testimonio en las 4 vistas.
- `cladding: horizontal`, `services: true`: sin juntas ni condensadoras vistas.
- `cutouts`, `open`, `cantilever/columns`, `section`/zona retranqueada,
  `stairs` explícita, `tile_shed`/`gable`, `tile/coración`: sin evidencia;
  el escalón de acceso lo genera el resolver al haber puerta con `v_m < 0.6`.
- `masses` XY legacy: la ruta por componentes ya expresa el partido sin copiar
  footprints.

## Iteración
1. v1: grupos+programas+motivo+orden, sin relieves → ritmo y vanos correctos,
   pero pilastras blancas de altura completa no existen en foto.
2. v2: +cornisa denticulada, alféizares, surrounds, bajante → bien, puerta
   maciza (falla: la foto muestra portón calado).
3. v3/final: puerta `open`+reja, orden retirado, cornisa afinada (0.42 m).
   `validate_mesh` OK y los 4 compares frontal/oblicuos calzan en masa,
   reparto de vanos, portal, balcón del ala, cerco y color.

## Archivos
`request.json` (input), `resolved_theta.json` (IR), `building.glb` (malla),
`render_*.jpg` + `compare_*.jpg` (4 vistas de `cameras.json`),
`cameras.json`, `manifest.json` (hipótesis, ocupación, validación, sha).

## v4 (corrige el parecido)
Diagnóstico del compare frontal: (1) vanos sobredimensionados — `window_ratio`
0.60/altura 1.70 ocupaban ~60% del bay frente a ~40% en foto; (2) cerco automático
`concreto_bajo` añadía portón de cochera espurio al oeste + pilares gruesos;
(3) el mismo cerco automático levantaba muros medianeros ciegos de 2.6 m
(masas marrones inexistentes en foto); (4) vidrio oscuro del renderer frente a
ventanas blancas de la foto (limitación: el material `glass` es fijo y oscuro;
se compensa con vanos más chicos, más marco blanco y rejas).
Cambios: programas a ratio .36–.42 / h 1.35–1.50 / sill 0.90–1.20; cerco
explícito `runs: [reja h=1.7, gate 4.86/1.1, garage 11.48/2.9]` solo en borde 1
(`fence: none` → sin muros laterales falsos); `order: None`; surrounds y
alféizares recalculados desde el resolve (pasada 1) en vez de a mano.
Queda: vidrio más oscuro que en foto, losa de entrepiso automática (franja gris
fina, no desactivable), forja con volutas no reproducible con `draw_fence`.
