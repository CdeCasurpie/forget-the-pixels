# R3 — Vanos de catálogo dimensionados conjuntamente

La ruta exterior de `plan_envelope()` reserva los huecos en el muro, sin crear
habitaciones, y `planning.catalogue_openings.materialize_openings(plan)` llama a
`opening_catalog.build_opening` para **cada** ventana y puerta: un vano, una
pieza. La exportación incluye esas piezas reales en el GLB y en las vistas, sin
emitir `_joinery` en la ruta nueva (esa carpintería queda sólo para la ruta
interior histórica `interiors=True`, que no cambia).

## Dimensionado conjunto (`planning/openings_plan.py`)

`openings_plan.solve_bays` resuelve en un solo paso ancho, reparto y ritmo. Las
bandas por familia son **disjuntas**, y por eso el resultado cumple la lectura
de R3: una ventana principal siempre es mayor que un respiradero.

| familia | proporción de catálogo | ancho admisible (m) |
|---|---|---|
| `storefront` | `horizontal` | 2.00 – 4.50 |
| `horizontal` | `horizontal` | 1.20 – 3.00 |
| `vertical` | `vertical` | 1.00 – 1.55 |
| `square` | `square` | 0.90 – 1.45 |
| `small_high` | `small_high` | 0.45 – 0.80 |

- **Márgenes desde el borde del vano**, no desde el centro: ventana ≥ 0.85 m,
  puerta ≥ 1.00 m hasta el extremo del paño.
- **Portal reservado**: `margin_for(kind='door', portal=…)` suma
  `PORTAL_GAP_M + PORTAL_WIDTH_M` (0.34 m) al margen de la puerta y
  `_door_clearance` deja el mismo volumen libre entre la puerta y las ventanas,
  así las pilastras o columnas nunca cruzan el extremo del muro ni pisan un
  vano vecino.
- **Pilastra entre vanos** (0.55 m) separa ventanas; *no* es el margen de
  extremo, de modo que no se aplica dos veces.
- **Reparto** `balanced | left | right | grouped`, con `weights` opcionales por
  vano. Cada vano se mantiene dentro de su banda: si el paño no alcanza, el
  solucionador devuelve `None` y un pedido explícito falla con
  `window_capacity` en vez de encoger una ventana a un tamaño irreal.
- **Tipología automática** cuando el LLM no declara fachada: comercio →
  `storefront` continua; oficina → tres `horizontal`; multifamiliar en frente
  ≥ 9 m → tres `vertical`; vivienda → dos `vertical`.

## Contornos, normales y estanqueidad

Las fachadas pueden pedir `windows.shape` (`rectangle`, `arch`, `circle`,
`ellipse`), `windows.grille`, `windows.grille_pattern` y `windows.sill`; la
entrada acepta `site.door.shape` (`rectangle`, `arch`), `site.door.transom`
(`none`, `glass`, `open`) y `site.door.portal` (`none`, `pilasters`,
`columns`).

- Los paños con algún vano no rectangular se sustituyen por una extrusión
  cerrada del dominio vertical donde **la abertura se sustrae con
  `opening_shape` del mismo `Opening`** que construye el catálogo.
- El catálogo se barre hacia el exterior (`host['normal']`, hacia la calle) y se
  recorta contra el **sobre-ancho de fachada** (`street_envelope`: parcela más
  un delantal acotado sobre los frentes), igual que la ruta histórica. Sin ese
  sobre-ancho el recorte catastral borraba todas las bandas de perfil y las
  ventanas aparecían sin marco.
- Rejas, sobreluces, hojas, mecanismos y perfiles vienen del catálogo; el
  número de parteluces se deriva del ancho y el alto reales.

## Pruebas

- `tests/test_openings_plan.py` — bandas disjuntas, margen con reserva de
  portal, factibilidad honesta, reparto y pesos.
- `tests/test_catalogue_openings_exterior.py` — un `build_opening` por vano,
  principales > respiraderos, lotes estrechos/anchos, conflicto explícito,
  reserva de portal y pilastra, vitrina continua, contorno de catálogo por
  familia (rectángulo/arco/círculo/elipse), ejes y dinteles repetidos entre
  pisos, y ausencia de la carpintería duplicada.

## Banco visual

```
PYTHONPATH=house_grammar/src python3 house_grammar/experiments/r3/run.py \
    --output /home/cesar/r3-review
```

Diecinueve casos (tipologías, familias mixtas, lotes estrecho/ancho, arco,
círculo, elipse, portales, vitrina, esquina, deterioro, progresiva y adaptada).
Cada caso se audita antes de exportar: un vano por vano de catálogo, sin
tabiques, márgenes y bandas respetados, portal reservado, principales mayores
que respiraderos y `audit.watertight`. Escribe `manifest.json` con familias,
portales, formas, semánticas de catálogo y número de paños contorneados.

Comparación visual (las imágenes R2 permanecen inalteradas): familia mixta
principal/vertical/respiradero [mixed_families](review/mixed_families/front.png),
portal de columnas [portal_pilasters](review/portal_pilasters/front.png),
[arco con reja](review/arched_windows/front.png),
[balcón con puerta de catálogo](review/balcony_access/front.png),
[vitrina de comercio](review/mixed_use/front.png) y lotes
[estrecho](review/narrow_lot/front.png) / [ancho](review/wide_lot/front.png),
todos con `preview.png` oblicua en sus carpetas.

Terminar R3 no equivale a la aceptación arquitectónica: falta la revisión
visual del usuario sobre los renders por familia. No reemplazar sus perfiles de
catálogo por geometría simplificada.
