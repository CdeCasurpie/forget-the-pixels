# Cercos: usar UNICAMENTE el catálogo

Regla: todo cerco y todo portón se genera con `build_fence` del catálogo.
Fuente única de estilos: `house_grammar/src/domain/fence_catalog.py:3`.
Constructor: `house_grammar/src/modeling/fences.py:10`.
No existe otro constructor válido. Las rutas legacy (`site.py:draw_fence`,
cajas en `grammar.py:_boundary_and_garden_body`) fueron eliminadas.

Estilos válidos (exactos, minúsculas):

- `republicano`
- `barroco`
- `moderno`
- `clasico`
- `madera`

`none` (theta automático) y `open` (puerta/gramática histórica) significan
ausencia, no son estilos. Prohibido: `reja`, `concreto`, `ladrillos`,
`concreto_bajo`, `solid_wall`, `wall`, `fence` como estilo. El validador los
rechaza sin conversión silenciosa.

## Dos formas de configurar

### A. Automático (un estilo para todo el frente)

```json
"site": {"fence": "republicano", "garden": false, "runs": null, "zones": []}
```

- Frente: el estilo elegido, 2.1 m, portón peatonal auto 1.1 m + cochera auto
  2.9 m si el tramo lo permite (`boundaries.py:79`).
- Linderos libres sin edificio: cerramiento macizo `clasico`, `brick`, 2.6 m,
  sin puertas (`boundaries.py:98`).
- `"fence": "none"` = sin cercos.

### B. Tramos explícitos (control total; obligatorio `fence: none`)

```json
"site": {
  "fence": "none",
  "garden": false,
  "runs": [
    {
      "edge": 1, "start_m": 0.0, "end_m": 15.03,
      "kind": "republicano", "height_m": 2.8,
      "height_mode": "high", "wall_material": "plaster",
      "gate_u": 4.86, "gate_width": 1.1,
      "garage_u": 11.48, "garage_width": 2.9,
      "gate_mode": "auto", "garage_mode": "auto",
      "openness": 0.3, "planters": false,
      "plinth": null, "base_height_m": null
    }
  ],
  "zones": []
}
```

Validación (`modeling/theta.py:214`):

- `runs != null` exige `fence == "none"`.
- `height_m` 0.65–4. `height_mode`: `high` | `low`.
- `wall_material`: `plaster` | `brick` | `stone` | `concrete`.
- `gate_u/garage_u`: metros desde `start_m` del run (pese al sufijo `_u`).
  `gate_width/garage_width > 0` si la `u` existe; sin traslapes; sin invadir
  edificio; runs del mismo `edge` sin traslaparse.
- `gate_mode/garage_mode`: `auto` (dibuja hojas del mismo estilo) | `open`
  (deja el vano libre).
- `openness` 0.1–0.7. Solo tiene efecto en `moderno`/`madera`.
- `planters: true` solo en `moderno` y en tramos > 0.8 m.
- `plinth`: zócalo sobre base/postes/muro macizo del mismo `wall_material`;
  no afecta estacas de madera.
- `base_height_m`: altura explícita de base maciza. Default: 0.40 (`high`) /
  0.24 (`low`). Ignorado en `madera` (no lleva base maciza).

Muestras copiables (10 = 5 estilos × high/low):
`house_grammar/steps/step23_fresh_theta/catalogo_cercos/<estilo>_<high|low>/request.json`.
Alto de muestra: 2.8 m; bajo: 1.1 m.

## Qué dibuja cada estilo (palabras clave reales)

Común a los 5: postes + remate (`boundary_post`, `post_cap`) en cortes y
puertas; hojas con marco, bisagras y tirador (`gate_frame`, `gate_hinge`,
`gate_handle`); peatonal 1 hoja, cochera 2 hojas; `open` omite hojas.

| `kind` | Geometría | Keywords que sí le afectan |
|---|---|---|
| `republicano` | Base albañilería (`boundary_base`), barrotes (`fence_bar`), rieles (`fence_rail`), aros (`fence_ring`), puntas (`fence_spear`, solo `high`) | `height_m`, `height_mode`, `wall_material`, `base_height_m`, `plinth`, puertas |
| `barroco` | Como republicano pero espirales pareadas (`fence_scroll`) en vez de aros; puntas solo en `high` | igual que republicano |
| `moderno` | Lamas horizontales (`fence_louver`), base con reveal (`modern_reveal`), jardineras opcionales (`planter_wall`, `planter_soil`, `planter_shrub`) | `openness` (hueco entre lamas), `planters`, resto común |
| `clasico` | Muro macizo (`fence_wall`); hojas paneladas con bastidor realzado (`gate_panel`, `gate_stile`, `gate_rail`) | `wall_material`, `plinth`, puertas; `openness`/`planters`/`base_height_m` sin efecto útil |
| `madera` | Estacas de punta (`fence_picket`), travesaños (`wood_rail`), diagonal en hoja (`gate_brace`); postes/madera fijos en `wood` | `openness` (separación), puertas; `wall_material` solo afecta jardineras (no hay), `plinth`/`base_height_m` sin efecto |

Notas finas verificadas en código:

- `height_mode` solo cambia: punta 0.16 m vs 0.02 m y base default en
  estilos de hierro. No cambia lamas, paneles ni estacas.
- `madera` ignora `wall_material` en postes/estacas/rieles (siempre `wood`).
- `clasico` en hoja usa `metal` para paneles/bastidor aunque el muro sea
  albañilería.

## Si algún día se toca el catálogo, tocar AQUÍ

1. `house_grammar/src/domain/fence_catalog.py` — `FENCE_STYLES` + validador.
   Nada fuera de esa tupla es seleccionable.
2. `house_grammar/src/modeling/fences.py` — `build_fence`, `infill`, puertas,
   postes. Prohibido crear otro constructor en `site.py`/`grammar.py`.
3. `house_grammar/tests/test_fence_styles.py` — alta/baja × 5 estilos, hojas,
   rechazo legacy, runs theta, automático vs medianero.
4. `house_grammar/steps/step23_fresh_theta/catalogo_cercos/` — regenerar las
   10 muestras si cambia la geometría.
5. `house_grammar/docs/guia_theta/CATALOGOS.md` §12 — vocabulario de referencia.
