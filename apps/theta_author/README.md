# B · Autor ágil de thetas

Aplicación local con **MOCK TEMPORAL**. El mock no analiza fotografías: devuelve
una propuesta determinista para comprobar el flujo. Prompt y contrato provisionales.

## Iniciar

Desde la raíz del repositorio, con el catastro ya inicializado por A:

```sh
python3 -m pip install -r apps/theta_author/requirements.txt
python3 -m apps.theta_author.server
```

Abrir **http://127.0.0.1:8767**. B lee las revisiones de A directamente; no requiere
su servidor abierto. Opciones: `--data`, `--cadastral-workspace`, `--workspace`,
`--port`, `--workers 1..8`. Una instancia por workspace, dos trabajos por defecto.

Para pruebas aisladas, leyendo el mismo catastro:

```sh
python3 -m apps.theta_author.server --port 8768 --workspace /tmp/opencode/theta-demo
```

## Flujo con teclado (sin mouse)

Bloque compacto QWERTY; cada letra aparece como insignia en su control.
Los atajos no actúan mientras escribes ni con un diálogo abierto.

| Teclas | Acción |
|---|---|
| `Q` `A` | Cantidad de pisos / altura por piso: enfoca el número y lo selecciona; escribe el valor exacto y `Tab` o `Enter` avanza |
| `S` | Activa/desactiva «Primer piso diferente»; al activar salta a su altura |
| `W` | Altura del primer piso (enciende la casilla si está apagada) |
| `1` `2` `3` `4` `5` | Republicano, barroco, clásico, madera, moderno |
| `D` `F` | Página anterior / siguiente de fotos |
| `Z` `X` | Marcar la 1.ª / 2.ª foto visible |
| `C` | Más fotos cercanas |
| `V` | Notas |
| `G` | Siguiente lote sin paquete (el más cercano; si no hay, retoma preparados sin generar) |
| `Enter` | Preparar paquete / generar theta |
| `/` | Buscar lote · `H` ayuda · `Esc` cerrar · `Retroceso` volver y ajustar |

Ejemplo de ciclo: `G` → `Q 3 Tab 2.8 Tab R Enter Enter G`.

## Flujo rápido

1. **Seleccionar lote** sobre el mapa a pantalla completa o buscar su ID. Aparecen
   fotos flotantes a la izquierda y controles a la derecha. No hay scroll del flujo
   principal en pantallas de escritorio; rueda y arrastre actúan sobre el mapa.
2. **Ajustar sugerencias:** cantidad de pisos y altura por piso. Opcionalmente activar
   «Primer piso diferente» y ajustar su altura. Altura total = primer piso +
   `(cantidad de pisos − 1) × altura habitual`. El prisma cambia en cada frame y
   la línea verde del primer piso aparece únicamente con esa casilla activada.
3. **Elegir un estilo visual** entre republicano, barroco, clásico, madera y moderno.
   Las imágenes son ilustraciones orientativas hechas para esta interfaz, no ejemplos
   arquitectónicos validados. Todo el formulario es sugerido, incluidas las notas.
4. **Revisar las tres fotos más cercanas.** Se muestran dos imágenes grandes por página.
   «Más fotos» añade candidatas bajo demanda; hay que marcar las que se enviarán.
   Los puntos amarillos corresponden a las fotos incluidas. Una selección guardada
   se respeta al reabrir; inicialmente se muestran sus primeras tres cámaras.
5. **Preparar paquete →** registra una versión sin esperar a proyectar/copiar fotos.
   La pantalla avanza inmediatamente al paso de envío; los adjuntos continúan en
   segundo plano y el estado indica cuándo el paquete está realmente completo.
6. **Generar theta · MOCK →** puede solicitarse mientras se preparan las imágenes.
   El servicio espera a completar el paquete antes de llamar al proveedor. Puedes
   pasar a otro lote mientras termina. Volver y editar no envía nada automáticamente.

Mapa: **azul sutil = paquete completo**, **verde = theta generado y validado por el
adaptador mínimo**, punto ámbar = cambios de formulario posteriores. Una revisión
catastral distinta invalida los colores anteriores. El estado `preparing` usa un
tono neutro; no se presenta un paquete incompleto como listo.

El paquete idéntico se reutiliza mediante hash de formulario normalizado (incluye
geometría y fotos). El envío es idempotente: repetir clic no hace otra llamada al
modelo. Cambiar datos y preparar de nuevo conserva una nueva versión.

## Guardado y rendimiento

- Cada movimiento de slider se guarda inmediatamente en `localStorage`. Se sincroniza
  al servidor tras una agrupación de 140 ms, serializada por lote. La UI muestra si
  está guardado localmente, sincronizado o pendiente por error. Cambiar de lote no
  espera la escritura; los IDs/revisiones quedan capturados en cada envío.
- `autosaves/<lot_id>.json` contiene el último formulario. Preparar un paquete crea
  una instantánea inmutable en `drafts/`; no se crean cientos de versiones al arrastrar.
