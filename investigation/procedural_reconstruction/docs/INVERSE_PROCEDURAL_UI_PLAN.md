# Plan de Implementación: Interfaz Interactiva de Modelado Procedural Inverso

## Objetivo
Crear una aplicación web interactiva (UI) que permita visualizar el catastro de Barranco, seleccionar un lote, confirmar/editar las cámaras de Street View asociadas, descargar las imágenes, estimar la altura, extraer características (simuladas por ahora) y generar el modelo 3D procedural (GLB) para visualizarlo directamente en la misma interfaz.

## 1. Stack Tecnológico Propuesto
- **Frontend / Backend UI**: **Dash (Plotly)**. Se recomienda Dash sobre Gradio porque Dash ofrece callbacks interactivos nativos sobre mapas de Plotly (Mapbox), permitiendo hacer clic en polígonos (lotes) y puntos (cámaras) bidireccionalmente.
- **Visor 3D**: Componente `dash_vtk` o un `iframe` simple con `<model-viewer>` de Google para renderizar el GLB resultante.
- **Geometría y Datos**: `geopandas` y `shapely` para el manejo de `Lotes_Barranco.shp`.

## 2. Fases de la Interfaz (User Journey)

### Fase A: Exploración Espacial (El Mapa)
- Se carga el Shapefile de Barranco (`Lotes_Barranco.shp`) y se convierte a WGS84 (EPSG:4326) para mostrarlo en un `dcc.Graph` tipo `scattermapbox` o `choroplethmapbox`.
- Se carga la base de metadatos de cámaras de Street View (si existe un índice global) o se hace una consulta de cercanía.
- **Interacción**: El usuario hace clic en un polígono (lote).

### Fase B: Selección de Cámaras
- Al seleccionar el lote, el backend calcula el centroide y busca las cámaras en un radio de ~30m.
- El mapa se actualiza destacando el lote seleccionado y mostrando los puntos de las cámaras candidatas.
- **Interacción**: Un panel lateral muestra la lista de cámaras (con checkboxes). El usuario puede marcar/desmarcar cámaras saltándose las heurísticas estrictas. Al confirmar, presiona "Procesar Lote".

### Fase C: Pipeline de Percepción (Mock) y Generación
Al presionar "Procesar", se ejecuta una cadena asíncrona (con barras de progreso en la UI):
1. **Adquisición**: `vision.acquisition.gsv` descarga los panoramas de las cámaras seleccionadas.
2. **Proyección**: `vision.projection` genera los recortes rectilíneos o cilíndricos apuntando al lote.
3. **Visión / Estimación**: Se llama a `vision.estimation.height.fit_height` (asumiendo que las máscaras del cielo se calculan al vuelo o se simulan por ahora).
4. **Mock de Red Neuronal (Inverse Modeling)**: Se invoca una función temporal `mock_predict_architecture(images)` que retorna parámetros aleatorios pero geométricamente válidos (ej. pisos basados en la altura estimada, color, tipo de cerco).
5. **Síntesis Procedural**: 
   - `modeling.layout.propose_building(..., **mock_params)`
   - `modeling.grammar.generate_v4_mesh()`
   - `modeling.exporters.export_glb()`

### Fase D: Visualización 3D
- Una vez exportado el GLB temporal, la UI actualiza un componente visor 3D (ej. `<model-viewer src="assets/temp.glb">` incrustado) para que el usuario pueda rotar e inspeccionar la casa generada.

## 3. Integración con Módulos Existentes
- **`spatial`**: Para transformaciones EPSG y distancias.
- **`vision.acquisition`**: Reutilizar clientes GSV.
- **`vision.projection`**: Reutilizar `PanoramaCamera` para reproyectar hacia el centroide del lote.
- **`modeling`**: La API refactorizada (`propose_building`, `generate_v4_mesh`, `export_glb`) se usará de forma directa.
