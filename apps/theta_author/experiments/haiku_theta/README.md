# Piloto de autoría incremental con Claude Haiku

**Objetivo:** partir del trabajo humano de A/B y completar una casa por decisiones
pequeñas, verificables y acumulativas. No pedir una reconstrucción completa en un
solo turno ni volver a estimar los pisos que la persona ya contó.

Código del experimento: esta carpeta. Datos/salidas: `data/barranco/theta_experiments/`.
Se consume una instantánea preparada por B. No se modifica el formulario humano,
el catastro, la selección vigente ni el proveedor de la interfaz.

## 1. Base que aporta la aplicación

| Información | Uso en este experimento |
|---|---|
| Parcela y frentes revisados | Contexto métrico fijo, origen local y aristas numeradas |
| Cantidad de pisos | **Fija por instrucción del usuario**, aunque el formulario antiguo diga suggested |
| Altura habitual / primer piso diferente | Cotas iniciales sugeridas; altura total con mode=fixed se respeta |
| Estilo humano | Sugerencia visual, no regla que obligue a ornamentar |
| Fotos seleccionadas | Se copian los bytes y verifican sus hashes |
| Cámaras | Se conserva angular-enu-v1, posición, encuadre y altura de cámara |
| Notas | Se entregan en todos los turnos |
| Historial | Cada etapa recibe inventario, theta aceptado, resolución y decisiones anteriores |

El programa construye automáticamente el **theta base**: parcela local, niveles
humanos, un prisma de referencia, fachadas vacías y semilla fija. No pretende que
la parcela completa sea la huella real. La etapa 02 mejora esa hipótesis.

Además entrega una receta paramétrica y los marcos de frente ya calculados. Haiku
puede indicar retiro, profundidad y fracción de ancho; el motor intersecta esas
regiones con el catastro sin pedirle al modelo aritmética de vértices rotados.

Antes de preparar se comprueba que el lote siga activo, que su geometría coincida
con la vigente, y que el paquete incluya el último formulario guardado. Si no,
se prepara de nuevo en B. Las revisiones posteriores no alteran esta instantánea.

## 2. Secuencia completa: 12 requests especializados

| Etapa | Recibe especialmente | Solo puede entregar/modificar | Queda cerrado después |
|---|---|---|---|
| `01_lectura` | Base, fotos limpias, identificación, plano y cámaras | Inventario observado/inferido y oclusiones | Correspondencia del lote, vocabulario de sus partes |
| `02_masas` | Inventario, cotas y marcos de frente calculados | Componentes relativos (preferidos) o masas XY, y retícula de niveles | Huellas, retiros, apoyos, pisos y IDs resueltos |
| `03_lenguaje` | Fotos, sugerencia de estilo, masas | `architectural_style` o null | Perfil global de piezas; no color ni adornos |
| `04_puertas` | Paredes, dominios visibles y cotas | Puertas/portones del edificio | Ubicación, dimensiones y carpintería de accesos |
| `05_ventanas` | Puertas ya colocadas y fotos | Ventanas | Ritmo, forma, dimensiones, marcos/rejas |
| `06_balcones` | Vanos e índices resueltos | Balcones/galerías/barandas | Tipo, plataforma, cierre y apoyos anidados |
| `07_miembros` | Vanos, portales y balcones existentes | Pilastras/columnas/postes independientes | Orden vertical sin duplicar soportes |
| `08_remates` | Silueta y piezas aceptadas | Frontones, entablamentos, trim, top_profile y proyecciones | Coronación y relieve de pared |
| `09_cubiertas` | Masas y frontones con IDs | Techos, aleros, parapetos, props y marquesinas | Cubierta coordinada con remates |
| `10_sitio` | Suelo libre, límites y puertas | Cercos, zonas de suelo y entradas | Cerco/portones, patio/jardín y accesos |
| `11_materiales` | Toda la geometría cerrada | Slots, colores y regiones de material | Apariencia física sin cambiar formas |
| `12_revision` | Comparaciones alineadas e historial | Diagnóstico y etapa responsable de cada corrección | Aceptar, revisar o declarar evidencia insuficiente |

**Puertas antes de ventanas:** reserva accesos y permite que ventanas respeten sus
dimensiones. **Cubierta después de remates:** permite usar crown_ref real. Un
balcón necesita una abertura existente; no se inventa su puerta al final.

