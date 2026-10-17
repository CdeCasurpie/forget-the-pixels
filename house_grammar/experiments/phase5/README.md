# Fase 5 — cerco, acceso y primer piso

Entrada: `envelope-plan-v1`; salida: `site-plan-v1` mediante
`planning.site_access.plan_site(request)`. El plan conserva la envolvente
completa y agrega piezas de sitio, portones, rutas y decisiones. Toda entrada
termina en la puerta o en el umbral **real** de Fase 4/Fase 3.

## Implementación

- Cerco físico de 0.16 m sobre el frente declarado: `solid`, `open`,
  `base_and_rail` y `partial`, alto (2.20 m) o bajo (1.15 m). `style` es
  independiente de la forma. `fence: false` deja el retiro libre; omitirlo
  en un jardín frontal solicita el prior de reja baja abierta. Sin retiro
  declarado no se inventa cerco.
- Huecos separados de portón peatonal (1.02 m) y cochera (2.72 m), alineados
  con la puerta y vano vehicular del edificio. Piezas de hoja/barrotes con
  jambas; `site.door.style` y `site.door.material` controlan el portón peatonal
  sin cambiar la forma/estilo del cerco. El cerco parcial
  conserva tramos realmente abiertos. Un remate de teja/calamina se materializa
  como tapa plana apoyada; sobre portón vehicular, una cubierta plana se
  apoya en sus dos jambas (todavía no se simulan pendientes ni tejas
  individuales). Medidor, timbre y numeración quedan anclados al costado.
- Ruta de 0.82 m para peatones y 2.20 m para vehículo, contenida en suelo
  libre; el pavimento llega al portón y al vano del edificio. Planta baja
  abierta: umbral sin hoja inventada. Edificio al borde de calle: acceso
  directo, sin pavimento fuera del lote.
- Desnivel: rampa si cabe a pendiente ≤1:12 (cuña cerrada) o escalones de
  contrahuella ≤0.17 m; si no hay carrera dentro del lote, conflicto
  `access_run`. No se resuelve un obstáculo con una ruta que atraviese masa:
  `access_blocked`/`access_outside_free` son diagnósticos localizados.
- `site.fence` y `site.access_route` se retiran de `pending`; cubierta,
  mobiliario e ingeniería continúan pendientes.

## Verificación y ejecución

```bash
python3 house_grammar/experiments/phase5/build_cases.py
PYTHONPATH=house_grammar/src python3 -m pytest house_grammar/tests/test_intent_site.py -q
PYTHONPATH=house_grammar/src python3 house_grammar/experiments/phase5/run.py \
  --output /tmp/opencode/phase5-review --seeds 7 17 81 \
  --comparisons /tmp/opencode/phase5-comparisons
```

Cada salida debe ser un directorio nuevo. `plan.json`, `summary.json`,
`site.glb`, `preview.png`, `ground.png` y `front.png` muestran y auditan los
sólidos del edificio **más** los del sitio. El audit exige piezas watertight y
`group_overlap_m3` nulo entre materiales. `results.json` guarda hashes de
fixtures, estado y expectativas. El banco congelado de Fase 0 tiene 20
casos; 11 fixtures sintéticos cubren:

| Caso | Alcance |
|---|---|
| `p5_high_fence_hidden` | muro alto, accesos peatonal y vehicular, remate de teja |
| `p5_low_open_rail` | reja baja abierta con postes, rieles y barrotes |
| `p5_base_and_rail` | zócalo bajo, reja y tapa apoyada |
| `p5_open_setback` | jardín y acceso sin cerco (`false`) |
| `p5_partial_fence` | paños parciales y sector abierto |
| `p5_garage_without_fence_gate` | cochera sin portón independiente en cerco |
| `p5_street_edge` | puerta al borde de calle, sin pavimento exterior |
| `p5_covered_portal` | cubierta de calamina sobre portón apoyada en jambas |
| `p5_raised_steps` | desnivel resuelto con escalones |
| `p5_raised_ramp` | desnivel resuelto con rampa ≤1:12 |
| `p5_auto_low_fence` | completado activo con espacio frontal y cerco omitido |

Seis comparaciones del mismo lote/casa (`solid_high`, `open_low`,
`base_and_rail`, `partial`, `unfenced`, `covered_vehicle_portal`) exportan
`comparisons.json` y mallas/vistas independientes.

## Límite deliberado

El trazado en esta etapa es recto y debe caber completamente en suelo libre;
no inventa servidumbres ni un giro alrededor de obstáculos. Geometría de
remates, herrajes y normativa municipal requieren desarrollo posterior. La
verificación ingenieril sigue marcada `false`.
