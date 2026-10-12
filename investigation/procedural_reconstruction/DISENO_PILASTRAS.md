# Pilastras, semicolumnas y columnas

## Catálogo y archivos para revisar

Ejecutar desde `investigation/procedural_reconstruction`:

```bash
python3 steps/step23_fresh_theta/generar_pilastras.py
```

Salida: `steps/step23_fresh_theta/catalogo_pilastras/`.

- **25 GLB individuales:** una pieza por variante, a una escala representativa.
- **5 conjuntos:** `00_conjunto_<estilo>/building.glb`, cinco variantes en fila.
- **5 anclajes:** `01_anclaje_*`, edificios completos con pilastra adosada,
  semicolumna, columna exenta, pilastra de esquina y colocación en segundo nivel.
- `index.json` y `README.md`: índice, orden de las piezas y enlaces.

No se enumeran todas las combinaciones de dimensión, material, sección y anclaje.
Cada carpeta incluye request JSON, miembros resueltos y validación. En los GLB
individuales se exporta solamente la pieza: su request reconstruye también el
edificio de referencia. No se generan imágenes ni renders.

## Familias

| Familia | Variantes |
|---|---|
| Republicano | `smooth_moulded`, `recessed_panel`, `restrained_fluted`, `rusticated`, `portico_column` |
| Barroco | `scroll_pilaster`, `leaf_pilaster`, `salomonic`, `estipite`, `composite_column` |
| Clásico | `tuscan`, `doric`, `ionic`, `corinthian`, `panel_pilaster` |
| Madera | `chamfered_post`, `turned_post`, `octagonal_post`, `joinery_pilaster`, `saddle_post` |
| Moderno | `plain_prism`, `plain_cylinder`, `oval_column`, `grooved_pilaster`, `tapered_column` |

Las categorías son familias procedurales, no una clasificación histórica
exclusiva. Los capiteles de hojas/volutas son interpretaciones simplificadas.
El poste liso y el prisma moderno pueden no tener basa ni capitel.

## Contrato reutilizable

`MemberDesign` define el diseño sin imponer dimensiones ni ubicación. Puede
utilizarse en:

- `theta.vertical_members[].design`.
- `FacadeProjection.member` para proyecciones de pilastras existentes.
- `DoorControls.portal_member` para portadas.
- `BalconyControls.column_member` para postes altos de galerías/cajones.
- `SupportControls.member` para apoyos de masas.
- `FacadeSection.member` para columnas de logias/pórticos.

Las dimensiones de los últimos cinco consumidores proceden de su contrato
existente: no se duplican controles de posición.

Ejemplo dentro de un theta completo:

```json
{
  "architectural_style": "republicano",
  "vertical_members": [{
    "id": "pilastra_portal",
    "mass_ref": "principal:0",
    "edge": 0,
    "u_m": 1.4,
    "bottom_m": 0,
    "height_m": 3.2,
    "width_m": 0.55,
    "depth_m": 0.28,
    "placement": "attached",
    "design": {
      "style": "auto",
      "variant": "recessed_panel",
      "material": "plaster",
      "base_profile": "attic",
      "base": true,
      "capital": true,
      "collar": true,
      "abacus": true,
      "detail": 2
    }
  }]
}
```

`u_m` es el **eje central**, desde el inicio de la arista canónica. `bottom_m`
es relativo a la base de la masa. La altura debe caber en una banda visible.
Se usa el plano desplazado de la fachada cuando lo hay. Si varias zonas
coinciden con el anclaje se rechaza la ambigüedad.

### Colocaciones

- `attached`: la sección queda frente al muro; la espalda del fuste toca el
  plano y las molduras pueden penetrarlo ligeramente.
- `embedded`: `embed_ratio` indica la fracción de profundidad hundida. `.5`
  coloca el eje de una semicolumna sobre el plano; no aplasta la sección.
- `freestanding`: `offset_m` es la distancia del eje hacia fuera del muro.
- `corner`: el eje debe coincidir con un extremo de la arista y una esquina
  ortogonal. Hay una sola pieza completa, con basa/capitel continuos.

`offset_m` desplaza también las piezas adosadas/embebidas cuando se solicita.
El empotramiento es intersección controlada con el muro, no una operación que
cree un nicho alrededor del elemento. No se excavan huecos automáticamente.

