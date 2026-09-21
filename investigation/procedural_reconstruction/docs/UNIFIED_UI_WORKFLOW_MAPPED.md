# Flujo de Trabajo Unificado: Mapeo Exacto de Módulos (V4)

Este documento detalla el flujo de la aplicación 3D y mapea cada acción de la interfaz de usuario con su correspondiente función en el directorio `src/`.

## 1. Precarga del Mundo 3D
**UI:** Se renderiza el mapa 3D (pydeck). Se cargan los lotes y todas las cámaras pre-descargadas o pre-indexadas (con su ID, posición, norte).
**Módulo a usar:**
- Carga de lotes: `geopandas.read_file("Lotes_Barranco.shp")` + transformación a EPSG:4326.
- Carga de metadatos de cámaras: `vision.acquisition.acquisition.load_route` o leyendo el `manifest.jsonl` generado.

## 2. Interacción: Selección de Lote
**UI:** El usuario presiona un lote en el mapa.
**Acciones de Backend:**
- Se calculan las aristas frontales (Fronts) y se devuelven al UI para que se resalten en color verde sobre el polígono 3D.
  *Módulo a usar:* `spatial.street_fronts.annotate_street_fronts` o `street_facing_edges`.
- Se calcula qué cámaras ven directamente esos fronts (con su raycast y validación de obstáculos).
  *Módulo a usar:* `vision.cameras.select_cameras`.
- Se verifica en disco si el archivo JPG de esa cámara ya existe (`os.path.exists`).
**Feedback UI:** El mapa resalta el lote, dibuja los "Fronts" en verde, enciende los marcadores de las cámaras seleccionadas y muestra un panel lateral con sus IDs y estado (Descargada / Pendiente).

## 3. Confirmación y Descarga
**UI:** El usuario presiona "Confirmar y Procesar".
**Acciones de Backend:**
- Se descargan las fotos faltantes (con streaming de progreso enviado al UI).
  *Módulo a usar:* `vision.acquisition.acquisition.download` (o invocando el API de streetlevel individualmente).
- Se ejecuta la estimación de altura sobre la vista de la fachada.
  *Módulo a usar:* `vision.estimation.height.fit_height`.

## 4. Proyección y Percepción (Red Neuronal Simulada)
**Acciones de Backend:**
- Se extrae una franja (proyección cilíndrica) de la fachada usando la huella catastral proyectada sobre el panorama.
  *Módulo a usar:* `vision.projection.cylindrical.extract_full_vertical_strip`.
- Se pasa la franja proyectada a la función que extrae las *features* (Por el momento será una función *mock* `mock_extract_features(image_strip)` que retorna parámetros aleatorios estilo V4 (uso, acabados, cercos) basados en la altura y el ancho del lote).

## 5. Generación Procedural y Posicionamiento 3D
**Acciones de Backend:**
- Con las features extraídas, se instancia un `BuildingProgram` y se define el `BuildingSpecificationV4`.
- Se invoca al motor procedural para generar la malla 3D.
  *Módulos a usar:* `modeling.grammar.generate_v4_mesh` y `modeling.exporters.glb_exporter.export_glb`.
**Feedback UI:** El archivo `.glb` recién exportado se envía al visor 3D (vía `ScenegraphLayer` en `pydeck`) y aparece físicamente plantado encima de su huella catastral en el mapa interactivo.
