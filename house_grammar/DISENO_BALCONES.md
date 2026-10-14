# Balcones y barandas adaptativos

## Activación y arquitectura

`theta.balconies` es una lista opt-in de ensamblajes. Cada elemento tiene un `id`
estable y se ancla al `mass_ref` y `edge` canónicos de una masa existente. No crea
vanos ni modifica automáticamente una ventana para convertirla en puerta.

Flujo: `reconstruct` → `resolve_theta` → `generate_resolved`.

- `domain/balconies.py`: controles de balcón y baranda.
- `balcony_catalog.py`: 25 configuraciones en cinco familias.
- `balcony_resolver.py`: compatibilidad, anclajes, recorridos, apoyos y envolvente.
- `railing_assembly.py`: postes, rellenos, balaustres de revolución y pasamanos.
- `balcony_assembly.py`: plataforma, ménsulas, cerramientos, galerías y jardineras.
- `ResolvedArchitecture.balconies`: instancias resueltas, sin depender de fotos.

Sin ensamblajes nuevos sigue funcionando la ruta anterior. Las barandas nuevas de
escalera sustituyen las barandas automáticas únicamente de la escalera anclada.

## Ejemplo: balcón volado

Dentro de un theta completo, con `architectural_style: republicano`:

```json
{
  "balconies": [{
    "id": "balcon_principal",
    "mass_ref": "principal:0",
    "edge": 0,
    "floor_m": 3.0,
    "u_m": 0.5,
    "width_m": 3.2,
    "depth_m": 0.85,
    "style": "auto",
    "variant": "iron_rings",
    "kind": "projecting",
    "slab": true,
    "slab_m": 0.18,
    "slab_material": "plaster",
    "brackets": true,
    "fascia": true,
    "railing": {
      "height_m": 1.05,
      "spacing_m": 0.14,
      "post_spacing_m": 1.6,
      "material": "metal"
    }
  }]
}
```

Las dimensiones son metros. `floor_m` se mide desde la base de la masa y debe
coincidir con un piso o cubierta de ella. `u_m` va desde el primer vértice de la
arista canónica. `opening_index` opcional centra el balcón en un vano de esa
arista; no deriva la altura del piso del alféizar.

## Catálogo

| Familia | Variante | Construcción |
|---|---|---|
| republicano | `iron_vertical` | Barras verticales finas. |
| republicano | `iron_rings` | Barras y aros repetidos. |
| republicano | `turned_gallery` | Galería de balaustres torneados y postes altos. |
| republicano | `open_lattice` | Cuadrícula inferior y celosía superior. |
| republicano | `sober_box` | Cajón panelado con carpintería acristalada. |
| barroco | `scroll_iron` | Paños de roleos simétricos y postes rematados. |
| barroco | `bowed_iron` | Barrotes curvados hacia afuera. |
| barroco | `ornate_balusters` | Balaustres vasiformes y dados rematados. |
| barroco | `ornate_box` | Cajón de paneles moldurados, medallones y calados. |
| barroco | `fretwork_gallery` | Torneados, friso perforado y faldón recortado. |
| clasico | `single_baluster` | Balaustre vasiforme sencillo. |
| clasico | `double_baluster` | Balaustre de dos cuerpos. |
| clasico | `mixed_parapet` | Alternancia de paneles y balaustres. |
| clasico | `geometric` | Bastidores con diagonales cruzadas. |
| clasico | `column_gallery` | Columnas, basas/capiteles sencillos y balaustrada. |
| madera | `vertical_timber` | Listones, postes y largueros. |
| madera | `turned_timber` | Balaustres torneados esbeltos. |
| madera | `cross_frames` | Cruces dentro de bastidores. |
| madera | `lattice_panels` | Entramado diagonal recortado al bastidor. |
| madera | `continuous_box` | Cajón corrido panelado y celosía perforada. |
| moderno | `slim_vertical` | Barras rectas finas. |
| moderno | `horizontal_rods` | Barras horizontales; admite `pattern: cables`. |
| moderno | `glass_posts` | Paños de vidrio, postes y herrajes. |
| moderno | `glass_channel` | Vidrio con canal inferior, sin postes. |
| moderno | `louver_parapet` | Antepecho inferior y lamas horizontales. |

Son familias de diseño procedural, no una atribución histórica exclusiva:
la madera y los balaustres aparecen en distintas familias. `style: auto` hereda
el estilo del edificio; se rechaza una familia contradictoria. `variant: auto`
elige la primera variante de esa familia. Materiales y color son independientes.

## Tipos espaciales y opcionales

- `projecting`: plataforma nueva, frente y retornos laterales.
- `terrace`: baranda sobre una cubierta existente. Exige `slab: false`; opcional
  `support_mass` selecciona la masa cuya cubierta la sostiene.