### Diseño

- `section`: `auto`, `rectangle`, `rounded`, `chamfered`, `octagon`, `circle`,
  `ellipse`. Una sección circular exige ancho y profundidad iguales.
- `base`, `capital`: `null` utiliza la variante; `false` desactiva la parte.
- `base_profile`: `auto`, `attic`, `simple`, `minimal`.
- `base_height_m`, `capital_height_m`: alturas explícitas opcionales.
- `pedestal_m`: pedestal opcional, dentro de la altura total.
- `collar`, `abacus`: activan el relieve correspondiente del perfil superior.
- `taper`: reducción relativa de sección al llegar arriba; `null` usa variante.
- `entasis`: ensanchamiento suave del fuste en familias de mampostería.
- `flute_count`: número objetivo de acanaladuras, con límites por sección.
- `turns`: vueltas del fuste salomónico.
- `ornament`: volutas, hojas y zapatas opcionales.
- `detail`: 1–3, muestreo de curvas; no cambia medidas generales.
- `material`, `base_material`, `capital_material`: slots existentes, incluyendo
  slots personalizados de `theta.materials`. El color se configura allí.

Paneles rehundidos requieren una sección rectangular compatible. Salomónicas
requieren círculo o elipse. Las combinaciones inválidas producen un error, no
una deformación arbitraria para hacerlas caber.

## Construcción geométrica

`vertical_member_profiles.py` define secciones y perfiles longitudinales.
`vertical_member_sweep.py` construye anillos y los une en un loft cerrado:

- Fuste constante: sweep vertical.
- Fuste afinado, torneado o estípite: secciones variables.
- Basa y capitel: sección recorrida por un perfil curvo continuo.
- Estrías: concavidades reales en la sección.
- Paneles: rehundimiento del fuste con bordes y transiciones.
- Almohadillado: juntas y biseles distribuidos según altura.
- Salomónica: relieve helicoidal continuo, muestreado según vueltas y detalle.

`vertical_member_ornaments.py` produce volutas mediante curvas y hojas mediante
lofts cerrados; la zapata de madera tiene una silueta propia.

El muestreo usa posiciones compartidas entre anillos y tapas trianguladas con
GEOS. Los recortes por visibilidad y envolvente se cierran con nuevas tapas;
no se descartan caras fuera del plano dejando mallas abiertas. La traslación
de altura se realiza una sola vez, también dentro de fachadas por piso.

Cada parte tiene semántica `member_shaft`, `member_base`, `member_capital`,
`member_pedestal`, `member_leaf`, `member_volute` o `member_saddle`.
Los miembros explícitos usan `vertical_member/<id>` como ensamblaje.

## Sustitución de los generadores anteriores

- `prefabs_facade.pilaster` es ahora un adaptador al motor común.
- `ornaments.classical_pilaster` traduce nombres antiguos; se eliminó su
  geometría de basas/capiteles hechos con cajas apiladas.
- Las pilastras automáticas de borde usan el mismo motor.
- Proyecciones de órdenes y portales pasan por esos adaptadores.
- Las portadas de puertas ya no apilan tambores para formar columnas.
- Galerías, columnas de logia y apoyos de masas utilizan el catálogo.

Los nombres antiguos siguen decodificando para permitir la migración de
requests. No activan un generador geométrico paralelo. Las franjas de concreto
dentro de muros estructurales mantienen su función: no son pilastras decorativas.
Las relaciones de apoyo conservan IDs y niveles del sistema de masas.

## Validación y límites

El resolver verifica estilo heredado, materiales, dimensiones, anclajes,
visibilidad, esquina ortogonal, envolvente, conflictos con vanos y duplicación
de miembros/proyecciones explícitas. Los consumidores existentes mantienen sus
reglas de colocación y pueden recortar la pieza en su dominio visible.

La altura total se conserva al activar/desactivar remates: cambia el largo del
fuste. Los perfiles se dimensionan con límites proporcionales. La geometría
rectangular simple es deliberada en diseños modernos; no se obliga a redondear
todas las piezas.

Los encuentros con molduras del muro conservan su anclaje común, pero no hacen
una unión booleana global de todas las piezas de la fachada. Los ornamentos
son simplificados y los materiales no determinan capacidad estructural.
La validación de malla no reemplaza la revisión visual de los GLB.
