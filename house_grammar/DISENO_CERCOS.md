# Diseño: cercos generativos por estilo + altura

Rama `cercos_mejora`. Objetivo: que el theta declare solo
`estilo + altura + presencia de puerta/cochera`, y la gramática
resuelva automáticamente los modelos compatibles.

## Vocabulario

5 estilos implementados: `republicano`, `barroco`, `moderno`, `clasico`,
`madera`. Cada uno existe en 2 variantes (`height_mode`):

- `high`: un piso (~2.4–3 m).
- `low`: piernas de una persona (~1.0–1.2 m).

`height_m` fija la altura métrica; el modo no la infiere de los pisos.

## Catálogo generativo (30 modelos + vacío)

| Pieza | Cuenta |
|---|---|
| Cercos: 5 estilos × 2 alturas | 10 |
| Puerta peatonal: 5 estilos × 2 alturas (+ `vacia` = sin puerta) | 10 + vacío |
| Cochera: 5 estilos × 2 alturas | 10 |

## Regla de compatibilidad

El estilo manda: elegido el estilo del cerco, la puerta y la
cochera se toman del mismo estilo automáticamente. El theta no
combina estilos a mano. Por eso puerta y cochera se modelan
duplicadas (alta y baja): cada altura del cerco necesita su
versión proporcional de vano.

## Implementación

`src/modeling/fences.py` construye los cinco estilos mediante piezas compartidas:
postes, coronaciones biseladas, barras, curvas muestreadas, anillos, lanzas,
lamas, tablas apuntadas, bastidores, bisagras, manijas y refuerzos. La cochera
usa dos hojas y la puerta una; los motivos se repiten sin estirarse al ancho.
Las rejas no tienen un panel opaco detrás. El clásico sí tiene hojas sólidas
paneladas. El moderno puede incluir jardineras huecas con tierra y vegetación.

Integrado en `FenceRun`, `ResolvedBoundary`, `BoundarySpec` y `draw_fence`.
Los tipos anteriores siguen siendo válidos y conservan su ruta de generación.
La selección nueva se hace en `site.runs`, con `site.fence: "none"`.

Ejemplo de tramo (las distancias se miden desde el inicio del tramo para los accesos):

```json
{
  "edge": 1, "start_m": 0, "end_m": 15.03,
  "kind": "republicano", "height_mode": "low", "height_m": 1.1,
  "wall_material": "plaster",
  "gate_u": 4.86, "gate_width": 1.1, "gate_mode": "auto",
  "garage_u": 11.48, "garage_width": 2.9, "garage_mode": "auto",
  "openness": 0.3, "planters": false
}
```

- `auto`: hoja del mismo estilo que el cerco.
- `open`: abertura libre, sin hoja; conserva la posición y ancho del acceso.
- Ausencia de acceso: `gate_u: null, gate_width: 0` (igual para cochera).
- `wall_material`: `plaster`, `brick`, `stone` o `concrete`, aplicado a base y pilares.
  Para elegir color/plantilla física, usar `theta.materials` con ese slot. El
  catálogo usa `plaster`, que hereda el color de la casa; no fuerza ladrillo.
- `metal` y `wood` también se pueden configurar en `theta.materials`.
- `openness` (.1–.7) controla la fracción de separación de lamas modernas y
  tablas de madera. En rejas, la transparencia depende de sus barras y motivos;
  en muros clásicos este parámetro no cambia la opacidad.
- `planters: true`: jardineras modernas hacia el interior del lote, fuera de los accesos.

## Verificación y catálogo

`python3 steps/step23_fresh_theta/catalogo_cercos.py`, desde el proyecto procedural,
genera diez ejemplos completos sobre la casa salmón: request, GLB, validación y
cuatro cámaras por ejemplo. Lámina: `steps/step23_fresh_theta/catalogo_cercos/catalogo.png`.
Pruebas focalizadas de cercos, base simplificada y theta: 56 aprobadas.
Las diez mallas pasan la prueba de envolvente. Esto verifica implementación,
no que una familia genérica reproduzca exactamente una reja histórica particular.

La primera versión barroca incluye volutas repetidas y lanzas; todavía no añade
coronaciones arqueadas ni rosetas escultóricas. Esos motivos pueden incorporarse
al generador sin cambiar la descripción de accesos del theta.
