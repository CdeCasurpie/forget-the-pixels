# Plan de rediseño: gramática arquitectónica adaptable de Barranco

**Estado:** R0 implementada; R1 con puente funcional y cierre técnico cerrado (anclaje de superficie, vecindad entre pisos, estilo local, paleta y cobertura geométrica); la aceptación arquitectónica sigue abierta y R2 en diseño. Las antiguas Fases 0–5 son antecedentes técnicos, no aceptación arquitectónica del resultado. El programa vigente es R0–R7, abajo.
**Objetivo:** generar casas plausibles, detalladas y habitadas de Barranco a partir de una descripción exterior compacta, completando algorítmicamente lo que no se ve.
**Alcance:** nuevo contrato, planificación espacial, generación procedural y materialización. No se exige compatibilidad con el sistema anterior.

> Este documento conserva las decisiones de la conversación y organiza su implementación por fases. Las capacidades propuestas y los criterios de aceptación no son resultados ya obtenidos. Para localizar la implementación vigente, consultar `PIPELINE_GRAMATICA.md` y contrastar con el código.

## Replanteamiento vigente — conservar catálogo, mejorar composición exterior

Esta sección sustituye las prioridades y fases del plan histórico que sigue debajo. No se implementa código con esta revisión. La petición es evolucionar el `src` existente: nuevas masas, ubicación automática coherente de vanos y elementos cotidianos, conservando la riqueza geométrica ya desarrollada.

### Contrato de alcance

- **Uso obligatorio de todos los catálogos existentes:** balcones, cercos, entradas, frontones, pilastras, puertas, remates, techos y ventanas. Conservar diseños, perfiles, formas, materiales y capacidades; no significa añadir todas las piezas a cada inmueble.
- Se permite modificar contratos, resolvers, ensambladores y pipeline dentro de `src`. No se exige compatibilidad con theta ni JSON antiguos. No actualizar ni regenerar `steps/` para perseguir compatibilidad: sus muestras son referencias visuales históricas, no una API que deba seguir ejecutándose.
- No crear otro motor de piezas paralelo. La planificación produce superficies y anclajes; los constructores existentes materializan las piezas. Migrar y retirar los emisores duplicados solo cuando su sustitución esté verificada.
- Mantener masas, vacíos, articulación, espesores, vanos reales, losas y conexiones exteriores útiles. El interior pasa a ser una hipótesis ligera de zonas perimetrales y núcleo vertical: **sin particiones, puertas internas ni mobiliario oculto en la malla por defecto**.
- La fachada gobierna la composición. Las zonas funcionales ayudan a elegir ventana y antepecho, pero no obligan a subdividir toda la casa para colocar vanos.
- Variación por edificio/cuerpo/piso y por función. La semilla de detalles cotidianos nunca cambia masas, ejes o dimensiones de vanos.

### Correcciones al diagnóstico anterior

- `small_high` significa ventana pequeña situada alta; no exige una proporción vertical. No convertir respiraderos horizontales en ventanas altas y estrechas indiscriminadamente.
- En `_completion`, la proporción horizontal se selecciona con el ancho final (`line.length >= 1.3`), no con la longitud original del borde. Una ventana automática de 0.85 m no se convierte por esa regla en 0.85 × 0.47 m. El problema de tamaños conservadores sigue existiendo.
- La alineación puede ocurrir con tramos y conteos iguales, pero no existe un sistema explícito de ejes compartidos que la garantice entre pisos distintos.
- El renderer ortográfico filtra caras con una dirección, pero no fija la cámara correspondiente (`view_init` solo se llama si no es ortográfico). Esto es un defecto concreto adicional al orden de profundidad limitado de matplotlib. Una malla watertight no demuestra por sí sola que el GLB sea visualmente correcto.
- No copiar automáticamente la planta baja comercial en las viviendas superiores. Repetir pisos tipo compatibles y permitir excepciones.

### Reglas dimensionales y compositivas

**Márgenes solicitados:** puerta peatonal a ≥1.00 m y ventana a ≥0.85 m de los extremos laterales del frente/paño anfitrión, medidos desde el borde del vano, no desde su centro. Reservar además el volumen del marco, portal o moldura de catálogo. No convertir cada fragmento de triangulación en un nuevo paño ni aplicar ese margen como separación entre cada par de ventanas.

La puerta puede estar a izquierda, centro o derecha: respetar la intención dentro del intervalo admisible; no imponer centro universal. El acceso debe coordinarse con escalera, comercio, cochera y cerco. Cuando no cabe, intentar otro paño o ajustar dimensiones libres dentro de su rango; si la cantidad o posición explícita lo impide, informar el conflicto. Nunca rebajar silenciosamente el margen ni producir ventanas minúsculas. Portones vehiculares, vitrinas continuas y vanos de esquina requieren reglas específicas, no heredar sin análisis el margen peatonal.