- `juliet`: protección sin plataforma, a 6 cm del plano; exige `slab: false`.
- `gallery`: postes altos y cubierta opcional (`cover`).
- `box`: cajón cerrado, con tapa y tres caras de cerramiento. Las variantes de
  cajón exigen este tipo y la baranda/antepecho activo.
- `stair`: `stair_index` selecciona una escalera existente en la arista. Se derivan
  sus vuelos y descanso; la nueva baranda reemplaza la automática anterior.

`sides: [left, front, right]` selecciona bordes; una terraza remetida puede usar
solo `front`. Los postes de los encuentros son compartidos.

`corner_return_m` prolonga el ensamblaje alrededor de la siguiente esquina
ortogonal de la masa. Debe terminar exactamente en dicha esquina y caber en la
arista vecina. Compatible con cajones: genera plataforma en L y cerramiento.

`curved_front_m` controla el abombamiento del frente en planta (independiente de
la curvatura vertical de `bowed_iron`). La plataforma se aproxima con 16 segmentos;
el relleno se modula en paños. Vidrio curvo: paños planos facetados, no vidrio
doblado. Los cajones/galerías requieren frente recto.

`path` permite un recorrido local explícito `(u, profundidad exterior, delta_z)`
de baranda en una terraza. Para desniveles del edificio usar `kind: stair` con
anclaje a una escalera; no se permite una baranda inclinada sin sustrato.

`enabled`, `slab`, `railing.enabled`, `railing.handrail`, `brackets`, `cover`,
`fascia` y `planters` son controles independientes sujetos a compatibilidad.
Un cajón cerrado requiere cerramiento, y una terraza no agrega otra losa.
Las jardineras son recipientes huecos con tierra; no se añaden plantas al azar.

## Adaptación y geometría

- Los barrotes aumentan en número conservando el grosor.
- Los balaustres son superficies de revolución cerradas; no cajas alargadas.
- Postes y módulos se repiten según `post_spacing_m`.
- Los paneles de vidrio, cruces y carpintería conservan un ancho razonable.
- Aros, volutas y celosías se repiten por módulo. Los motivos no se estiran a
  todo el ancho del balcón.
- Pasamanos horizontales: sweep con ingletes; en pendiente siguen cada tramo,
  manteniendo verticales los postes y balaustres.
- Ménsulas: siluetas extruidas, distribuidas bajo la losa. Se desplazan dentro
  de un margen para evitar vanos inferiores; si no caben se rechaza el diseño.
- Frisos y faldones tienen geometría perforada/recortada real.
- Cada pieza conserva semántica y pertenece al assembly `balcony/<id>`.

## Materiales

`railing.material: auto` utiliza el material de la variante. Cualquier slot
existente puede seleccionarse manualmente: `wood`, `metal`, `stone`, `plaster`,
etc. `slab_material` y `railing.glass_material` son independientes. Colores y
texturas usan `theta.materials`; no se obliga a usar el color del ejemplo.

## Generación y salmón

Desde `house_grammar`:

```bash
python3 steps/step23_fresh_theta/generar_balcones.py
# Opcional: --only catalogue | --only salmon
```

`catalogo_balcones/` contiene 103 ejemplos:

- 75: 25 variantes × 1.2, 3.2 y 8 m de ancho.
- 20: cinco familias × terraza, esquina, falso balcón y escalera con descanso.
- 8 extras: dos frentes curvos, cables, material manual, desactivado, plataforma
  sola, cajón de esquina y jardineras.

Cada carpeta contiene `building.glb`, `request.json`, `resolved_balconies.json`
y `validation.json`. `index.json` resume el catálogo. No genera imágenes.

La salmón usa `profundidad_central/request.json` y escribe en
`lotes/1134299_casa_salmon_republicana/balcones_vinculados/`. El paño de las dos
ventanas remetidas identifica la arista; la baranda republicana con aros se
ancla a su piso y se apoya en la cubierta del cuerpo inferior, protegiendo el
frente y retorno derecho. Sustituye el parapeto automático de esa cubierta para
evitar barras enterradas en él. Mantiene rejas, puertas, cerco y remates; no crea
una puerta de acceso ni otra plataforma.

## Verificación y límites

Se comprueban dimensiones finitas, IDs, herencia de estilo, referencias de masa,
pisos, anclajes de escalera, sustrato de terraza, envolvente, intersecciones con
otras masas y losas/vanos, duplicación de ensamblajes y presupuesto geométrico.
Se prueba cierre/orientación de balaustres y continuidad/distribución de postes.

Los capiteles, tallas y herrajes son geométricos simplificados. Las alturas son
parámetros de modelado, no cálculos estructurales. Las esquinas de cajón en esta
versión son ortogonales. No se simula la apertura de carpinterías del cajón ni
colisiones de puertas móviles con la baranda. Los recorridos y geometrías
inválidos se rechazan; no se deben interpretar las pruebas como parecido visual.
