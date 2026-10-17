# Experimentos de la gramática adaptable

## Qué abrir

- **Fase 0 — contrato:** [casos y validación](../../../house_grammar/experiments/phase0/README.md). No genera maquetas.
- **Fase 1 — masas y vacíos:** [resultados definitivos](fase_1/resultados/).
- **Fase 2 — profundidad y espacios exteriores:** [comparaciones del mismo lote](fase_2/comparaciones/) y [banco completo](fase_2/resultados/).
- **Fase 3 — plantas interiores:** [banco y fijaciones](fase_3/resultados/). Cada corrida trae `preview.png`, `floors/floorN.png` y `plan.json`.

```text
gramatica_adaptable/
├── fase_1/
│   ├── resultados/     ← banco definitivo: 20 casos × 3 semillas
│   └── archivo/        ← corridas anteriores
├── fase_2/
│   ├── resultados/     ← banco definitivo: 20 casos × 3 semillas
│   ├── comparaciones/  ← 8 variantes sobre el mismo lote
│   └── archivo/        ← corridas anteriores, pueden contener fallos corregidos
└── fase_3/
    └── resultados/     ← banco 20 × 3 semillas + 6 fijaciones × 3 semillas
```

Dentro de cada caso:
- `preview.png`: plantas y vista oblicua.
- `front.png`: vista frontal (Fase 2).
- `massing.glb`: maqueta 3D.
- `plan.json`: geometría calculada y decisiones del planificador.
- `summary.json`: comprobaciones de la malla.
- `floors/floorN.png`: planta por piso con ambientes coloreados (Fase 3).

Para ver qué añadió Fase 2, comparar `compact`, `center_recess`, `right_loggia`,
`alternating`, `projecting_rhythm`, `portico`, `vestibule` y `balcony` dentro de
`fase_2/comparaciones/`. Las zonas azules de las plantas son espacios exteriores.

En `fase_3/resultados/` los casos `p3_*` son las seis fijaciones de experimento
(dos ventanas grandes, tres desiguales, ventana pequeña alta, cochera
independiente, piso superior diferente y logia conectada); el resto son los 20
casos del banco. `floors/floorN.png` colorea cada ambiente y marca puertas,
ventanas y accesos.

Los scripts, pruebas y reportes versionados están en
[`house_grammar/experiments/`](../../../house_grammar/experiments/README.md).
Las carpetas de este directorio contienen salidas generadas locales.
