# Puertas y portones vinculados — primera iteración

## Activación y estilo

Una abertura `kind: door` o `gate` activa el ensamblaje nuevo al incluir `door`.
`door.model: auto` hereda `theta.architectural_style`, con las mismas cinco familias
de ventanas: republicano, barroco, clásico, madera y moderno. Se rechaza un modelo
que contradiga el estilo del edificio. Las aberturas sin `door` conservan su ruta.

El perfil utiliza el catálogo `PROFILES` compartido con ventanas. El vano y todos
los anillos se derivan de `opening_shape`; no se coloca un marco rectangular
independiente sobre un vano curvo.

## Modelo de datos

Ejemplo de Opening (requiere contexto y theta como el resto de aberturas):

```json
{
  "kind": "gate", "u_m": 2.0, "v_m": 0.1,
  "width_m": 3.2, "height_m": 3.4,
  "shape": "arch", "arch_rise_m": 0.6,
  "frame_width_m": 0.12, "frame_depth_m": 0.14, "recess_m": 0.2,
  "door": {
    "model": "auto", "leaves": 0, "construction": "panelled",
    "leaf_material": "wood", "frame_material": "frame",
    "portal": "columns", "portal_width_m": 0.28,
    "portal_gap_m": 0.12, "portal_depth_m": 0.24,
    "portal_material": "plaster", "cornice": true,
    "transom_height_m": 0.55, "transom_infill": "glass",
    "transom_grille": true, "grille_pattern": "scrolls",
    "threshold": true, "opening_angles_deg": [0, 0]
  }
}
```

### Dimensiones, hojas y apertura

- Formas: `rectangle` y `arch`, con elevación ajustable del arco.
- `leaves: 0`: una hoja hasta 1,35 m de ancho útil; dos desde ese ancho.
  `1` o `2` fijan explícitamente la composición.
- Los paneles se repiten aproximadamente cada .8 m de ancho y .95 m de altura.
  Las tablas, lamas y barras mantienen su espesor y varían su cantidad.
- `opening_angles_deg`: un ángulo por hoja, entre 0 y 110 grados, apertura exterior.
  Rota bastidor, relleno y herrajes alrededor de la jamba. No incluye análisis de
  colisión con vecinos/columnas durante el giro: comprobar el espacio disponible.
- `transom_height_m: 0` lleva las hojas hasta el arco. Un valor positivo separa
  una sobreluz fija superior con travesaño. Se exige paso de al menos 1,5 m.

### Construcción de la hoja

`auto` elige paneles para republicano/barroco/clásico, tablas para madera y lamas
para moderno. Opciones explícitas: `panelled`, `glazed`, `grille`, `boards`, `louvers`.

Todas llevan bastidor, herrajes y manija; el moderno usa tirador largo. Los paneles
tienen backing hundido, cuarterones y anillos de moldura. La construcción `grille`
no tiene una placa opaca detrás. `glazed` admite `leaf_grille: true`.

`grille_pattern`: `auto`, `vertical`, `grid`, `rings`, `scrolls`.
Auto usa aros para republicano, volutas para barroco y barras para los demás.
`grille_spacing_m` controla repetición. Se recorta la geometría al paño disponible.
`transom_grille` es independiente de la reja de hoja, y `transom_infill` admite
`glass` u `open`. En esta ruta usar estos controles, no el booleano legacy `grille`.

### Cerco propio y portada exterior

El cerco sigue el vano y su espesor se aloja dentro de él. `portal` permite
`none`, `pilasters` o `columns`; las columnas tienen fuste circular y piezas de
base/capitel, las pilastras son planas. `cornice` añade tres cursos superiores.
Anchura, separación y profundidad se expresan en metros, relativas al vano.
Se rechazan portadas fuera de fachada o que invadan otras aberturas.

El umbral sustituye al alféizar y se activa con `threshold`.

### Materiales manuales

`leaf_material` y `frame_material` admiten `auto`: madera para hojas tradicionales,
metal para modernas; marco `frame`, o `wood` para estilo madera. Pueden sustituirse.
`portal_material`, `metal_material`, `glass_material`, `threshold_material` también
son configurables con slots existentes. Colores/texturas: `theta.materials`.
Los slots son compartidos por el edificio; todavía no existen slots exclusivos
para colorear cada puerta independientemente de las demás piezas.

## Generación, catálogo y casa salmón

Desde `house_grammar`:

```
python3 steps/step23_fresh_theta/generar_puertas.py
```

Produce `catalogo_puertas/`: 5 estilos × 2 formas × 2 tamaños (puerta/portón),
con GLB, Opening JSON y validaciones. Los portones clásicos/barrocos muestran
columnas; republicanos muestran pilastras. Los modernos anchos son acristalados.

`lotes/1134299_casa_salmon_republicana/puertas_vinculadas/` contiene request
completo y GLB con la puerta principal arqueada/calada y el portón lateral
panelado. Se heredan base, ventanas y cerco de `ventanas_vinculadas/request.json`.
Se guarda el registro de los tres elementos de portada reemplazados. La cornisa
horizontal de la fachada se conserva. No se inventa una sobreluz en esa puerta.

## Alcance

Son modelos procedurales iniciales: perfiles geométricos, paneles, aros/volutas,
columnas y herrajes. No son reproducciones escultóricas de las referencias.
No incluye todavía mamparas plegables, corredizas, aldabas complejas ni capiteles
corintios. La ruta se amplía sin cambiar posición y forma de la abertura.
No se generan renders ni comparativas en esta iteración.