Una pieza ausente se representa con `[]`; eso también es una decisión válida.
No es obligatorio poblar todos los catálogos para que una casa sea buena.

## 3. Paquete completo de cada request

Cada llamada abre un turno autocontenido. No depende de que el proveedor recuerde
una conversación anterior. Lleva:

1. [Instrucciones comunes](prompts/common.md) y prompt específico de la etapa.
2. **Secciones completas de guía y catálogos pertinentes a la etapa**, incorporadas
   como texto, no como rutas que el modelo no puede abrir. Por ejemplo, masas recibe
   regiones/soportes, no el catálogo de 25 balcones; ventanas recibe formas/rellenos/
   perfiles. La revisión final recibe el conjunto. No se recortan por un presupuesto
   de tokens; se seleccionan por responsabilidad arquitectónica.
3. JSON Schema de respuesta generado desde los contratos reales; descripciones
   de los campos de dominio alcanzables por esa etapa, obtenidas de `campos.json`.
4. En etapas de autoría, ejemplo de sintaxis de una casa rica, rotulado como otra casa.
5. Formulario humano original y restricciones efectivas separadas.
6. Theta actual, retícula de pisos, inventario y decisiones aceptadas anteriores.
7. Arquitectura resuelta completa: masas, techos, dominios expuestos, piezas,
   completados del motor, tablas de paredes e índices actuales de vanos.
8. Cámaras y esquinas proyectadas de paredes para asociar foto y coordenadas.
9. Fotos limpias, copia auxiliar con prisma y plano métrico; tras materializar,
   también comparaciones del último estado aceptado y diagnóstico geométrico.

Los prompts están separados en [prompts/](prompts/). No hay que enviar referencias
a archivos locales esperando que Claude los lea: `messages.json` contiene texto y
**bytes base64 de cada imagen**. Las credenciales nunca se escriben allí.

Las anotaciones del prisma ayudan a identificar el lote, pero no son evidencia
independiente de altura/huella. La lectura inicial debe diferenciar vecinos,
oclusiones, puertas de cerco y puertas de edificio.

**Aceptación técnica no equivale a verdad observada.** El inventario inicial
también puede equivocarse. Cada etapa contrasta sus elementos con las fotos; una
hipótesis de lectura puede refinarse con nueva evidencia. Lo bloqueado son los
datos humanos fijos y la geometría ya aceptada, no una interpretación visual
equivocada del primer turno. Registrar discrepancias en evidence/notes.

## 4. Respuesta, fusión y verificación

Cada turno devuelve un objeto con esta envoltura; `changes` cambia según la etapa:

```json
{
  "stage": "03_lenguaje",
  "changes": {"architectural_style": "republicano"},
  "evidence": [{
    "element": "lenguaje_de_piezas",
    "view_ids": ["ID_REAL_DE_LA_FOTO"],
    "status": "inferred",
    "description": "Justificación breve basada en las piezas visibles."
  }],
  "notes": ["Se conserva o ajusta la sugerencia humana por esta razón."],
  "blockers": []
}
```

No se permite devolver otro request ni editar claves ajenas a la etapa. El programa:

1. Valida estructura, nombres, referencias de evidencia y ámbito de modificación.
2. Fusiona la propuesta sobre una copia del estado aceptado.
3. Comprueba N pisos mediante una **retícula global de N+1 cotas**. Cada masa usa
   sus cotas interiores; se impiden pisos extra escondidos en masas apiladas.
4. Ejecuta el decodificador theta y `resolve_theta` para obtener referencias reales.
5. En etapas geométricas, ejecuta `reconstruct`, envolvente y topología, exporta
   GLB y genera comparación angular de la misma malla.
6. Publica checkpoint y estado únicamente cuando las comprobaciones pasan.

Las incidencias de conectividad (p. ej., barras de reja desconectadas dentro de un
registro) quedan documentadas y no se llaman "topología limpia". Bordes abiertos,
aristas no-manifold, orientación incoherente y caras degeneradas/duplicadas en
violaciones bloquean la etapa para revisión.

Por defecto se permite **una reparación** de formato/contrato/geometría con el error
exacto, dentro de la misma etapa. Se conserva el intento inicial. Un bloqueo
declarado, respuesta truncada o error de transporte detiene la ejecución; no dispara
una cadena de reintentos. `notes` pide decisiones breves, no razonamiento interno.