**Referencia peruana consultada:** RNE A.020, RM 188-2021-VIVIENDA, artículos 9 y 12, disponible en el [índice oficial del RNE](https://www.gob.pe/institucion/vivienda/informes-publicaciones/2309793-reglamento-nacional-de-edificaciones-rne) y en el [texto oficial](https://cdn.www.gob.pe/uploads/document/file/2366561/36%20A.020%20VIVIENDA%20-%20RM%20N%C2%BA%20188-2021-VIVIENDA.pdf).

- Altura mínima de vano de puerta residencial: 2.10 m; ancho mínimo de acceso a vivienda: 0.90 m; acceso principal multifamiliar: 1.20 m.
- No establece una altura universal de ventana: área de vanos ≥10% del ambiente y abertura al exterior ≥5%; alféizar mínimo 1.00 m, con las excepciones de vidrio fijo/protección descritas en el artículo 12.5.
- Estas referencias residenciales no se extrapolan como normativa comercial ni certifican un proyecto generado sin planta completa. Las áreas funcionales aproximadas ayudan a dimensionar, pero no demuestran cumplimiento normativo.
- Los márgenes 1.00/0.85 m son reglas compositivas solicitadas por el usuario, no mínimos atribuidos al RNE.

**Rangos iniciales propuestos para calibración, no medidas oficiales ni estadísticas de Barranco:** ventana residencial principal: ancho 1.20–2.40 m, alto 1.20–1.60 m; sala horizontal amplia: ancho 1.80–3.00 m cuando el paño lo permita; ventana vertical de casona: ancho 1.00–1.50 m y alto 1.80–2.40 m si el piso y el catálogo lo admiten. Los respiraderos siguen una familia pequeña y alta en posición. Dimensionar ancho y alto conjuntamente según tipo, proporción, antepecho, dintel y superficie disponible; no estirar todo hasta el dintel ni sustituir la proporción histórica por un estándar moderno.

Puertas y ventanas tienen profundidades independientes. El acceso puede tener mayor retranqueo y portal; resolver el espesor/vestíbulo necesario en vez de colocar la hoja detrás de un muro inexistente. Comparar sus sombras y derrames en vista oblicua.

### R0 — Inventario de capacidades y referencia visual fiable

**Trabajo:** registrar cada catálogo, su constructor, controles, anclaje esperado y casos representativos. Revisar `opening_catalog.py`, `window_assembly.py`, `door_assembly.py`, `fences.py`, `entrances.py`, `balcony_*`, `vertical_member_*`, `crown_*`, `trim_*`, `entablature_resolver.py`, `roof_*` y materiales. Separar pruebas de capacidad de las que exigen un JSON histórico. Corregir cámara/culling y usar render con profundidad real para la validación; preservar vistas frontal y oblicua comparables.

**Salida:** matriz de conservación de los nueve catálogos; referencias históricas consultables y casos mínimos nuevos fuera de `steps/`; imágenes sin paredes transparentadas, triángulos espurios ni cámara frontal incorrecta. No aprobar integración basándose en los PNG actuales.

### R1 — Integración de nuevas masas con el materializador existente

**Trabajo:** reutilizar `planning/massing.py` y `articulation.py`; adaptar los contratos de superficies y ensamblaje existentes a sus resultados. Superficies con ID estable, sistema local, normal, espesor, piso/cuerpo, exposición y regiones utilizables. Anclajes explícitos para fachada, cerco, cubierta y coronación. Modificar `modeling/assembly.py`, `theta.py`/pipeline y contratos según corresponda; no forzar el nuevo plan a serializarse como theta viejo.

**Salida:** una ruta de generación que muestra nuevas masas con piezas reales de catálogo, incluidos un frontón y un balcón; mismas huellas/siluetas que las masas aprobadas, sin constructores alternativos de piezas. Los frontones conservan volumen y relación con techo; no se reducen a etiquetas o material.

**Hecho (R1):** contrato neutral `domain/surfaces.py` (`WallSurface`, `SurfaceChart`) y refactor nativo de `crown_resolver.py` y `balcony_resolver.py`, que consumen `(controls, estilo, chart, envelope, materials)` en vez de un candidato theta; `theta.py` construye el chart en la frontera y queda como adaptador. `planning/chart.py` deriva el chart de las masas nuevas (un cuerpo por piso, con su silueta, espesor `EXTERIOR` y regiones visibles) y los vanos ya reservados; `planning/catalogue.py` resuelve y materializa con los ensambladores del catálogo.

**Cierre técnico (R1):** el balcón se ancla al plano construido (`surface.frame()`, con `plane_offset_m`), valida su región visible y consulta las fachadas del mismo plano —incluido el piso inferior, que ya es otro cuerpo— reproyectando los vanos al marco ancla. `domain/styles.py` hereda el estilo global y acepta una excepción local sin rechazarla. `planning/catalogue._palette` pinta la misma paleta que los resolvers validaron. Ruta y pruebas: `house_grammar/experiments/r1/`, `tests/test_intent_catalogue.py`, `tests/test_r1_footprints.py` y `tests/test_r1_closure.py` (patio, retiro, parcela irregular, borde compartido, dos cuerpos). Los resolvers de pilastras, entablamentos, entradas y cubiertas siguen sobre theta y migran en R4/R5; los vanos de catálogo (`_joinery` duplicada) se sustituyen en R3. La aceptación arquitectónica sigue abierta: es lo que R2 ataca.

### R2 — Composición exterior y tipos de edificio sin planta interior completa

**Diseño de ejecución y auditoría previa:** véase `house_grammar/experiments/r1/AUDITORIA_Y_R2.md`. Conservar `plan_massing`/`plan_articulation`; sustituir la dependencia de `plan_interiors` como origen obligatorio de vanos. La mejora debe ser visible incluso en una masa rectangular sencilla.

**R2.1 implementada (contrato, aún no fachada visible):** `building.program`
declara uso, organización residencial, evolución, conservación y ocupación
independientes, con excepciones por cuerpo/piso/frente. `planning/exterior_program.py`
lo completa sobre `plan_articulation` sin crear tabiques ni tocar la masa.
`site.fence=False` permanece una prohibición explícita. R2.2–R2.5 deberán
consumir estas asignaciones para reservar paños y construir la envolvente;
agregar vocabulario por sí solo no satisface la salida visual de R2.

**Primer corte exterior R2.2/R2.4/R2.5 (sin aprobar R2):** `plan_envelope()`
ejecuta por defecto `planning/exterior_envelope.py` sobre las masas articuladas:
reserva solo la huella continua de la escalera, construye muros/losas exteriores,
abre ventanas y un acceso peatonal, sin habitaciones, tabiques ni puertas internas.
Cada balcón/logia/espacio transitable de `building.operations` reserva **una puerta
de fachada real** en su desembarco (`access_for`); una ventana no cuenta. Los
tests recorren 20 casos sintéticos sin BSP y comprueban el acceso. La ruta de
interiores previa exige ahora `plan_envelope(request, interiors=True)` y sigue
siendo referencia histórica. `surface_chart(..., enclosed=True)` ancla vanos en
el muro detrás de balcones, sin confundirlo con la silueta de la losa. Faltan
retícula arquitectónica y pisos tipo, criterios completos para comercio, y
despacho de carpintería al catálogo en R3; el preview aún no acredita realismo.

**Avance R2.3/R2.4:** el plan exterior publica `facade.sectors` (uso local,
superficies expuestas, ejes, accesos) y `facade.floor_types` (retícula compartida
por pisos geométricamente compatibles). Uso comercial reserva una vitrina mayor;
oficinas y multifamiliares repiten tres ejes en paños suficientemente anchos.
Una solicitud de coronación reserva `facade.coronations` con su **paño anfitrión**
y ancho disponible, sin generar un triángulo universal: su volumen y encuentro
con cubierta siguen siendo trabajo de R4/R5. Banco R2: 11 escenarios exportados
con frente/oblicua y 20 casos de masas comprobados sin BSP. El cerco se conserva
como intención, **aún no se materializa** hasta integrar su catálogo en R4.

**Trabajo:** sustituir la dependencia obligatoria de la partición BSP por paños, ejes, zonas funcionales aproximadas y reserva de núcleo. Reutilizar ideas/código de `facade_composition.py`, `facade_program.py` y las reservas útiles de `interiors.py`. No materializar muros interiores por defecto.

Separar atributos: uso (residencial/comercial/oficinas-mixto), organización residencial (unifamiliar/multifamiliar), uso por piso/sector, evolución (unitaria/progresiva), conservación/ocupación y estilo. Abandonada es un estado, no una tipología equivalente a comercio. Permitir edificios sencillos, irregulares o sin estilo dominante. Cerco es independiente del uso.

Resolver grupos de pisos tipo y ejes compartidos: escalera lateral o central, repetición superior, planta baja diferenciada, retiros y ampliaciones como excepciones. Conservar núcleo conceptual cuando aporte coherencia; sin obligar a resolver baños y pasillos completos.

**Salida:** vivienda individual, comercio con/sin cerco, multifamiliar, multifamiliar sobre comercio, oficinas, edificio progresivo y variantes desocupadas/deterioradas distinguibles por composición. Misma fachada tipo se repite entre pisos compatibles; cambiar semilla de detalles no mueve vanos.

### R3 — Vanos automáticos dimensionados y construidos con catálogo

**Trabajo:** resolver conjuntamente conteo, ejes, ancho, alto, antepecho, dintel, padding, separación entre vanos y profundidad. Aplicar reglas anteriores, respetar solicitudes explícitas y evaluar ocupación del paño. Reservar huella completa de portales, pilastras y molduras. Adaptar `Opening` y el despacho existente a la escena resuelta y a estilos locales; conservar formas curvas, rejas, sobreluces, hojas y perfiles. Retirar `_joinery` duplicado después de verificar equivalencia de capacidades requeridas.

**Salida:** ventanas principales claramente mayores que respiraderos; puertas alejadas del borde y con profundidad propia; conteos y proporciones correctos en lotes estrechos/anchos. Verificar ventanas y puertas de cada familia, huecos de igual contorno que su pieza y repetición de dinteles/ejes entre pisos. Una prueba confirma invocación del constructor de catálogo, no solo parecido visual.

### R4 — Cercos, accesos y composición ornamental completa

**Trabajo:** conectar planificación de sitio con `boundaries.py`, `fences.py`, `entrances.py` y catálogos asociados. Mantener forma independiente del estilo, ausencia explícita, posición de accesos y rutas exteriores. Resolver acceso compartido por cochera cuando se solicite, sin exigir siempre otra puerta peatonal. Retirar `_fence_parts` duplicado al integrar el catálogo.

Integrar todos los balcones, pilastras, frontones, cornisas, zócalos y remates conservados. Selección explícita o autocompletado compatible con lenguaje local; no ornamentar todas las casas. Remates sobre cerco usan su propio anclaje y cubierta apoyada.

**Corrección visual solicitada — frontones:** no colocar un triángulo de ancho fijo en el centro de cualquier fachada. R2 debe reservar su paño anfitrión, eje, ancho y relación con acceso/balcón/cornisa; R4 resolverá la continuidad de base, molduras, espesor y retornos con esa fachada, y R5 el encuentro con cubierta. Ajustar proporciones al sector coronado, sin estirar arbitrariamente perfiles del catálogo ni imponer frontón a casas que no lo requieren. Verificar apoyo y continuidad en frente y oblicua, incluyendo fachadas asimétricas, retiros y distintos anchos.

**Salida:** matriz de los nueve catálogos sin capacidades perdidas por la migración; frente republicano, moderno y mixto sobre las nuevas masas; accesos conectados y piezas apoyadas, sin invasiones. Cubiertas detalladas se completan en R5, con su constructor ya conectado.

### R5 — Cubiertas y vida cotidiana exterior automáticas

**Trabajo:** reutilizar techos, tejas/calamina y props existentes. Planificar zonas de azotea, circulación conceptual, acceso de escalera, caseta, tanque, tendido, antenas, equipos y macetas según uso y superficie. Resolver pendientes, apoyos, aleros y encuentros con frontones. Extender la colocación automática a fachadas, balcones, entradas y retiros.

El “noise” es detalle contextual: reglas de soporte, espacio, orientación, agrupación y densidad; no dispersión uniforme. Cortinas/persianas y fondos someros detrás de ventanas cuando sean visibles, sin una vivienda interna completa. Reutilizar capacidades existentes y ampliar solo huecos funcionales identificados en R0.

**Salida:** azoteas y exteriores habitados pero no saturados; cero props flotantes/bloqueando accesos; variantes de ocupación mantienen arquitectura idéntica. Ausencias explícitas respetadas.

### R6 — Calibración Barranco y aceptación arquitectónica

**Trabajo:** comparar con referencias de fachadas reales, incluidas las aportadas por el usuario cuando estén disponibles como archivos de referencia. Banco nuevo separado de los casos usados para ajustar. Cubrir lotes angostos/anchos, esquina, casona, vivienda sencilla, multifamiliar repetitivo, comercio y construcción progresiva.

**Medir:** padding real al borde del vano, dimensiones, proporción vano/paño, alineación entre pisos, profundidad puerta/ventana, fidelidad al catálogo, silueta, colocación de ornamentos y densidad de detalle. Revisar frente y oblicua del GLB con render fiable. Revisar geometría y coste por componente sin exigir que piezas decorativas legítimamente abiertas sean sólidos cerrados.

**Salida:** aceptación visual además de tests; casos inviables producen diagnósticos y no ventanas comprimidas. El éxito de 413 pruebas y 93 corridas anteriores conserva valor como regresión geométrica, no como evidencia de realismo arquitectónico.

### R7 — Entrada compacta, ruta única y limpieza

**Trabajo:** conectar descripción humana/LLM con tipología, masas, composición y selección cualitativa de catálogo. LLM sin metros por ventana; compilador resuelve dimensiones. Consolidar una ruta pública de `src`; retirar emisores duplicados y dependencias del plan interior completo después de migrar consumidores. Actualizar documentación vigente y pruebas del contrato nuevo. JSON/theta históricos pueden dejar de funcionar; `steps/` permanece como historia visual.

**Salida:** generación extremo a extremo determinista, conservando todas las capacidades inventariadas y con presupuesto de geometría exterior medido. No mantener dos motores para producir la misma pieza.

### Secuencia y seguimiento

R0 → R1 → R2 → R3 → R4 → R5 → R6 → R7. Revisar visualmente desde R1; R6 amplía la evaluación, no posterga todas las revisiones hasta el final.

- [x] R0: inventario y render fiable. Véase `house_grammar/experiments/r0/README.md`.
- [ ] R1: puente implementado y cierre técnico hecho (anclaje de superficie, pisos entre cuerpos, estilo local, paleta y cobertura geométrica). La aceptación arquitectónica —frente y oblicua— pasa a R2/R6. Véase `house_grammar/experiments/r1/AUDITORIA_Y_R2.md`. Las cuatro imágenes no constituyen aceptación arquitectónica.
- [ ] R2: R2.1–R2.5 tienen una ruta exterior funcional (paños, ejes/pisos tipo, puerta vinculada al balcón y envolvente sin BSP). Pendiente la aceptación visual del usuario y completar composición/zonas de acceso en casos complejos; cerco y piezas finales pertenecen a R3–R5.
- [ ] R3: vanos de catálogo con tamaño, profundidad y padding.
- [ ] R4: cercos, entradas y ornamentación conservada.
- [ ] R5: cubiertas y detalle cotidiano contextual.
- [ ] R6: aceptación arquitectónica sobre referencias.
- [ ] R7: flujo compacto, ruta única y limpieza.

Las secciones siguientes documentan el plan anterior y sus resultados. Sus instrucciones de interiores completos y su declaración de fases cerradas no prevalecen sobre este replanteamiento.

## 1. Decisiones fundamentales

1. **La evidencia es opcional.** El LLM no necesita justificar cada elemento con fotografías, confianza o procedencia.
2. **El autocompletado estará activo por defecto.** No omitir detalles solo porque no se ven o no hay información suficiente.
3. **El objetivo es plausibilidad arquitectónica local**, guiada por lo visible; no una reproducción exclusivamente limitada a elementos demostrables.
4. **El LLM describe; el algoritmo dimensiona, organiza y completa.** No pedir coordenadas y medidas exactas de cada ventana, muro o accesorio.
5. **Se permiten estilos mezclados.** El estilo global es una preferencia heredable, no una prohibición de excepciones locales.
6. **No es obligatorio mantener compatibilidad.** Se pueden sustituir contratos y rutas antiguas. Reutilizar constructores geométricos no obliga a conservar el theta anterior.
7. **Prioridad: masas, vacíos, profundidades y organización espacial.** La ornamentación no corrige una mala composición.
8. **Interiores plausibles y contenido cotidiano forman parte del generador:** cortinas, macetas, muebles sencillos y estados de apertura.
9. **Las azoteas se autocompletan aunque no se vean**, según uso, cubierta, construcción y espacio disponible.
10. **La variación será coherente y reproducible.** Cambiar cortinas o materiales no debe reorganizar la casa.

### Fuentes de decisiones

| Fuente | Ejemplos |
|---|---|
| Contexto humano | Parcela, frentes, pisos, alturas y restricciones fijadas |
| Descripción exterior | Dos ventanas largas, cerco alto, logia, cuerpo superior retirado |
| Generación procedural | Dimensiones finales, distribución interior, carpintería, mobiliario y equipamiento |

### Semántica mínima de entrada

- **Campo omitido:** el generador puede completarlo.
- **Ausencia explícita:** respetarla; por ejemplo, `cochera: false`.
- **Presencia explícita:** generar el elemento; por ejemplo, `cochera: true`.
- **Descripción específica:** condiciona posición, cantidad, proporción o tipo.
- Los registros internos de decisiones pueden ayudar a depurar, pero **no serán evidencia obligatoria ni una carga para el LLM**.
- Si una combinación resulta imposible, ajustar primero los parámetros libres. No eliminar silenciosamente elementos solicitados para pasar un validador.

## 2. Diagnóstico de la implementación revisada

La revisión cubrió la ruta central, contratos, documentación y módulos pertinentes; no equivale a una auditoría exhaustiva de cada archivo histórico o dataset.

| Área | Base existente | Trabajo pendiente |
|---|---|---|
| Masas | Regiones, componentes, recortes, apoyos, cuerpos abiertos | Interpretar relaciones y operaciones cualitativas |
| Fachadas | Crujías, grupos, programas por piso, ejes y correcciones | Coordinación por piso y con la planta interior |
| Profundidad | Zonas desplazadas, retornos y secciones | Operaciones arquitectónicas completas: logias, pórticos y ritmos |
| Planta interior | Apoyos y distribución de aberturas | Ambientes, circulación, núcleo vertical y continuidad entre pisos |
| Ventanas | Marcos, rejas, vidrio, perfiles, alféizares y derrames | Materiales independientes, estados de uso y relación con ambientes |
| Cercos | Muros, rejas, postes y portones | Separar forma, estilo, protección y remate; conectar accesos |
| Cubiertas | Tejas, calamina, listones, faldones y marquesinas | Organización funcional y colocación condicionada |
| Props | Catálogo de azotea y dispersión sin solapes | Zonas funcionales, apoyos, acceso y completado en la ruta nueva |
| Aleatoriedad | Semillas deterministas por identificadores | Identidad estable y variación jerárquica en todo el edificio |

### Hallazgos concretos

- `modeling/assembly.py` resuelve regiones, recortes, apoyos y zonas libres; no interpreta por sí solo una descripción como «centro hundido y extremos adelantados».
- `modeling/base_massing.py` contiene recetas de retiros y mordidas por piso, todavía expresadas mediante dimensiones.
- `modeling/facade_composition.py` ya distribuye grupos y programas de vanos. No hay que asumir que todo el trazado parte de cero.
- No se identificó un generador de plantas habitables en la ruta vigente: `layout.py` y `programs.py` distribuyen principalmente fachadas/aberturas; una retícula de apoyos no es una planta funcional.
- Un balcón retranqueado necesita vacío, suelo, laterales, cubierta cuando corresponda, baranda y acceso. Hoy esas funciones están repartidas entre sistemas.
- Las ventanas ya tienen `recess_m` positivo y validación. Falta coordinarlo con muro, carpintería y ambiente, no solamente añadir un valor mínimo.
- `modeling/theta.py` asigna cobertura aleatoria de cortina, pero el `build_window()` revisado en `window_assembly.py` no la materializa.
- Hay rechazos de estilos locales diferentes del global en `opening_catalog.py`, `balcony_resolver.py`, `vertical_member_resolver.py`, `crown_resolver.py` y `entablature_resolver.py`.
- `boundaries.py` puede proponer puerta y cochera cuando caben. La ruta nueva debe respetar presencia/ausencia y conectarlas con espacios útiles.
- `roofscape.scatter_props()` ofrece una base geométrica de colocación, pero necesita relaciones funcionales, orientación y apoyos.
- `randomness.py` permite derivar semillas estables; los IDs no deben depender únicamente de posiciones en listas.
- `apps/theta_author/compiler.py` es un adaptador mínimo, no el planificador arquitectónico propuesto.
- En el experimento, `common.py` añade candidato y error de reparación a `prompt` después de construir el bloque `content`. Ese contenido añadido no se incorpora al bloque ya creado: corregir antes de usar reparaciones como medida de calidad.

## 3. Lenguaje de masas sin dimensiones exactas

La descripción combinará **organización base + operaciones + relaciones + magnitudes relativas**. Evitar un catálogo cerrado de casas completas: las operaciones deben poder componerse.

### 3.1. Organizaciones base

| Organización | Significado |
|---|---|
| Compacta | Cuerpo principal continuo |
| Barra | Cuerpo alargado |
| En L | Dos alas que delimitan un espacio |
| En U | Tres alas alrededor de un patio |
| Con patio | Masa alrededor de uno o varios vacíos |
| Escalonada | Huellas que retroceden entre pisos |
| Podio y cuerpo superior | Base amplia y volumen alto más reducido |
| Cuerpos adosados | Varias piezas conectadas |
| Esquina articulada | Dos frentes con tratamiento del encuentro |
| Crecimiento por etapas | Cuerpos o niveles con diferencias constructivas |

Son puntos de partida, no moldes rígidos. La cobertura exacta de cada fase se definirá en su banco de aceptación.

### 3.2. Operaciones

| Operación | Ejemplo | Efecto |
|---|---|---|
| Retirar | «Piso 3 retirado al frente» | Reduce ocupación superior |
| Morder | «Mordida en esquina izquierda» | Sustrae una porción localizada |
| Vaciar | «Patio central» | Crea un vacío interior |
| Adosar | «Ala baja al fondo» | Añade un cuerpo conectado |
| Avanzar | «Cuerpo derecho adelantado» | Cambia profundidad entre cuerpos |
| Volar | «Segundo piso sobresale» | Proyección con soporte compatible |
| Abrir | «Planta baja abierta bajo el cuerpo» | Pórtico o espacio cubierto |
| Retranquear sector | «Centro hundido» | Desplaza parte de la fachada |
| Alternar | «Entrantes y salientes» | Ritmo de planos |
| Desfasar entre pisos | «El entrante cambia de lado arriba» | Alternancia vertical |
| Achaflanar | «Esquina cortada» | Encuentro oblicuo |
| Redondear | «Esquina curva» | Superficie curva; ampliación posterior si es necesario |
| Coronar | «Frontón sobre el centro» | Remate de una parte |

### 3.3. Tres escalas de profundidad

1. **Volumen:** retiros, alas, patios, mordidas, cuerpos salientes. Afecta huella y ocupación.
2. **Espacio/plano de fachada:** logia, vestíbulo, pórtico, paño retranqueado. Puede crear un espacio habitable o exterior cubierto.
3. **Detalle constructivo:** derrames, marcos, zócalos, cornisas, juntas y textura. No altera la organización general.

Una casa compacta puede ser convincente mediante las escalas 2 y 3. No imponer grandes salientes para evitar un «cubo».

### 3.4. Desambiguar zigzag

- En planta: avance y retroceso horizontal de fachada.
- Entre pisos: entrantes o balcones cambian de posición.
- En silueta: alturas escalonadas.
- En detalle: patrón quebrado de una pieza.

El LLM elige la relación; el algoritmo calcula la geometría.

### 3.5. Magnitudes y referencias

- Profundidad: leve, media, profunda.
- Ancho: estrecho, medio, ancho, todo.
- Posición: izquierda, centro, derecha, esquina.
- Alcance: un piso, varios pisos, todos.
- Relación: alineado, desfasado, simétrico, independiente.
- Pesos relativos: por ejemplo, sectores `[1, 2, 1]`.
- IDs semánticos: frente, cuerpo, sector y grupo de vanos; no índices de aristas resueltas para el LLM.

Los términos se dimensionan según su tipo y contexto. «Profundo» no significa lo mismo para un derrame, una logia y un retiro. Admitir proporciones estimadas cuando ayuden; evitar precisión métrica falsa.

### 3.6. Ejemplo de intención volumétrica

**Borrador ilustrativo: no es un esquema implementado.**

```json
{
  "organizacion": "compacta",
  "espacio_frontal": {"profundidad": "media", "uso": "patio"},
  "cerco": {
    "tipo": "macizo", "altura": "alta",
    "puerta": "izquierda", "cochera": "derecha"
  },
  "cuerpos": [
    {"id": "principal", "pisos": "todos", "posicion": "detras_del_patio"}
  ],
  "operaciones": [
    {
      "tipo": "retranquear", "sobre": "principal", "frente": "F1",
      "pisos": [3], "profundidad": "media"
    },
    {
      "tipo": "logia", "sobre": "principal", "frente": "F1",
      "pisos": [2], "sector": "derecha", "ancho": "medio",
      "profundidad": "leve"
    },
    {
      "tipo": "ritmo_de_planos", "sobre": "principal", "frente": "F1",
      "pisos": [1, 2], "sectores": [1, 2, 1],
      "planos": ["base", "retranqueado", "base"]
    }
  ]
}
```

El algoritmo deriva huellas, dimensiones, cerramiento, superficies y acceso a la logia. Las operaciones tendrán precedencia explícita por tipo y dependencia, no por orden accidental del JSON.

## 4. Plantas interiores y fachada: resolución conjunta

### Planta funcional inicial

Representar por piso:

- Zonas sociales, privadas y de servicio.
- Circulación y núcleo vertical.
- Patios, terrazas y logias.
- Relaciones entre ambientes y superficies exteriores.

No comenzar con un proyecto ejecutivo completo. Primero resolver una hipótesis funcional suficiente para dar coherencia al exterior.

### Ventanas como restricciones de borde

«Dos ventanas grandes separadas» puede corresponder a dos ambientes o a una sala con dos ventanas. Elegir según ancho, profundidad, uso, acceso, escalera y resto de la planta.

No generar ventanas ignorando las habitaciones ni forzar después la descripción exterior para encajar una planta arbitraria.

### Continuidad entre pisos

Conservar cuando corresponda escaleras, vacíos, ejes de apoyo, servicios y muros principales. Permitir redistribución, ampliaciones, terrazas y diferencias de construcción entre niveles.

### Reservas constructivas

Incluir espesores de muros y losas, dinteles o zonas de vigas, circulación, huecos de escalera y apoyos. Los ejes inferidos son una hipótesis compositiva: no deben convertirse automáticamente en pilastras ornamentales visibles.

### Cotas de ventanas

Separar terreno exterior, piso terminado interior, altura libre, losa, antepecho y dintel.

```text
base de ventana = piso terminado del ambiente + antepecho
```

La parte superior debe caber bajo el límite constructivo disponible. Un suelo elevado o terreno inclinado cambia la relación con la vereda; no calcular todos los vanos desde una única cota exterior.

## 5. Generación cotidiana y perfiles de Barranco

### 5.1. Atributos independientes

| Dimensión | Ejemplos |
|---|---|
| Lenguaje | Republicano, moderno, mixto |
| Construcción | Albañilería, concreto, madera, mixto |
| Acabado | Completo, parcial, sin tarrajear |
| Evolución | Unitaria, ampliada por etapas |
| Conservación | Cuidado, intermedio, deteriorado |
| Uso | Vivienda, comercio, mixto |
| Cubierta | Losa, calamina, teja, mixta |
| Ocupación | Baja, media, alta |

Evitar un único selector que mezcle estilo, recursos, deterioro y uso. La calamina condiciona construcción y equipamiento, pero no implica automáticamente deterioro.

### 5.2. Interiores visibles

- Sala: cortinas, mesa, sillas, planta.
- Dormitorio: cortina o persiana, cama simplificada, mueble.
- Cocina: mesón, repisa y objetos pequeños.
- Comercio: mostrador o estanterías.
- Servicio: ventilación, vidrio opaco y contenido reducido.

Generar conjuntos compatibles con el ambiente. Apoyar muebles, ubicar cortinas detrás del vidrio, reservar pasos y colocar macetas donde quepan. Ventanas del mismo ambiente comparten contexto, no sortean interiores contradictorios.

### 5.3. Azoteas

Organizar acceso, circulación, servicios, estancia/tendido, cubiertas ligeras y equipamiento antes de colocar objetos.

- Autocompletar aunque el techo no esté descrito.
- Preservar los elementos que sí se mencionan.
- Adaptar densidad al área útil.
- Alinear piezas con la arquitectura cuando corresponda.
- Una caseta se relaciona con la escalera; un tanque necesita apoyo compatible.
- No colocar cargas pesadas arbitrariamente sobre una lámina de calamina.
- No rellenar cada metro: el espacio de circulación también aporta realismo.

### 5.4. Herencia de estilo

```text
edificio → cuerpo → piso/sector → tipo de pieza → excepción
```

Una selección local sustituye la global sin rechazo. Las restricciones que permanezcan serán geométricas, funcionales o de mecanismo, no de pureza estilística.

### 5.5. Aleatoriedad

- Separar semillas de arquitectura, ocupación y apariencia.
- Derivar semillas locales de IDs estables y propósito.
- No usar el nivel de detalle para decidir qué arquitectura existe.
- Una vista lejana simplifica piezas; no cambia la cantidad de ambientes, balcones o tanques.

## 6. Arquitectura objetivo

```text
Contexto humano + descripción exterior + perfil generativo + semillas
                              ↓
Plan arquitectónico
  masas / espacios / plantas / superficies / accesos / cubiertas / tipos
                              ↓
Escena resuelta
  piezas dimensionales / soportes / interiores / equipamiento / materiales
                              ↓
Materializadores geométricos reutilizados y ampliados
                              ↓
GLB + diagnósticos
```

No obligar al nuevo diseño a pasar por todas las restricciones del antiguo `ReconstructionRequest`. Se pueden reutilizar sus constructores sin conservar su API.

### Organización orientativa de módulos nuevos

```text
domain/
  building_intent.py
  architectural_plan.py
  generation_profile.py
planning/
  massing.py
  spaces.py
  floorplans.py
  facade_layout.py
  access.py
  roof_layout.py
  constraints.py
generation/
  completion.py
  occupancy.py
  appearance.py
modeling/
  constructores geométricos reutilizados y ampliados
pipeline/
  building.py
```

Estas rutas son propuestas, no archivos existentes. Su distribución final se concreta en fase 0. Separar planificación, completado y materialización; evitar concentrarlo todo en el actual `modeling/theta.py`.

## 7. Protocolo común de experimentación

Cada fase debe entregar:

1. Entradas y configuración reproducibles.
2. Semillas e IDs estables.
3. Plan o resultado intermedio legible.
4. Diagnósticos y conflictos localizados.
5. Vistas comparables de planta, frente y volumen cuando apliquen.
6. Tiempo de generación y complejidad geométrica.
7. Resultados frente a criterios de aceptación.
8. Problemas pendientes, sin presentarlos como capacidades terminadas.

Los criterios siguientes son metas propuestas. No avanzar solo porque un JSON valida o un GLB se exporta. Los conteos de triángulos no miden calidad arquitectónica.

## 8. Fases de implementación

### Fase 0 — Lenguaje y banco de evaluación

**Implementar/preparar**

- Contrato de contexto y descripción compacta.
- Semántica de omisión, ausencia y presencia.
- IDs y orientación de frentes/cuerpos/pisos/sectores.
- Perfiles iniciales de Barranco.
- Casos para ajustar reglas y casos separados para evaluar.
- Precisar límites de cada operación y prioridades ante conflictos.

**Resultado esperado:** describir casas variadas sin coordenadas por pieza.

**Experimentos:** describir manualmente unos 20 casos: lotes angostos, anchos, esquinas, cercos altos, retiros abiertos, patios, logias, ampliaciones y estilos mixtos.

**Criterio de salida:** todos los casos se expresan con el vocabulario acordado, sin evidencia obligatoria y sin confundir cerco/fachada, masa/relieve o piso/cubierta.

### Fase 1 — Masas, vacíos y operaciones

**Implementar**

- Organizaciones base y operaciones de retiro, mordida, patio, adición y apertura.
- Dimensiones relativas, huellas por piso y operaciones superpuestas.
- Separación de construido, libre y cubierto.
- Parcelas irregulares, esquinas y varios frentes.

**Reutilizar/reorganizar:** `assembly.py`, `base_massing.py`, `geometry_constraints.py`, `exposure.py`, `top_composition.py`; añadir planificación de intención volumétrica.

**Resultado esperado:** maquetas sin ventanas distinguibles por ocupación, vacíos y escalonamiento.

**Experimentos:** organizaciones sobre parcelas angostas, anchas e irregulares; varias semillas; combinaciones de retiro superior, mordida y patio; múltiples frentes.

**Criterio de salida:** operaciones presentes, sin interpenetraciones involuntarias ni fragmentos inutilizables; apoyos resueltos; plantas y volúmenes revisados. No basta con obtener prismas de distinta altura.

### Fase 2 — Profundidad habitable y articulación exterior

**Implementar**

- Sectores entrantes/salientes y alternancia entre pisos.
- Pórticos, vestíbulos y logias.
- Balcones salientes vinculados a espacios.
- Retornos, losas, bordes y encuentros continuos.

**Archivos relacionados:** `facade_depth.py`, `facade_top.py`, `balcony_resolver.py`, `balcony_assembly.py`, `vertical_member_resolver.py`; contratos nuevos de espacios y superficies.

**Resultado esperado:** profundidad y espacios reales, no solo molduras superpuestas.

**Experimentos:** misma masa con paño compacto, centro retranqueado, logia derecha, entrantes alternados, cuerpo saliente y pórtico.

**Criterio de salida:** logias con suelo, acceso, límites y protección cuando corresponda; detalles siguen el plano; sin retornos abiertos ni superficies duplicadas; diferencias legibles frontal y oblicuamente.

### Fase 3 — Plantas interiores plausibles y circulación

**Implementar**

- Grafo de ambientes, accesos y conexiones.
- Núcleo vertical y continuidad de servicios/vacíos.
- Partición espacial por piso condicionada por fachada.
- Reservas de espesores y circulación.
- Generación de alternativas y selección por coherencia.

**Algoritmo inicial:** plantillas topológicas y particiones adaptables: reservar acceso/escalera/patios, distribuir ambientes perimetrales, completar interiores, conectar, ajustar a aberturas y puntuar. No comenzar con un solucionador universal.

**Resultado esperado:** plantas esquemáticas creíbles, todavía sin mobiliario detallado.

**Experimentos:** dos ventanas grandes; tres desiguales; ventana pequeña alta; cochera con ingreso independiente; piso superior diferente; logia conectada; posteriormente dos viviendas por piso.

**Criterio de salida:** ambientes accesibles conectados, escaleras continuas, ausencia de espacios residuales absurdos, particiones fuera de vanos, relación ambiente–ventana y variación sin perder restricciones exteriores.

**Dificultad:** alta; esta capacidad no existe como planificador habitable en la ruta revisada.

### Fase 4 — Vanos y envolvente constructiva

**Implementar**

- Dimensionamiento por ambiente y altura útil.
- Antepechos, dinteles, profundidad y carpintería.
- Ventanas horizontales, verticales y de servicio.
- Herencia por tipo y excepciones.
- Materiales y mecanismos independientes del estilo global.
- Espesores, losas y encuentros.

**Archivos relacionados:** `facade_composition.py`, `opening_catalog.py`, `window_assembly.py`, `door_assembly.py`, `grammar.py`; contratos de vanos/envolvente.

**Resultado esperado:** casa sencilla convincente sin depender de props u ornamentación.

**Experimentos:** conteo fijo en distintos anchos, alturas de piso distintas, primer piso elevado, distribución desfasada, carpinterías modernas en cuerpo republicano y puertas de materiales diferentes.

**Criterio de salida:** conteos/distribuciones respetados; proporciones razonables; sin invasión de pilares, losas o particiones; accesos funcionales; estilos locales admitidos; lectura correcta en render neutro.

### Fase 5 — Cerco, acceso y primer piso

**Implementar**

- Forma física de cerco independiente de estilo.
- Cerramientos altos/bajos, macizos/abiertos y parciales.
- Puerta y cochera explícitas.
- Conexión portón–patio–edificio.
- Desniveles, escalones y rampas.
- Remates de teja/calamina y protecciones.
- Medidores, timbres, numeración y detalles compatibles.

**Archivos relacionados:** `boundaries.py`, `fences.py`, `site.py`, `entrances.py`; contratos de cerramiento/anclajes. Un remate sobre cerco necesita un anclaje propio, no fingir que es una fachada del edificio.

**Resultado esperado:** conjunto coherente de exterior, límite y edificio.

**Experimentos:** cerco alto ocultando planta baja, reja baja, retiro sin cerco, cerco parcial, cochera sin puerta independiente, casa a borde de calle y cubierta sobre portón.

**Criterio de salida:** accesos conectados a espacios transitables, sin portones bloqueados por masas; remates apoyados; ausencias respetadas; planta baja coherente con el interior.

### Fase 6 — Cubiertas y azoteas autocompletadas

**Implementar**

- Superficies transitables, técnicas y ligeras.
- Cubiertas parciales/mixtas y zonas de servicio.
- Caseta vinculada al núcleo.
- Generación por uso, construcción, cubierta y evolución.
- Colocación jerárquica, apoyos y densidad adaptativa.

**Archivos relacionados:** `roofscape.py`, `roof_planes.py`, `roof_detail_resolver.py`, `roof_assembly.py`, `prefabs_roof.py`.

**Resultado esperado:** azoteas pobladas y organizadas incluso sin descripción del techo.

**Experimentos:** losa residencial, calamina, teja, terraza con sol y sombra, ampliación progresiva, uso comercial y poca superficie disponible.

**Criterio de salida:** apoyos y circulación válidos, sin colisiones; orientaciones coherentes; objetos solicitados presentes; completado activo cuando se omite el techo; no colocar tanques arbitrariamente sobre coberturas incompatibles.

### Fase 7 — Interiores visibles y estados de uso

**Implementar**

- Cortinas materializadas, persianas y coberturas variadas.
- Muebles simples por ambiente y macetas interiores.
- Apertura de hojas y fondos con profundidad.
- Variación local estable y compartida por ambiente.

**Módulos nuevos orientativos:** `interior_assembly.py`, `furniture_catalog.py`, `occupancy_generator.py`; ampliar ventanas, materiales y aleatoriedad.

**Resultado esperado:** ventanas que muestran espacios ocupados, no vidrio repetido sobre vacío.

**Experimentos:** dormitorio con varias ventanas, sala, cocina, comercio, reja con cortina, cortina abierta y vistas oblicuas.

**Criterio de salida:** muebles dentro de ambientes y apoyados, cortinas detrás del vidrio, estados compatibles, ausencia de ruido independiente y arquitectura invariable ante cambios de semilla interior.

### Fase 8 — Acabados, mezcla y carácter local

**Implementar**

- Paletas por cuerpo/piso/sector.
- Tarrajeo parcial, ladrillo y escarchado.
- Ampliaciones de distintas etapas.
- Perfiles ornamentales locales.
- Conservación condicionada por material.

**Archivos relacionados:** `materials.py`, `wall_finish.py`, `texturing/library.py`, catálogo PBR y catálogos de piezas; revisar herencia en resolvers.

**Resultado esperado:** viviendas sencillas, antiguas, modernas, remodeladas y mixtas reconocibles como parte de una diversidad local.

**Experimentos:** misma organización con distintos perfiles; mismo estilo con distinta conservación; casa antigua con carpintería nueva; planta alta incompleta; frente cuidado y laterales de ladrillo.

**Criterio de salida:** materiales no alteran accidentalmente la masa; escala física coherente; mezclas admitidas; diversidad no reducida a una plantilla; revisión sobre casos reservados.

### Fase 9 — LLM y flujo completo

**Implementar**

- Prompt breve y vocabulario estable.
- Una llamada visual para describir; compilación algorítmica posterior.
- Sin segunda llamada obligatoria para inventar metros.
- Diagnósticos y revisión semántica localizada cuando aporte información.
- Integración en B.

**Archivos relacionados:** `apps/theta_author/{contracts,compiler,prompting,providers}.py`, experimento y evaluación.

**Resultado esperado:** descripción corta que activa decisiones arquitectónicas completas.

**Experimentos:** comparar entrada manual compacta, entrada LLM compacta y flujo métrico anterior como referencia histórica. Separar error de interpretación de error de generación.

**Medir:** tiempo, longitud de respuesta, fallos geométricos, conservación de elementos descritos, coherencia visual y diversidad.

**Criterio de salida:** sin coordenadas métricas por pieza ni evidencia obligatoria; omisiones completadas; elementos descritos conservados; funcionamiento en casos nuevos.

### Fase 10 — Robustez, rendimiento y sustitución

**Implementar**

- Pruebas combinatorias y control de complejidad.
- Niveles de detalle y generación por lotes.
- Diagnósticos topológicos por componente.
- Limpieza de rutas antiguas y documentación única.

**Resultado esperado:** una ruta pública estable y adaptable, con costes medidos.

**Experimentos:** combinaciones de operaciones, lotes completos, varias semillas, diferentes niveles de detalle y reordenación de entradas con IDs estables.

**Criterio de salida:** determinismo, banco de aceptación aprobado, arquitectura invariable al cambiar detalle, presupuesto medido en equipo objetivo y ausencia de adaptadores de compatibilidad innecesarios.

## 9. Casos de referencia que deben guiar el desarrollo

### Casa sencilla, detallada

- Dos pisos y masa principal compacta.
- Patio frontal y cerco macizo alto.
- Puerta peatonal a un lado y cochera al otro.
- Remate pequeño de teja sobre el cerramiento.
- Dos ventanas horizontales arriba, con carpintería metálica.
- Cubierta ligera parcial, tanque y completado residencial.
- Interiores simples, cortinas y algunos muebles/macetas.

**Éxito:** parece construida y habitada sin añadir torres, frontones o balcones que no necesita.

### Casa compleja

- Esquina y dos frentes.
- Cuerpos adosados de distinta altura.
- Retiro, patio y ala posterior.
- Logia retranqueada y balcón saliente con acceso.
- Sectores de distinta profundidad y distribución diferente por piso.
- Frontón localizado y cubiertas mixtas.
- Mezcla de carpinterías/estilos por etapas de ampliación.
- Circulación vertical, servicios e interiores compatibles.

**Éxito:** las relaciones se resuelven conjuntamente y no mediante piezas independientes que colisionan.

## 10. Orden de evaluación y prioridades

Evaluar siempre en este orden:

1. Ocupación y vacíos.
2. Volumen y silueta.
3. Profundidad y espacios intermedios.
4. Plantas, accesos y continuidad.
5. Conteos y proporciones de fachada.
6. Espesores, apoyos y encuentros.
7. Mobiliario, cortinas y servicios.
8. Materiales, color y conservación.

No aprobar una mala masa porque tenga muchas tejas, ni ventanas mal proporcionadas porque tengan cortinas. Tampoco forzar complejidad volumétrica cuando la casa puede ser compacta y convincente mediante encuentros y pequeños relieves.

### Prioridad inmediata

```text
lenguaje de masas
  → operaciones volumétricas
  → espacios retranqueados
  → planta funcional
  → vanos coherentes
```

## 11. Seguimiento

Al crear este plan todas las fases estaban pendientes. Las fases 0–5 están cerradas: contrato `intent-v1` con 20 casos sintéticos, masas y vacíos, profundidad habitable, plantas interiores con núcleo vertical, circulación y conexiones, envolvente constructiva con vanos métricos, carpintería, losas y soportes, y acceso de planta baja con cerco/portones y transición de nivel. El banco de evaluación ya se ejecutó durante el desarrollo; es regresión sintética, no evaluación ciega.

Entregables, comandos y relevo por fase: [`phase0`](house_grammar/experiments/phase0/README.md), [`phase1`](house_grammar/experiments/phase1/README.md), [`phase2`](house_grammar/experiments/phase2/README.md), [`phase3`](house_grammar/experiments/phase3/README.md), [`phase4`](house_grammar/experiments/phase4/README.md) y [`phase5`](house_grammar/experiments/phase5/README.md). Contrato detallado: [`CONTRACT.md`](house_grammar/experiments/phase0/CONTRACT.md). Resultados reproducibles: [`results.json`](house_grammar/experiments/phase0/results.json).

- [x] Fase 0: lenguaje y banco de evaluación.
- [x] Fase 1: masas y vacíos (91 pruebas; banco sintético 20 × 3 semillas).
- [x] Fase 2: profundidad habitable (113 pruebas; 60 corridas y 8 comparaciones; accesos reservados para Fase 3).
- [x] Fase 3: plantas interiores (160 pruebas; banco 20 × 3 semillas + 6 fijaciones × 3 semillas; núcleo, circulación, partición y conexiones).
- [x] Fase 4: vanos y envolvente constructiva (200 pruebas; banco 20 × 3 semillas + 10 fijaciones × 3 semillas; 90 corridas, 6 comparaciones y GLB auditable por corrida).
- [x] Fase 5: cerco, accesos y primer piso (53 pruebas; banco 20 × 3 semillas + 11 fijaciones × 3 semillas; 93 corridas y 6 comparaciones; GLB combinado auditable).
- [ ] Fase 6: cubiertas y azoteas.
- [ ] Fase 7: interiores visibles.
- [ ] Fase 8: acabados y carácter local.
- [ ] Fase 9: integración LLM.
- [ ] Fase 10: robustez y sustitución.

Para cerrar cada fase, registrar sus casos, resultados, limitaciones y decisión de avance en este documento o en resultados enlazados. Actualizar `PIPELINE_GRAMATICA.md` cuando cambie la ruta ejecutable, sin presentar propuestas como implementación vigente.

**Principio rector:** que el modelo diga poco, pero que cada cosa que diga active una decisión arquitectónica completa; el generador aporta el resto de manera coherente, variada y plausible para Barranco.
