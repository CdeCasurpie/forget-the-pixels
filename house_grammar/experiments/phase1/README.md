# Fase 1 — masas y vacíos

Maquetas definitivas: `apps/experimento_paralelizacion/gramatica_adaptable/fase_1/resultados/`.
Corridas previas: `fase_1/archivo/` dentro de ese mismo directorio de experimentos.

Revisión de cierre: 91 pruebas del contrato y planificador pasan. El banco
sintético de 20 casos sobre semillas 7, 17 y 81 genera 60 planes sin conflicto;
todos sus componentes tienen volumen positivo, winding consistente y son
watertight. Esto no demuestra fidelidad a edificios reales ni cálculo estructural.

Implementado: organizaciones, huellas por piso, retiros, mordidas, patios reales,
adiciones, avances, voladizos, planta abierta, chaflanes, apoyos conceptuales,
superficies orientadas y balance de ocupación/libre/cubierto. Casos incompatibles
producen PlanningError localizado; operaciones posteriores quedan pendientes.

```bash
PYTHONPATH=house_grammar/src python3 -m pytest house_grammar/tests/test_building_intent.py house_grammar/tests/test_intent_massing.py -q
PYTHONPATH=house_grammar/src python3 house_grammar/experiments/phase1/run.py --output /tmp/opencode/phase1-review --seeds 7 17 81
```

El directorio de salida debe ser nuevo. Cada caso contiene plan.json, summary.json,
massing.glb y preview.png. Las coordenadas son salida del planificador; parcel y
levels_m son contexto externo (sintético en estos fixtures), no autoría del LLM.

Revisión visual realizada sobre patios U, ala L, planta abierta, lote irregular y
combinación compleja. La vista Matplotlib puede mostrar artefactos de ordenación
de triángulos: GLB y plantas son referencias geométricas adicionales.

Límites: priors métricos iniciales, soportes conceptuales y sólidos por componente,
no unión booleana del edificio. El banco de evaluación ya se ejecutó durante el
desarrollo; es regresión sintética, no evaluación ciega. Fase 2 debe materializar
espacios exteriores y sus encuentros sin confundirlos con mordidas de piso entero.
