# Editor catastral local — Aplicación A

Desde la raíz de `forget-the-pixels`:

```sh
python -m pip install -r apps/cadastral_editor/requirements.txt
python -m apps.cadastral_editor.server
```

Abrir **http://127.0.0.1:8765**. Para probar sin editar el dataset de trabajo:

```sh
python -m apps.cadastral_editor.server --demo --workspace /tmp/opencode/catastro-demo --port 8766
```

## Uso

1. Seleccionar lote; Shift+clic o «Multiselección» para seleccionar varios.
2. Revisar las fotos. «Más fotografías» muestra más candidatas; se puede introducir
   otro ID de panorama. Pulsar una foto para ampliarla con el mismo prisma.
   Los puntos amarillos numerados del mapa son las cámaras mostradas; pulsa uno
   para localizar su foto. «Ver cámaras en mapa» encuadra lote y cámaras.
3. «Dibujar corte»: añadir puntos atravesando completamente el lote; «Quitar
   punto» permite corregir la línea. «Prever corte» muestra dos hijos.
4. «Unir selección» fusiona vecinos de la misma manzana (o sin asignación).
5. Las manzanas y los frentes ya se precalculan por conexión entre lotes.
   «Asignar selección» permite corregir un grupo o añadir lotes a un ID existente.
6. Activar **«Mover manzanas» en la barra del mapa** y arrastrar cualquier lote:
   se selecciona y mueve su manzana completa. Se ve el contorno desplazado mientras
   arrastras; al soltar aparecen **Confirmar y guardar / Cancelar** sobre el mapa.
   También se pueden introducir desplazamientos este/norte en metros. Esc sale del modo.
7. Ajustar los frentes mediante sus casillas. Verde: frente; rojo: no frente.
8. **Confirmar y guardar** publica una revisión. Cancelar no modifica los datos.
9. Historial, deshacer la última operación y exportar JSON están al final del panel.

El arrastre convierte sus extremos del mapa a EPSG:32718 para calcular el
desplazamiento métrico; puede precisarse con los campos numéricos. Los contornos originales
se muestran mediante la casilla «Original».

## Satélite

El modo inicial es sin conexión. «Satélite · Esri» usa World Imagery con su
atribución visible y requiere Internet. Para Google configurar una clave de
**Maps Static API**, con restricciones de navegador apropiadas:

```sh
GOOGLE_MAPS_API_KEY=... python -m apps.cadastral_editor.server
```

Google se muestra como una imagen central de 640×640 píxeles al zoom del mapa;
la navegación solicita otra imagen. No es un acceso gratuito garantizado: depende
de la configuración y facturación del proyecto Google. La clave de navegador
se entrega al cliente y no se escribe en datos ni historial.

## Persistencia y compatibilidad

- Fuente prioritaria de nuevas importaciones:
  `data/barranco/lotes/BARRANCO_LM_geogpsperu_SuyoPomalia.shp`, con sus archivos
  `.shx`, `.dbf`, `.prj` y demás acompañantes. Se conservan hashes de procedencia.
  Se admite el GeoJSON como respaldo cuando no existe SHP.
- Workspace por defecto: `data/barranco/editor/`, excluido de Git.
- Área mínima de nuevos lotes: 6 m², configurable mediante `--min-area` al crear
  un workspace; se conserva en sus revisiones posteriores.
- Al importar por primera vez se aplica una vez el offset existente y se registra
  en `source.applied_offset_m`. Reabrir no vuelve a aplicarlo.
- La detección automática encuentra componentes conectados de lotes que se
  intersectan (incluye contacto en un vértice), une sus polígonos y extrae sus
  exteriores para clasificar frentes. No extiende polígonos ni puentea calles
  mediante buffers. Los lotes aislados constituyen grupos de un solo lote.
