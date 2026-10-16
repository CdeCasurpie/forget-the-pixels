# Experimento: descripción española → theta en dos llamadas

Rama: `experimento-paralelizacion`. Experimento aislado; no cambia A/B ni el motor.
Los pasos son **secuenciales** (2 consume 1), aunque el nombre de rama sea paralelización.
Preparado sin ejecutar llamadas a Claude ni generar un theta por IA.

## Caso congelado

- Lote **1136002**, activo en A al preparar; geometría `5ca18f85c5c142f08ab8a1f46708bb3a`.
- Paquete B original: `data/barranco/theta_author/runs/3bbc4f17cf08462bbe9ea707c8d2c0a1/package.json`.
- Formulario comparado con autosave de B: coincidente al preparar.
- Tres pisos, altura regular **3 m**, primer piso igual: cotas **0, 3, 6, 9 m**.
- Estilo sugerido **republicano**. Los flags originales dicen suggested; este experimento impone pisos/cotas por instrucción del usuario, sin modificar el original.
- Tres recortes seleccionados en B, con poses/proyección y hashes originales. Son imágenes proyectadas, no ortofotos: no medir proporciones de píxeles como distancias reales.
- Principal: `inputs/images/001.jpg`, primera seleccionada en B. Se inspeccionó: hay árboles y vehículos que ocultan la fachada. No es un caso de visibilidad perfecta; el paso 1 debe registrar incertidumbres. Revisar visualmente las tres antes de gastar una llamada.

## Proyección de identificación (actualizado)

Ambos pasos reciben ahora **fotografías marcadas**, en `inputs/projected_images/`:
paso 1 las tres, paso 2 la principal. El manifest selecciona esos adjuntos automáticamente.
El prisma usa la parcela local congelada, su origen métrico y la cámara angular de cada foto.
Incluye suelo a 0 m, fin del primer piso a 3 m, segundo nivel a 6 m y coronación a 9 m.
Las cotas se leen de `context_and_levels.json`, no se reparten uniformemente: si el primer
piso tiene otra altura en un futuro caso, la proyección respeta esa diferencia.
Amarillo=suelo, verde=niveles, magenta=coronación, azul=aristas. Hay etiquetas y leyenda.
Los originales limpios permanecen en `inputs/images/`; ya no son los adjuntos enviados.
La leyenda agrega 90 píxeles arriba, sin cambiar la proyección de la foto.
Las líneas son referencias impuestas, no evidencia de la silueta o de ocupación total.

Regeneración local (requiere numpy y OpenCV, no llama a la API):
`python3 apps/experimento_paralelizacion/preparar_proyecciones.py`.
Se generaron las tres imágenes y se inspeccionó la principal. No se ejecutaron prompts.
El presupuesto visual orientativo pasa de ~820 a ~935 tokens por imagen (960×730);
la contabilización efectiva depende del proveedor.

## Organización

```
inputs/                registro humano, paquete B completo, contexto local,
                       cotas/aristas, evidencia, imágenes y hashes
guides/                copias congeladas de guía, catálogo y referencia de campos
paso_1/prompt.md        cuestionario arquitectónico completo en español
paso_1/generar_descripcion.py
paso_2/prompt.md        instrucciones de traducción única al contrato
paso_2/generar_theta.py
common.py              transporte Messages, preparación y conservación de resultados
```

`base_request.json` es un prisma de referencia preparado localmente, NO el resultado deseado ni ground truth. Las masas deben interpretarse a partir de las fotos. El contexto ya está en coordenadas locales canónicas; cada arista tiene extremos y longitud. El paquete fuente conserva clasificación, notas, geometría y selección de fotos originales.

## Entradas y salidas

**Paso 1:** registro + contexto/cotas/aristas + metadatos de evidencia + catálogo visual + tres fotos → `descripcion.txt`. Pregunta por masas, planos, vanos, balcones, soportes, frontones, cubiertas, cercos, puertas/portones, estacionamiento, accesos, materiales y detalles. Localiza mediante intervalos con denominador explícito y registra confianza/oclusiones.

**Paso 2:** mismo registro/contexto + texto anterior + imagen principal + catálogo + guía + referencia exhaustiva de campos + contrato base → `request.json`. Una única llamada, sin historial ni reparaciones automáticas. Prioriza masa y ubicación antes de ornamentación.

