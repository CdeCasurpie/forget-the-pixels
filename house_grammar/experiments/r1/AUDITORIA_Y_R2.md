# Auditoría de R1 y diseño de R2

## Dictamen

El puente masas → catálogo funciona; **R1 no puede declararse 100% cerrado**.
Las regresiones previas (150 de theta, 387 de planning, 8 de R1) verifican sus
respectivos contratos, no realismo ni toda la cobertura geométrica prometida.
La revisión visual del usuario rechaza las casas como resultado arquitectónico.

Se conserva el sistema de masas. La **ruta histórica R1** usa
`plan_envelope(..., interiors=True)` y llama a `plan_interiors`, que parte de
`plan_articulation`/`plan_massing`. La ruta exterior nueva es la predeterminada.
Los cuatro casos R1 son compactos:
no ejercitan patios, retiros, logias, esquinas ni cuerpos adosados.

## Hallazgos comprobados en código

| Hallazgo | Evidencia / consecuencia | Acción | Estado |
|---|---|---|---|
| Frontón añadido sin composición | `experiments/r1/cases.py` fuerza familia triangular, altura 1 m y ancho limitado a 2.4 m, centrado en todos los estilos | R2 reserva sector y eje; R4 integra base/cornisa/perfiles; R5 cubierta | Pendiente (R2/R4/R5) |
| Balcón sin acceso requerido | `placements` centra el balcón independientemente de los vanos; el resolver no exige puerta transitable | R2 resuelve balcón y acceso juntos, no agrega una baranda después | Pendiente (R2.4) |
| Fachada subordinada a interiores | El pipeline histórico `plan_envelope(..., interiors=True) → plan_interiors` genera particiones y puertas internas | Ruta exterior por defecto; interiores solo con opción explícita | Primer corte resuelto; aceptación R2.5 pendiente |
| Carpintería aún duplicada | `_joinery` sigue produciendo ventanas/puertas de previews | R3 conecta catálogo; no atribuir a ventanas de catálogo el aspecto de estas imágenes | Pendiente (R3) |
| Evidencia débil de silueta | Runner restaba áreas, omitía agujeros y omitía IDs faltantes | Corregido: diferencia simétrica con patios, igualdad de IDs y fallo efectivo (`experiments/r1/run.py`, `tests/test_r1_footprints.py`) | Resuelto |
| Anclaje de balcón parcialmente antiguo | `resolve_balconies` calculaba el marco desde `mass.footprint`, no desde `WallSurface.frame`; no consultaba `visible_domains` | Anclaje explícito de superficie con offset y validación de exposición | Resuelto |
| Comprobación inferior incompleta al dividir por piso | Colisiones con vanos/ménsulas filtraban por `mass.id`; un piso inferior ahora es otro cuerpo | `_same_plane` reúne las fachadas del mismo plano y los vanos se reproyectan al marco ancla | Resuelto |
| Estilo local aún rechazado | Coronas, balcones, pilastras, entablamentos y vanos conservaban `style conflicts with building` | `domain/styles.resolve_style`: hereda solo si `auto`; excepción local válida sin rechazo por pureza estilística | Resuelto |
| Contrato parcial | `WallSurface` no explicitaba espesor; los anclajes de cerco/cubierta siguen con masa/arista | `thickness_m` y `local_point` declarados; cerco y cubierta conservan su propio tipo de anclaje: no se finge una superficie de fachada para ellos | Parcial (R4/R5) |
| Materiales personalizados | `materialize` validaba `materials`, pero construía `MeshBuilder` con `appearance` por separado | `planning/catalogue._palette`: la apariencia se reconstruye desde el mapping validado | Resuelto |

El manifest histórico `silhouette_drift_m2 = 0` era igualdad de áreas en cuatro
rectángulos. No demuestra por sí solo preservación de contornos arbitrarios.
La corrección actual fortalece las próximas corridas, no reescribe esa evidencia.

## Cierre técnico de R1 antes de aceptar R2

- [x] Superficie estable como anclaje: origen desplazado, normal, altura y región
  visible; rechazar soporte oculto o ambiguo. El catálogo sigue siendo el
  constructor (`tests/test_r1_closure.py`).
- [x] Probar patio, retiro superior, esquina rotada (parcela irregular), borde
  oculto y dos cuerpos contiguos; cotejar polígonos con agujeros y cotas.
- [x] Probar balcón respecto a vanos del piso inferior y estilos locales
  heredados o explícitos. Verificar materiales realmente emitidos.
- [x] Espías sobre ensambladores más semántica de malla: `build_crown` y
  `build_balcony` se cuentan e inspeccionan, no basta el nombre de una pieza.
- [ ] Frente y oblicua por caso. Distinguir resultado de integración de
  aceptación arquitectónica; nunca cerrar por conteo de tests solamente.

