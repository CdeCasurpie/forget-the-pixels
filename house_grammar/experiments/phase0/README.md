# Fase 0 — contrato y banco de aceptación

Estado: implementada a nivel de contrato y experimentos semánticos. **No genera mallas.**

Plan general: [`../../../PLAN_GRAMATICA_ADAPTABLE.md`](../../../PLAN_GRAMATICA_ADAPTABLE.md).

## Entregables

- `src/domain/building_intent.py`: entrada estricta `intent-v1`, validación semántica, serialización sin completar omisiones y orden determinista de operaciones.
- `src/domain/generation_profile.py`: cuatro perfiles iniciales de diseño, independientes del estilo. No son estadísticas medidas de Barranco.
- `cases/tuning/`: 14 casos para diseñar las reglas posteriores.
- `cases/evaluation/`: 6 casos reservados para evaluar los futuros generadores. Se comprueba ahora su sintaxis, pero no se deben usar para ajustar parámetros geométricos.
- `build_cases.py`: receta reproducible del banco.
- `evaluate.py` y `results.json`: evaluación de contrato y dependencias.
- `tests/test_building_intent.py`: pruebas positivas y negativas.
- `CONTRACT.md`: vocabulario, orientación, prioridades y límites.

Los 20 casos son **fixtures sintéticos de diseño**, no reconstrucciones observadas ni un benchmark representativo de todas las casas de Barranco. Esa distinción queda escrita en cada caso. Los renders y la evaluación de fidelidad corresponden a fases posteriores.

## Reproducir desde la raíz del repositorio

```bash
python3 house_grammar/experiments/phase0/build_cases.py
PYTHONPATH=house_grammar/src python3 -m pytest house_grammar/tests/test_building_intent.py -q
PYTHONPATH=house_grammar/src python3 house_grammar/experiments/phase0/evaluate.py
```

## Matriz de cobertura

| ID | Caso | Partición | Qué comprobar después |
|---|---|---|---|
| 01 | Compacta angosta | Ajuste | No convertir ancho reducido en vanos absurdos |
| 02 | Barra ancha | Ajuste | Ritmo proporcional al ancho |
| 03 | Esquina achaflanada | Ajuste | Dos frentes y encuentro |
| 04 | Cerco alto | Ajuste | Patio, puerta, cochera y tapa de teja |
| 05 | Retiro abierto | Ajuste | Ausencia de cerco no implica ausencia de retiro |
| 06 | Patio interior | Ajuste | Vacío dentro de la masa |
| 07 | Mordida izquierda | Ajuste | Sustraer porción localizada |
| 08 | Retiro superior | Ajuste | Huellas distintas por piso |
| 09 | Logia | Ajuste | Espacio retranqueado, no balcón saliente |
| 10 | Ritmo de planos | Ajuste | Pesos relativos y tres planos |
| 11 | Planta baja abierta | Ajuste | Soportes y espacio cubierto |
| 12 | Estilos mezclados | Ajuste | Republicano global, moderno local |
| 13 | Ala posterior en L | Ajuste | Adición conectada |
| 14 | U con patio | Ajuste | Organización y vacío compatibles |
| 15 | Desfase superior | Evaluación | Variación entre pisos |
| 16 | Parcela irregular y mordida | Evaluación | No asumir rectángulo |
| 17 | Ampliación con calamina | Evaluación | Perfil incremental, tanque y materiales |
| 18 | Uso mixto | Evaluación | Acceso sin cochera |
| 19 | Logia en segundo frente | Evaluación | Referencia F2 y distribución desfasada |
| 20 | Composición compleja | Evaluación | Ritmo, retiro, logia, remate y techo mixto |

## Cierre y relevo a Fase 1

La Fase 0 se cierra cuando los 20 documentos validan, las pruebas de rechazo/omisión/estilos/dependencias pasan y el contrato está documentado. Esto demuestra expresividad inicial, **no factibilidad geométrica**.

La Fase 1 debe consumir este contrato y producir primero un plan de masas y vacíos, con vistas de planta y volumen. Implementar organizaciones y operaciones progresivamente; si una operación todavía no se soporta, devolver un diagnóstico explícito. No interpretar una operación pendiente como ausencia ni llamar al materializador antiguo para esconder la limitación.

Próximos pasos concretos:

1. Contrato del plan resuelto: cuerpos por piso, vacíos, superficies y relaciones.
2. Marco de frente estable para ambos sentidos del anillo.
3. Región base, retiro, mordida y patio.
4. Cuerpos conectados y apoyos.
5. Ejecución del banco con reportes de geometría y casos pendientes.
6. Antes de ajustar presets, congelar los seis casos de evaluación.
