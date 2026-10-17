# Fase 3 — plantas interiores y circulación

Entrada: `intent-v1`; salida: `interior-plan-v1` mediante
`planning.interiors.plan_interiors(request)`. Las coordenadas siguen siendo
calculadas por el compilador; el LLM no aporta geometría interior.

## Implementación

- **Núcleo vertical.** Plantillas de escalera y baño lado a lado, apiladas o con
  la escalera girada (plantas anchas y poco profundas). La escalera usa paso
  0.18 m, huella 0.27 m, ancho 0.95 m y descanso de 1.10 m; baño 1.70 × 2.50 m y
  ducto 0.40 m. Los tramos de cada piso son continuos (subida, descanso,
  segunda mitad) y arrancan en el nivel del piso.
- **Circulación.** Corredor de 1.20 m; si el cuerpo es estrecho se reintenta con
  1.00 m y el ancho real queda registrado como `corridor_width_m`. La región
  transitable se erosiona a media anchura para el grafo de visibilidad, y el
  corredor dibujado se recorta a la planta útil.
- **Partición por piso.** Árbol binario de cortes con zonas protegidas (vanos de
  fachada, accesos a espacios exteriores, núcleo) y cortes preferidos entre
  ventanas contiguas de una misma fachada, de modo que cada vano tienda a mirar
  a su propio ambiente. Las astillas inusables se absorben a la circulación si
  la tocan; nunca se descarta área.
- **Puertas.** Hojas de 0.85 m (baño) o 0.90 m sobre muros compartidos reales,
  eligiendo el segmento más largo disponible; el árbol de conexiones se expande
  desde el recibidor y no atraviesa baños, escaleras ni cocheras.
- **Ventanas.** Cada ventana reservada en fachada pertenece a un único ambiente
  usable (sala, dormitorio o servicio; nunca circulación, escalera o cochera).
  La ventana pequeña alta busca un ambiente de servicio. La selección de
  alternativa penaliza vanos que comparten ambiente.
- **Cochera.** 2.90 × 5.20 m en planta baja con acceso vehicular propio desde
  la calle; no puede ser paso hacia otros ambientes ni recibir ventanas.
- **Espacios exteriores.** Logias, pórticos y vestíbulos (reservados en Fase 2)
  se conectan a un único ambiente del piso, con abertura real de 0.60 m o más.

## Comando

```bash
PYTHONPATH=house_grammar/src python3 house_grammar/experiments/phase3/run.py \
  --output /tmp/opencode/phase3-review --seeds 7 17 81
```

El directorio de salida debe ser nuevo. Por cada corrida se genera
`plan.json`, `summary.json`, `preview.png` (plantas en una tira) y
`floors/floorN.png`. `results.json` resume estado, ambientes, anchos de
circulación, ventanas y expectativas.

## Fijaciones de experimento

`build_cases.py` genera seis fixtures sintéticos. El runner evalúa sus
expectativas y las pruebas de `test_intent_interiors.py` las revalidan.

| Caso | Expectativa |
|---|---|
| `p3_two_large_windows` | dos ventanas grandes, cada una en un ambiente distinto |
| `p3_three_unequal_windows` | tres proporciones distintas sobreviven al reparto |
| `p3_small_high_window` | la ventana pequeña alta cae en servicio, nunca en dormitorio |
| `p3_garage_independent` | cochera con acceso propio y sin funciones de paso |
| `p3_upper_floor_different` | las ventanas pedidas viven solo en el piso superior retranqueado |
| `p3_connected_loggia` | la logia del piso 2 conecta con un solo ambiente |

## Límites

- Plantas esquemáticas: zonas, muros y conexiones; todavía sin mobiliario,
  aparejos ni espesores constructivos completos.
- El banco congelado solo pide ventanas en dos casos (12 y 19); los fixtures de
  arriba cubren la relación vano–ambiente.
- Dos viviendas por piso queda como trabajo posterior, indicado en el plan.
- Los patios de 06 y 14 se recolocan con el margen de 1.45 m que exige la
  circulación de Fase 3; por eso Fase 1 y 2 se regeneraron con el mismo código.