**Lo que sigue sin cerrarse es de diseño, no de contrato:** el frontón centrado
sin composición y el balcón sin acceso son R2.4/R4; la separación exterior/BSP
es R2.5; la carpintería duplicada es R3. La aceptación visual del usuario sigue
siendo el criterio de cierre de la fase.

## R2: orden concreto de implementación

### R2.1 — Programa exterior compacto

Extender `domain/building_intent.py` y `domain/architectural_plan.py` con uso por
piso/sector, organización residencial, evolución y conservación independientes.
Estilo global heredable, excepciones locales; cerco independiente. Omitido permite
completar; `false` prohíbe. El LLM no entrega metros por ventana.

**Contrato implementado:** `building.program` y `planning/exterior_program.py`;
`ExteriorProgramPlan` incorpora el mismo massing articulado más asignaciones
por cuerpo/piso/frente, sin habitaciones. `tests/test_exterior_program.py`
fija validación, prioridades locales y ausencia explícita de cerco. Aún falta
que R2.2–R2.5 consuman el programa para producir una fachada exterior.

### R2.2 — Paños y reservas sobre las masas actuales

Entrada: salida de `plan_articulation` y chart corregido. Agrupar bordes
colineales expuestos en paños arquitectónicos conservando discontinuidades
reales, patios y retiros. Reservar acceso, núcleo lateral/central, comercio y
cochera antes de distribuir vanos. No crear tabiques ni habitaciones ocultas.
IDs por cuerpo/frente/sector/piso, con trazabilidad a superficies.

### R2.3 — Ejes y pisos tipo

Reutilizar las ideas de `resolve_bay_layout` en `facade_composition.py` y
`bay_axes`/programas de `facade_program.py`, extrayendo lo necesario de sus
controles theta y rangos antiguos. No llamar esos generadores sin revisar sus
defaults. Definir grupos de pisos compatibles: misma retícula arriba, planta
baja comercial independiente, retiro como excepción, núcleo continuo.

### R2.4 — Relaciones funcionales de fachada

Un balcón transitable referencia un acceso a su cota, con paso libre y respaldo;
una ventana normal con antepecho no cuenta como acceso. Logias conservan vacío,
suelo y límites. Puerta izquierda/centro/derecha responde al programa. Reservar
vanos y volúmenes de marcos con márgenes 1.00/0.85 m desde sus bordes.
R2 reserva dimensiones plausibles según los rangos del plan; R3 termina el
dimensionamiento y materializa con catálogo. No posponer toda la escala a R3.

La coronación referencia un sector compositivo: entrada, eje principal o paño
completo cuando corresponde. Su ancho nace de ese sector; no hay un triángulo
universal ni obligatoriedad de simetría. Conservar las familias de catálogo.

### R2.5 — Envolvente exterior y evaluación

Separar en `planning/envelope.py` la construcción de muros exteriores, huecos y
losas del consumo de habitaciones BSP. Consumir el plan de fachada directamente;
interiores completos solo mediante opción explícita. La misma reserva debe
alimentar corte y carpintería, evitando dos trazados discrepantes.

Banco: casa sencilla sin ornamento, casona, comercio con/sin cerco,
multifamiliar, vivienda sobre comercio, oficinas, edificio progresivo;
variantes angostas/anchas, esquina, retiro, patio, desocupación y mezcla local.
Comparar misma masa antes/después: acceso válido a balcones, ejes/dinteles
coherentes, márgenes, tamaños y proporción de vacíos legibles, sin particiones
ocultas por defecto. Cambiar semilla de detalle no mueve arquitectura.

**Primer corte verificable:** `planning/exterior_envelope.py` es la ruta por
defecto de `plan_envelope()`. Reserva una huella continua de escalera, no una
planta de habitaciones; materializa muros/losas exteriores, ventanas y puertas,
incluida una puerta con `access_for` por cada espacio transitable articulado.
`tests/test_exterior_envelope.py` cubre también los 20 casos de masas sin
particiones. El programa por sectores y los pisos tipo todavía no gobiernan
ejes compartidos; esta ruta **no** sustituye el trabajo R3 de carpintería de
catálogo, ni aprueba visualmente las casas.

**Banco R2 ampliado:** `experiments/r2/run.py` genera 11 frentes y oblicuas
con paños/ejes documentados en `facade.sectors` y pisos repetibles en
`facade.floor_types`. Las coronaciones solicitadas reservan paño y eje en
`facade.coronations`, **sin** superponer un triángulo; el constructor de frontones
se integrará al encuentro real en R4/R5. `site.fence` queda declarado pero no
dibujado: no reemplazar el catálogo de cercos por un constructor temporal.

**Aceptación:** primero debe funcionar una fachada sobria, sin frontón ni props.
Después añadir ornamento vinculado a sus paños. R2 no se aprueba porque se hayan
añadido campos de tipología al JSON o más piezas a los mismos rectángulos.
