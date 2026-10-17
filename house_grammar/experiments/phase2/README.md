# Fase 2 — profundidad y articulación exterior

Entrada: `intent-v1`; salida: `articulation-plan-v1` mediante
`planning.articulation.plan_articulation(request)`. Las coordenadas siguen siendo
calculadas por el compilador; el LLM elige operaciones y categorías cualitativas.

## Implementación

- `recess`: retranqueo parcial real del cuerpo.
- `depth_rhythm`: sectores proporcionales con planos base, entrante y saliente.
  El plano saliente coincide con la envolvente inicial; el base está a media
  profundidad y el entrante a profundidad completa. No invade el lote vecino.
- `floor_shift`: reserva lateral y desplazamiento alternado entre pisos (o lado
  explícito). En plantas irregulares incompatibles se emite diagnóstico.
- `loggia`, `portico`, `vestibule`: espacios excavados que conservan suelo,
  techo, retornos laterales y acceso al cuerpo. Pórtico y vestíbulo comparten el
  constructor espacial; su ancho/profundidad distinguen la configuración.
- `balcony`: suelo saliente sin cubierta propia, con acceso y protección.
  Necesita espacio dentro del lote; si no cabe, se solicita retiro mediante
  `space_outside_parcel`, sin recortar silenciosamente el balcón.
- Protección continua de 1.05 m para desniveles mayores de 0.60 m. Entradas de
  PB mantienen una abertura exterior. Escaleras/rampas de acceso son Fase 5.
- Suelos referidos a `levels_m`: espesor bajo la cota de acabado, no sobre ella.
- `enclosed_geometry` y superficies recalculadas tras excavar espacios.
- Unión de sólidos por celdas XY y niveles Z: interfaces internas eliminadas,
  retornos cerrados y sin caras compartidas duplicadas en la malla exportada.

Los accesos son huecos/pockets de 0.90 × 2.10 m conectados al cuerpo con estado
`reserved_for_phase3`. No existe todavía un ambiente interior ni circulación:
Fase 3 deberá consumir esas reservas. Tampoco hay carpinterías de puerta aún.
Los apoyos siguen siendo conceptuales, no cálculo estructural.

**Limitación de autocompletado:** esta fase construye articulaciones solicitadas;
todavía no decide añadir logias, balcones o ritmos cuando se omiten. Solo 5 de
los 20 casos originales solicitan articulaciones de Fase 2. Las comparaciones
las piden explícitamente. Aprobar geometría no demuestra variedad arquitectónica
autocompletada; ese objetivo general sigue pendiente.

## Verificación

113 pruebas pasan (contrato, masas y articulación). Banco sintético congelado:
20 casos × 3 semillas = 60/60, incluyendo exportación watertight, volumen positivo
y winding consistente. Ocho comparaciones adicionales del mismo lote: compacto,
centro retranqueado, logia derecha, alternancia, ritmo saliente, pórtico, vestíbulo
y balcón. Se revisaron plantas y vistas frontal/oblicua de logia, balcón y ritmo,
además de pórtico. No equivale a validación con fotografías de casas reales.

La comparación adicional detectó y corrigió un encuentro no manifold en PB:
la losa ahora continúa bajo el cuerpo y los retornos, en vez de tocar el muro
solo por una arista. Las ocho variantes finales pasan los tres checks de malla.
Entregas locales: `apps/experimento_paralelizacion/gramatica_adaptable/fase_2/resultados/`
y `apps/experimento_paralelizacion/gramatica_adaptable/fase_2/comparaciones/`.
Las corridas previas están en `fase_2/archivo/`. Resumen reproducible con hashes en `results.json`.

```bash
PYTHONPATH=house_grammar/src python3 -m pytest house_grammar/tests/test_building_intent.py house_grammar/tests/test_intent_massing.py house_grammar/tests/test_intent_articulation.py -q
PYTHONPATH=house_grammar/src python3 house_grammar/experiments/phase1/run.py --phase 2 --output /tmp/opencode/phase2-bank --seeds 7 17 81
PYTHONPATH=house_grammar/src python3 house_grammar/experiments/phase2/compare.py --output /tmp/opencode/phase2-comparison
```

Cada directorio debe ser nuevo. Exporta plan.json, massing.glb, summary.json,
preview.png y front.png. Colores oscuros señalan límites interiores de espacios
como ayuda diagnóstica; no son acabados definitivos.

Los tipos `crown` y `round_corner` continúan explícitamente pendientes. Las
profundidades iniciales 0.8/1.4/2.0 m son priors, no medidas observadas; en balcones
se limita el vuelo conceptual a 1 m. La unión exportada conserva semántica en
plan.json, pero aún no transmite IDs individuales de cada superficie al GLB.
