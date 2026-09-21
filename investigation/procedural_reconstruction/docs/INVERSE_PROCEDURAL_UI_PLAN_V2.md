# Plan de Implementación V2: Plataforma de Modelado Procedural Inverso

Este plan ha sido refinado tras una rigurosa auditoría arquitectónica (UX, GIS y Pipeline) para garantizar rendimiento, escalabilidad y una experiencia de usuario en tiempo real al manejar grandes volúmenes catastrales (14,000 lotes en Barranco).

## 1. Stack Tecnológico Definitivo
- **Frontend / Servidor**: **Dash** (con soporte para Background Callbacks vía `DiskcacheManager`).
- **Mapa Interactivo**: **`dash-leaflet`** (Crucial para superar el cuello de botella de Plotly. Maneja miles de polígonos fluidamente vía WebGL/Canvas y responde en <16ms).
- **Visor 3D**: Componente HTML web nativo **`<model-viewer>`** inyectado directamente en Dash, permitiendo sombreado PBR, texturas y navegación suave delegada a la GPU del navegador del cliente.
- **Lógica Espacial Backend**: `geopandas.sindex` para consultas ultra-rápidas por bounding box (LOD espacial dinámico).

## 2. Flujo de Experiencia de Usuario (Studio Layout)

La interfaz usará un diseño asimétrico de "Pantalla Dividida" (Split-Screen).

### Panel Izquierdo (55%): Explorador Espacial y Selección
1. **Mapa de Alto Rendimiento (Fase A)**:
   - Capa Base: Mapa satelital o vectorial (Mapbox/Carto).
   - Capa Lotes: Se cargan los lotes con `dash-leaflet`.
   - Capa Lote Activo: Al hacer clic, una capa separada resalta el lote sin recargar el resto del distrito (Cero *flickering*).
2. **Selección de Cámaras y Previsualización (Fase B)**:
   - Al seleccionar un lote, se consulta el índice espacial (`sindex`) para ubicar las cámaras de Street View a <30m.
   - Las cámaras se muestran como *pines interactivos* en el mapa.
   - En un panel lateral se despliegan **Miniaturas (Previews)** de las fotos de las cámaras candidatas. El usuario puede desmarcarlas visualmente si hay árboles tapando la casa, ignorando cualquier restricción algorítmica.

### Panel Derecho (45%): Pipeline y Síntesis 3D interactiva
1. **Pipeline de Percepción (Fase C - Asíncrona)**:
   - Al presionar **"Procesar Lote"**, se detona un *Background Callback* (proceso secundario) para no congelar la pestaña web.
   - Una consola de progreso avanza: `[1/4] Descargando panoramas -> [2/4] Recortando -> [3/4] Estimando altura -> [4/4] Sintetizando...`
2. **Estrategia "Optimistic UI" y Caché (Resolución de Cuello de Botella)**:
   - La descarga desde GSV es lo más lento (8-25s). Se implementará caché en disco para panoramas ya descargados.
   - Mientras se descarga y analiza, el sistema genera inmediatamente un **volumen preliminar rápido (LOD 0)** en base al polígono catastral para que el usuario no espere frente a una pantalla vacía.
3. **Visor 3D y Ajuste Fino (Fase D)**:
   - Al finalizar, el `<model-viewer>` carga el `.glb` final.
   - Aparece un panel de "Ajuste Interactivo" (*Human-in-the-Loop*) donde el usuario puede corregir las predicciones de la red neuronal (ej. "Son 3 pisos, no 4" o "Cambiar cerco"). Un botón "Re-generar" aplicará los cambios reconstruyendo la malla en <100ms, sin volver a descargar las fotos.

## 3. Arquitectura del Código y Adaptadores V4

Se corregirá la brecha técnica identificada en el sistema de tipado entre la interfaz y el motor procedural:
- En lugar del obsoleto `propose_building` (V3), el pipeline utilizará un adaptador estructurado: `build_specification_v4(parcel_poly, mock_ai_params) -> BuildingSpecificationV4`.
- Las observaciones de la red (simuladas por ahora) se encapsularán en un DTO limpio (`PerceptionResult`), alimentando al `BuildingProgram` y al `SitePlan`.

### Módulos a Conectar:
- **`spatial`**: Índices espaciales (`sindex`) y proyecciones cartográficas.
- **`vision.acquisition`**: Módulo GSV (integrado a sistema de caché de disco).
- **`vision.projection` & `vision.estimation`**: Reproyección e inferencia de altura (manteniendo la heurística de techo/cielo rápida para CPU).
- **`modeling`**: Generador de mallas V4 y exportador a GLB.