### Qué hacer si una etapa anterior estaba equivocada

No arreglarlo mediante otra pieza. La respuesta señala el bloqueo o la revisión
final indica `target_stage`. Crear una rama **antes** de esa etapa, corregir allí
y volver a ejecutar sus dependientes. Por ejemplo, cambiar masa invalida todos
los anclajes posteriores; cambiar puertas invalida la secuencia desde puertas.

El original y todos sus intentos se conservan. La revisión final puede terminar
en `revise`: haber completado las 12 llamadas no equivale a aprobación visual.

## 5. Comparación de cámaras

`rendering.py` usa ray casting CPU de Open3D sobre la misma MeshData exportada al
GLB. Los rayos se calculan con las fórmulas y centros de píxel de `angular-enu-v1`.
Esto evita aproximar el encuadre angular mediante una cámara perspectiva distinta.

- Origen UTM y geometría local se reconcilian explícitamente.
- Se trabaja Z-up; el exportador GLB convierte a Y-up. No se vuelve a transformar
  la geometría de trabajo como si ya hubiera sido exportada.
- Se obtiene foto / render / superposición para cada cámara seleccionada.
- El render usa color base con sombreado simple: **sin texturas PBR ni transparencia**.
- Cámara a 2.5 m y suelo plano son supuestos actuales; no calibración exacta.
- No incluye coches, árboles ni vecinos: la oclusión de la foto se interpreta por
  separado y no se usa una diferencia global de píxeles como puntuación de fidelidad.

Se comprueba con un test que rayos y proyección recuperen los mismos centros de
píxel, y con un render real de un prisma. Los GLB permiten inspección adicional
de los materiales PBR en el visor que ya utilizas.

## 6. Piloto preparado: lote 1134706

- Dos pisos humanos.
- Primer piso sugerido: 3.0 m; segundo: 2.6 m; altura de masa inicial: 5.6 m.
- Estilo sugerido: republicano.
- Tres fotos elegidas por la persona.
- Fotos con ventanas, cerco/retiro, materiales diferenciados y coronación: hay
  suficientes rasgos para evaluar fidelidad más allá de un prisma.
- La curvatura aparente se debe contrastar entre vistas; no atribuir automáticamente
  la distorsión angular a la silueta arquitectónica.

Paquete fuente:
`data/barranco/theta_author/runs/380ddc17a3ad40cd8bd4ec779dbc0946/package.json`.

Caso de trabajo preparado:
`data/barranco/theta_experiments/1134706_etapas_v1/`.
Consultar `state.json` para saber qué etapas se ejecutaron; no confundir prompts
preparados con respuestas reales del modelo.

## 7. Comandos (desde la raíz del repositorio)

Dependencias: las de la gramática y B, más `httpx` y `open3d` para transporte/render.
Las dos variables de entorno son las del script probado por el usuario:
`ANTHROPIC_BASE_URL` y `ANTHROPIC_API_KEY`. Modelo por defecto: `claude-haiku-4-5`.

Preparar otro caso, con directorio nuevo:

```bash
python3 -m apps.theta_author.experiments.haiku_theta.cli prepare \
  --package data/barranco/theta_author/runs/380ddc17a3ad40cd8bd4ec779dbc0946/package.json \
  --output data/barranco/theta_experiments/1134706_otro_intento
```

Inspeccionar lo que se enviará en el siguiente turno, sin llamar a la API:

```bash
python3 -m apps.theta_author.experiments.haiku_theta.cli packet \
  --case data/barranco/theta_experiments/1134706_etapas_v1 \
  --output /tmp/opencode/haiku-siguiente-paquete
```

**Ejecutar solo la siguiente etapa**, para revisar poco a poco:

```bash
python3 -m apps.theta_author.experiments.haiku_theta.cli next \
  --case data/barranco/theta_experiments/1134706_etapas_v1
```

Ejecutar secuencialmente hasta un límite explícito:

```bash
python3 -m apps.theta_author.experiments.haiku_theta.cli run \
  --case data/barranco/theta_experiments/1134706_etapas_v1 \
  --through 05_ventanas
```