Cada ejecución conserva `prompt_completo.txt`, `payload.json`, `budget.json`, respuesta original, texto crudo y métricas de uso/latencia/stop_reason. Una respuesta truncada no se promueve a resultado. Paso 2 comprueba sintaxis JSON y contexto intacto: **no certifica geometría ni cumplimiento de niveles**; ejecutar la validación posterior. Los outputs contienen fotos/datos del lote; las credenciales no se guardan.

## Tokens y límites

Medición local del texto preparado (sin ejecutar los scripts):

| | Texto de entrada | Estimación heurística | Imágenes | Salida máxima configurada |
|---|---:|---:|---:|---:|
| Paso 1 | ~43 903 caracteres | ~11 000–22 000 tokens | 3 de 960×640 | 8192 |
| Paso 2 | ~121 295 caracteres + descripción | ~30 000–61 000 + descripción | 1 de 960×640 | 16384 |

Las imágenes podrían aportar aproximadamente 820 tokens cada una según la regla orientativa ancho×alto/750; el proveedor puede redimensionar o contabilizar distinto. Un texto de descripción de 15–25 mil caracteres añade aproximadamente 4–13 mil tokens. Presupuesto conservador del paso 2: hasta ~91 mil tokens incluyendo salida. No son conteos exactos ni garantía de costo: `usage` de la respuesta será la medición real. Confirmar límites del endpoint/modelo; un proxy puede imponer otros límites.

Se mantiene la referencia completa para no pedir JSON sin tipos/campos. No se envía todo el repositorio. Si el resultado se trunca, conservar el intento como fallo y aumentar explícitamente `--max-tokens` para otro intento; no reparar silenciosamente. Modelo por defecto: `claude-haiku-4-5-20251001`, configurable con `--model` si el proveedor usa alias.

## Ejecutar manualmente desde la raíz del repositorio

Python 3.10+, biblioteca estándar para los dos scripts. Para validar la gramática hacen falta sus dependencias habituales. Las carpetas de salida deben ser nuevas.

```bash
export ANTHROPIC_API_KEY='tu-clave'
# Opcional; por defecto https://api.anthropic.com
export ANTHROPIC_BASE_URL='https://api.anthropic.com'

python3 apps/experimento_paralelizacion/paso_1/generar_descripcion.py \
  --output /tmp/opencode/experimento-p1

python3 apps/experimento_paralelizacion/paso_2/generar_theta.py \
  --description /tmp/opencode/experimento-p1/descripcion.txt \
  --output /tmp/opencode/experimento-p2
```

También se admite `ANTHROPIC_AUTH_TOKEN` mediante `Authorization: Bearer`,
para el proxy configurado en `ANTHROPIC_BASE_URL`. Si ambas credenciales existen,
se usa el token. No reemplazar la URL de tu proxy por el ejemplo si usas ese token.

Agregar `--prepare-only` prepara el payload sin conexión ni credenciales, en otra carpeta nueva. Paso 2 necesita una descripción incluso para esta preparación. No pegar secretos en prompts.

Validación posterior, independiente de las dos llamadas:

```bash
PYTHONPATH=house_grammar/src python3 house_grammar/docs/guia_theta/revisar_theta.py \
  /tmp/opencode/experimento-p2/request.json \
  --output /tmp/opencode/experimento-validacion
```

## Evaluación rápida

1. Comprobar que el lote descrito es el correcto en las fotos y que no absorbió vecinos.
2. Marcar 5 rasgos visibles prioritarios; revisar masas/planos, accesos, vanos, cerco y cubierta.
3. Separar errores de percepción del paso 1, traducción del paso 2 y validación del motor.
4. Verificar cotas y número de pisos impuestos, parcela/frentes, inventario de piezas y ausencias explícitas.
5. Comparar render y foto; no usar un request histórico como verdad geométrica.
6. Registrar tokens, tiempo, stop_reason, éxito de parseo/resolución y piezas omitidas/inventadas. No afirmar mejora frente a una sola llamada sin realizar después un control comparable.

La primera prueba puede hacerse en unos 15 minutos, dependiendo de latencia y tamaño de salida. No se ha ejecutado ni facturado ninguna llamada como parte de esta preparación.
