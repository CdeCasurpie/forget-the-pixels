# R6 — banco de calibración arquitectónica

El banco `run.py` usa ocho entradas nuevas y una variante de ocupación,
separadas de las 20 entradas históricas y de R1–R5. Los casos angosto y ancho
**ya informaron ajustes** al conteo automático de ventanas: este banco no es
un holdout visual intacto. Se genera con:

```bash
PYTHONPATH=house_grammar/src python3 house_grammar/experiments/r6/run.py \
  --output /tmp/opencode/r6-holdout
```

El directorio de salida debe ser nuevo. Cada caso entrega `front.png`,
`preview.png`, `envelope.glb` y un `manifest.json` con márgenes medidos al
extremo real de cada vano, anchos y coste geométrico. El banco también verifica
puertas de balcones y accesos. Las pruebas numéricas sólo aseguran geometría
y accesos: **no**
certifican semejanza con una fachada real de Barranco. La variante de ocupación
comprueba que no cambia masa, vanos, fachadas, cubiertas ni piezas.

## Revisión visual pendiente

| Caso | En frente y oblicua comprobar |
| --- | --- |
| `narrow_house` | Escala de vanos y cubierta en paño angosto; no mini-ventanas. |
| `wide_casona` | Ejes, cuerpo del frontón, encuentros con techo y cornisa. |
| `modern_corner` | Las dos fachadas de esquina, azotea y pérgola apoyada. |
| `multifamily` | Ejes repetidos y proporción entre niveles. |
| `shop_without_fence` | Acceso comercial directo, escaparate y ausencia de cerco. |
| `shop_with_fence` | Cerco, recorrido, portón y separación física respecto a la tienda. |
| `progressive_house` | Cubierta de calamina y señales de crecimiento sin interior ficticio. |
| `vacant_weathered` | Silueta idéntica a una casa ocupada; desgaste sólo en el acabado. |
| `occupied_weathered` | Pareja de control para medir si cambia la arquitectura al variar sólo ocupación. |

Para cerrar R6 hace falta comparar estos renders contra fotografías
independientes de fachadas de Barranco (incluidas las del usuario si se
proporcionan), consignar observaciones por caso y corregir los desaciertos
arquitectónicos. Después se necesita otro conjunto de casos no usado para
ajustes; el banco actual no constituye aceptación visual.