`--model`, `--max-tokens` (16384 por defecto) y `--repairs 0|1|2` son configurables.
El piloto mostró que el proveedor puede agotar 8192 tokens antes de devolver el
JSON de masas; las respuestas con stop_reason=max_tokens se conservan y rechazan.
También agotó 16384 devolviendo solo un bloque de razonamiento, sin texto JSON.
Ahora `--thinking-budget 4096` solicita un límite para esa parte y deja espacio para
la respuesta; `--thinking-budget 0` la desactiva. Se registra el ajuste en el cuerpo
HTTP. Las referencias se seleccionan por etapa y masas prefiere regiones relativas.
`--no-render` es solo diagnóstico: no permite completar revisión visual sin imágenes.

Importar una respuesta guardada por otra llamada al mismo prompt:

```bash
python3 -m apps.theta_author.experiments.haiku_theta.cli apply \
  --case data/barranco/theta_experiments/1134706_etapas_v1 \
  --response /ruta/respuesta.json
```

Rehacer una etapa ya aceptada conservando el experimento original:

```bash
python3 -m apps.theta_author.experiments.haiku_theta.cli branch \
  --case data/barranco/theta_experiments/1134706_etapas_v1 \
  --before 04_puertas \
  --output data/barranco/theta_experiments/1134706_puertas_v2 \
  --note "El portón verde pertenece al cerco; revisar la puerta de la vivienda."
```

## 8. Archivos de una ejecución

```text
manifest.json                  lote, procedencia y política del experimento
inputs/                        fotos, cámaras, formulario y snapshot congelados
  plan.png                     aristas, dimensiones y cámaras
  target_01.jpg                identificación auxiliar del lote
state.json                     theta acumulado y etapas aceptadas
checkpoints/00_base/            theta inicial construido desde la clasificación
checkpoints/02_masas/           estado aceptado y ruta a su intento concreto
attempts/02_masas/001/
  packet.json                  fuentes/hashes, adjuntos y contrato
  prompt.txt                   todo el texto suministrado
  response_schema.json         esquema de salida específico
  messages.json                cuerpo HTTP exacto, incluidas imágenes, sin credenciales
  api_response.json            respuesta original de la API
  response.txt                 texto propuesto, incluso si no es válido
  metrics.json                 tokens, tiempo, modelo y stop_reason
  request.json                 theta candidato
  resolved_theta.json          resolución del candidato
  validation.json              comprobación geométrica
  topology_summary.json        diagnóstico por componente
  building.glb                 malla de esta etapa, junto al JSON
  comparisons/                 vistas alineadas de las cámaras seleccionadas
  status.json                  aceptado, rechazado o fallo
```

Un intento rechazado puede tener solo los archivos de las fases alcanzadas. Su
geometría candidata nunca reemplaza el estado aceptado. `state.last_artifact` señala
el GLB/comparaciones actuales; no hay que buscarlos en directorios temporales.

## 9. De un caso a diez y después a la zona

1. Cerrar el primer caso etapa por etapa, revisando especialmente masa y vanos.
2. Seleccionar diez paquetes actuales variados y mantener la misma versión de prompts.
3. Registrar fidelidad por etapa, reparaciones, errores de cámara y tiempo/tokens.
4. Comparar un par de lotes también sin información humana como experimento separado:
   en ese caso hay que retirar pisos/alturas/estilo y TODO derivado de ellos, incluido
   el prisma/retícula inicial, no solo borrar una frase del prompt. El CLI actual es
   deliberadamente el piloto **asistido**; la condición ciega se prepara después.
5. Congelar polígono/lista de IDs de la zona y paquetes elegidos, sin inferirla del color
   de una captura de pantalla. No mezclar formularios obsoletos con geometría vigente.
6. Paralelizar llamadas entre lotes; **dentro de cada lote las etapas son dependientes**.
   Un límite de 50 sería para requests de theta, no para 50 renderizadores. La cola
   de geometría/render debe tener su propio límite. Este CLI ejecuta un caso secuencial;
   el planificador de zona se añade tras evaluar los diez casos.

La división por etapas apunta a mejorar representación y atribuir errores: más
requests no garantizan fidelidad, pero permiten localizar y corregir cada decisión.

## Comprobaciones

```bash
python3 -m pytest apps/theta_author/experiments/haiku_theta/tests -q
```

Cubren restricciones humanas, pisos ocultos en masas, inmutabilidad de etapas,
claves desconocidas, referencias de evidencia, recorrido de contratos con malla
real, proyección angular/render y rechazo de respuestas truncadas. No llaman a la API.