- Al cerrar se intenta enviar lo pendiente; si la red falla, se recupera del guardado
  local al reabrir ese lote. Las revisiones antiguas se rechazan en el servidor.
- Caché de revisiones catastrales inmutables y de polígonos del mapa; índices de
  preparaciones/trabajos en memoria evitan recorrer archivos en cada selección.
- Solo dos solicitudes de imagen visibles, cancelación al cambiar de lote/página,
  caché de 24 imágenes en el navegador. El servidor descarta peticiones desconectadas
  que todavía esperan un turno de proyección; las dos ya en curso pueden terminar.
- B usa decodificación JPEG a media resolución y caché de dos panoramas de entrada,
  además de la caché de 64 encuadres. A conserva su decodificación original.
- La proyección angular sigue siendo `angular-enu-v1`, 960×640. Cambiar alturas no
  vuelve a solicitar imágenes: el prisma y la línea de piso son Canvas locales.
- La preparación usa dos workers independientes de la cola del proveedor; registra
  el pedido primero y congela fotos limpias/hashes después. Su duración depende de
  cuántas fotos selecciones y de la caché, pero no bloquea la navegación.

## Partes reemplazables

| Archivo | Responsabilidad |
|---|---|
| `providers.py` | `Provider.generate(package) -> str`, única frontera con el modelo |
| `prompts/guide_v1.txt` | Guía provisional |
| `prompting.py` | Prompt exacto, evidencia, esquema y hashes del código |
| `contracts.py` | Formulario y respuesta `authoring-v1`, con `levels_m` opcional |
| `compiler.py` | Validación y adaptación mínima a theta 0.3 |
| `service.py` | Autosave, paquetes, cola, deduplicación y versiones |
| `static/styles/*.svg` | Ilustraciones intercambiables de los cinco estilos |

Para conectar una API o modelo local, implementar `name`, `model`, `is_mock=False`
y `generate(package)`, e inyectar con `create_app(provider=MiProveedor())`.
El adaptador devuelve texto original; el servicio conserva y valida la respuesta.
Un proveedor multimodal debe adjuntar los **bytes**, no solamente rutas: `attachment`
es relativo a `runs/<package.run_id>/`, mientras `image_path` identifica el panorama
fuente relativo a `--data`. El workspace puede inyectarse en el constructor del proveedor.
La UI actual está rotulada para el mock; actualizar las etiquetas al activar un proveedor real.

Cada llamada hace un intento. No hay reenvíos automáticos de resultados inciertos.
Al reiniciar, trabajos `preparing/queued/running` pasan a `interrupted`. Se conserva
cancelación de pendientes, importación manual y selección de versión vigente mediante API.
El paso de envío ofrece «Ver paquete / historial» y descarga ZIP en un diálogo separado.

## Archivos persistentes

```text
data/barranco/theta_author/
  autosaves/<lot_id>.json       # último formulario, escritura atómica
  drafts/<draft_id>.json        # formulario + instantánea de preparación
  runs/<run_id>/
    record.json                # estado, proveedor, hashes, fechas
    package.json               # prompt exacto, contrato, revisión, evidencia
    evidence/001.jpg            # encuadres limpios congelados
    response.txt               # respuesta original, también si es inválida
    proposal.json              # autoría interpretada o null
    request.json               # context + theta, o null si inválida
    validation.json            # errores, alcance y origen métrico
  selections/<lot_id>.json      # selección manual histórica (API)
```

Los JSON se publican mediante renombrado atómico y fsync. La importación manual crea
otro `run_id`, sin reemplazar la respuesta anterior. Paquetes previos y campos fijados
del contrato antiguo se siguen leyendo; el formulario rápido nuevo siempre usa sugerencias.

## Alcance del mock

El request usa una masa explícita derivada del lote como referencia, niveles sugeridos
(incluye primer piso diferente), cubierta plana y fachada vacía. Es un placeholder,
no una reconstrucción observada. Los estilos no determinan materiales ni colores.
El panel de masas/mordidas está retirado temporalmente; sus contratos históricos se
mantienen para poder leer versiones anteriores.

Se valida estructura, referencias y compatibilidad del request mínimo; no se ejecuta
el resolver completo de gramática, no se genera malla ni se evalúa fidelidad visual.
`validation.coordinate_frame` conserva CRS y origen para convertir metros locales
a EPSG:32718. Los IDs y coordenadas originales permanecen en el paquete.

Pendientes del alcance arquitectónico completo: medición por rayos, detalles de
fachada, masas complejas, guía/ejemplos revisados y proveedor real.

## Comprobaciones

```sh
python3 -m pytest apps/theta_author/tests apps/cadastral_editor/tests -q
node --check apps/theta_author/static/app.js
```

Incluyen persistencia, respuesta inválida, revisión catastral, compatibilidad del
decodificador real, proyección congelada, no bloqueo al preparar, envío único,
colores de avance y niveles no uniformes. Las pruebas usan directorios temporales.
