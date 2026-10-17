# Fase 4 — vanos y envolvente constructiva

Entrada: `interior-plan-v1`; salida: `envelope-plan-v1` mediante
`planning.envelope.plan_envelope(request)`. El compilador dimensiona vanos,
muros, losas y carpintería; el LLM no aporta medidas.

## Implementación

- **Vanos métricos.** Jambas, antepecho y dintel por uso y proporción
  (`vertical`, `horizontal`, `square`, `small_high`). Antepechos: 1.50 m para
  `small_high`; 1.20 baño/servicio; 1.05 cocina-comedor; 0.70 sala; 0.60
  tienda; 0.90 resto. Dintel libre 0.20 m (`LINTEL`). Si la banda pedida no
  cabe en la altura útil, el vano se limita al máximo y la adaptación queda
  como decisión explícita.
- **Muros huecos.** Muro exterior 0.18 m, partición 0.12 m; los sólidos son
  prismas por bandas de altura entre los niveles relevantes (sin CSG). Las
  particiones no terminan en revelas exteriores y los cortes interiores
  sobrepasan 1 cm para atravesar encuentros sin invadir el muro exterior.
  Muros y particiones ceden ante columnas y zócalos, y cada pieza se sanea
  antes de extruirse (sin vértices sub-micrométricos ni anillos degenerados)
  para que el GLB salga cerrado.
- **Puertas.** La línea reservada por Fase 3 permanece; si el marco choca se
  desplaza a lo largo del mismo muro compartido (extremos medidos por sondeo
  de cobertura de ambos ambientes). Los muros dobles delgados con puertas
  enfrentadas se aceptan: las revelas se fusionan y se registran como decisión.
- **Carpintería.** Marcos, hojas y vidrio con micro-retranques de 1 mm (sin
  caras coplanares entre materiales). Hojas por mecanismo: `guillotine`
  (dos hojas horizontales), `sliding`/`casement`/`hinged` (dos si el ancho
  supera 1.30 m), `awning` y `fixed` una. Perfil de marco por estilo:
  0.045 m moderno, 0.06 madera/clásico, 0.065 republicano, 0.07 barroco.
  Mecanismo derivado si se omite: `vertical` → `casement`, `horizontal` →
  `sliding`, `small_high` → `awning`; cochera `sliding` + `metal`; entrada
  peatonal `hinged`. Material y estilo de puerta son independientes del estilo
  global (`site.door` como objeto; materiales `wood`, `metal`, `glass`).
- **Completado.** Una ventana por ambiente perimetral habitable en ámbitos no
  declarados (`<ambiente>/auto_window`); frentes nombrados con prioridad, el
  borde del lote es muro mediero y `facades: []` desactiva el completado.
- **Losas y soportes.** Una losa de 0.18 m en cada datum; las intermedias
  excluyen escalera y ducto, la superior los cubre. Columnas y zócalos del
  planeamiento de masas se materializan como piezas propias. Las logias
  aportan antepecho de 1.05 m.
- **Decisiones y pendientes.** Vocabulario auditado: proporción adaptada,
  cabeza limitada por losa y dintel, completado en frente no especificado,
  desplazamiento en el mismo muro y revelas fusionadas. `pending` reserva
  `roof`, `site.fence`, `site.access_route` e `interior.furniture` para fases
  posteriores.

## Comando

```bash
python3 house_grammar/experiments/phase4/build_cases.py
PYTHONPATH=house_grammar/src python3 house_grammar/experiments/phase4/run.py \
  --output /tmp/opencode/phase4-review --seeds 7 17 81 \
  --comparisons /tmp/opencode/phase4-comparisons
PYTHONPATH=house_grammar/src python3 -m pytest house_grammar/tests/test_intent_envelope.py -q
```

Los directorios de salida deben ser nuevos. Por corrida se genera `plan.json`,
`summary.json`, `envelope.glb` (una pieza cerrada por sólido, coloreada por
material), `preview.png`, `front.png`, `elevations/<frente>.png` y
`floors/floorN.png`. `results.json` resume estado, conteos, mecanismos, estilos
y el audit (`watertight`, `group_overlap_m3`, `materiales`); en una corrida
sana, todas las corridas son `watertight` y `group_overlap_m3` queda en 0.
`compare.py` puede correrse aparte para exportar las seis comparaciones.

## Fijaciones de experimento

`build_cases.py` genera diez fixtures sintéticos; el runner evalúa sus
expectativas y `test_intent_envelope.py` las revalida.

| Caso | Expectativa |
|---|---|
| `p4_fixed_count_narrow` | tres ventanas por piso en 8 × 20 m; anchos menores que en lote ancho |
| `p4_fixed_count_wide` | el mismo conteo en 16 × 13 m produce vanos más anchos |
| `p4_low_ceiling` | con 2.70 m de piso útil, ninguna cabeza supera 2.32 m |
| `p4_tall_floor` | con 3.80 m, las ventanas horizontales alcanzan 1.00 m de alto |
| `p4_raised_ground` | con el piso en 0.50 m, toda elevación es relativa al piso |
| `p4_staggered_distribution` | los pisos alternos desplazan sus vanos dentro de la celda |
| `p4_modern_frame_republican` | carpintería moderna admitida; el completado hereda el estilo republicano |
| `p4_guillotine_tracks` | guillotina de dos hojas horizontales en madera |
| `p4_door_materials` | puerta de calle clásica en metal, independiente del estilo |
| `p4_completion_upper_floor` | los pisos declarados quedan cerrados; los demás completan |

## Comparaciones

Seis variantes de una misma casa exportan su tabla de diseño
(`comparisons.json`): `joinery_republican_wood`, `joinery_modern_metal`,
`joinery_classic_pvc`, `doors_wood`, `doors_metal` y `doors_glass`.

## Límites

- Sin unión booleana entre piezas: un GLB por sólido; el vidrio es opaco claro
  en el GLB y semitransparente solo en los renders.
- Las revelas fusionadas de muros dobles delgados se registran, no se ocultan;
  una planta baja abierta difiere la puerta de calle a la fase de acceso.
- Verificación ingenieril pendiente (`engineering_verified: false`); sin
  acabados, mobiliario ni cubierta (Fases 5–8).