- Para un workspace antiguo se rellenan las asignaciones faltantes en una nueva
  revisión, conservando geometrías corregidas y manzanas manuales. La detección
  no reimporta datos ni vuelve a aplicar el offset. Se puede desactivar el paso
  de inicio con `--no-auto-blocks`.
- El dataset actual produjo 310 grupos para 4926 lotes (109 grupos de un lote).
  Son propuestas topológicas corregibles: un contacto accidental puede conectar
  grupos que el usuario prefiera separar mediante «Asignar selección».
- `revisions/<uuid>.json`: instantáneas completas con lotes, manzanas, procedencia,
  segmentos de frente y operación. `current.json`: puntero publicado atómicamente.
- Las escrituras usan bloqueo de proceso local, fsync y reemplazo atómico. Cada
  previsualización está ligada a una revisión y expira al reiniciar el servidor.
- Deshacer genera una revisión nueva. Los IDs retirados permanecen registrados.
- `GET /api/lots/<id>/snapshot`: contrato compartido con la aplicación B.
  Incluye lote, revisión, CRS, `view_settings`, `view_settings_stale`, `cameras[]`
  con `camera_lonlat`, `camera_xy`, `pose`, `image_path` y `projection`
  (`angular-enu-v1`), más `missing_photo_ids`. Ejemplo: `lote-*.json` exportado
  desde el panel.
- `POST /api/lots/<id>/view-settings`: guarda fotos elegidas y altura de
  referencia (`height_role='cadastral_preview_only'`). Rechaza revisiones
  antiguas con 409 para no asociar vistas a otra geometría.
- `GET /api/cameras/<pid>?lot_id=&revision=`: describe una cámara en el marco
  del lote (para «Abrir cámara» y para la app B).
- `GET /api/photos/<pid>?lot_id=&revision=&clean=true`: imagen base en caché,
  independiente de la altura. Sin `clean`, devuelve base + prisma dibujado en
  servidor (usado solo para exportación; la UI dibuja la altura localmente).
- `GET /api/freshness/<id>/<geometry_revision>`: detecta resultados obsoletos.
- Fotos y proyecciones usan revisión explícita. Las cámaras y fuentes no se editan.
- Paquetes compartidos con B: `packages/barranco_data` (revisiones, lotes,
  manzanas, frentes, vistas) y `packages/barranco_imaging/angular.py`
  (convención ENU, `view_spec`, `project_image`, `project_points`).

Guardar/copiar el workspace completo conserva historia y correcciones. El motor
antiguo sigue leyendo el catastro original: la adopción de instantáneas corregidas
se realiza por el consumidor nuevo, sin sobreescribir los originales.

## Pruebas

```sh
python -m pytest apps/cadastral_editor/tests -q
```

Cobertura: corte/fusión, ascendencia, deshacer, conservación de área, rechazo de
fragmentos, manzanas, desplazamientos, solapamientos, frentes parciales, conflictos,
revisiones no publicadas, convención de cámara, caché de imagen base, vistas
compartidas y su invalidación por revisión, API e invalidación de instantáneas.

Prueba opcional de navegador con Playwright, contra un workspace demo nuevo:

```sh
python -m pip install playwright
python -m playwright install chromium
python apps/cadastral_editor/tests/browser_smoke.py --url http://127.0.0.1:8766
```

Ese recorrido confirma asignación, cancelación de movimiento, corte dibujado,
fusión, recarga, deshacer e historial. Requiere los IDs iniciales `demo-a/b/c`.

## Alcance actual

MVP con asignación automática/corrección manual de manzanas y traslación. Rotación
es una ampliación futura. Las candidatas fotográficas se ordenan por proximidad,
sin prometer visibilidad real; la galería permite inspeccionar todas las cercanas.
La altura del campo numérico se dibuja como overlay vectorial en el navegador:
no recarga fotos y es instantánea tras la primera carga. La imagen base por
foto+geometría se cachea en servidor; el prisma solo depende de la altura.
La aplicación no genera thetas ni mallas; expone el snapshot que consumirá B.
