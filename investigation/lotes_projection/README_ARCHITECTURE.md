# [AI_CONTEXT] Memoria Estática del Agente: Geo-Proyector Generativo
**ATENCIÓN AGENTE (ANTIGRAVITY / LLM):** Si estás leyendo esto, tu contexto anterior probablemente se truncó. Este documento contiene la arquitectura estricta y los contratos de datos para construir el "Geo-Proyector Generativo". NO te desvíes de estas reglas.

## 1. Meta Global del Sistema
Cruzar datos espaciales 2D (Catastro/Shapefiles) con poses de cámaras 3D (COLMAP/Street View) para proyectar el polígono de cada edificio sobre la foto 2D. Esta proyección genera un Bounding Box matemático que se usa como Prompt Positivo para recortar la imagen (offline usando MobileSAM en Khipu). El objetivo es alimentar a modelos Image-to-3D con imágenes aisladas de edificios para re-escalar las mallas generadas devuelta a su coordenada GPS.

## 2. Arquitectura de Fases (Contrato)
*   **Fase 1 (Local / Laptop):** Director matemático. Código en Python que carga datos, convierte a ENU local, extruye lotes y proyecta a 2D. Se valida el resultado usando Rerun.io (0 IAs pesadas aquí).
*   **Fase 2 (Batch / Khipu):** El archivo `crops_metadata.json` (output de la Fase 1) se procesa en el clúster con MobileSAM (offline mode, pesos `.pth` en caché) inyectando los Z-Buffers vecinos como prompts negativos (evita llevarse el cielo/árboles).

## 3. Estructura de Módulos (Código)
El código debe ir en `investigation/lotes_projection/` y respetar esta estructura POO estricta:

### `models.py`
*   `Camera`: Atributos: `camera_id`, `pose (4x4 matrix en local ENU)`, `K (3x3 matriz intrínseca)`, `image_path`, `is_360 (bool)`.
*   `CadastralLot`: Atributos: `lot_id`, `polygon_2d (Shapely)`, `z_min (float)`, `z_max (float)`. Método `get_3d_bounding_box() -> np.ndarray (8x3)`.

### `loaders.py`
*   `CRSManager`: Convierte `ECEF (EPSG:4978)` de COLMAP y `UTM (EPSG:32718)` del Catastro a un sistema Euclidiano Local **ENU (East-North-Up)** restando el centroide del Tile (evita Jittering de float32).
*   `DataLoader`: Lee `cameras.bin/images.bin/points3D.bin` (pycolmap) y cruza con `gpd.read_file(shp)`. Aplica `offset_config.json` al Shapefile (Translación X,Y y Rotación).

### `projection.py`
*   `ZBufferProjector`: Implementa $x = K[R|t]X$. Entra un `CadastralLot` y una `Camera`. Retorna `[xmin, ymin, xmax, ymax]` y `is_visible (bool)` calculando que el lote esté por delante del plano de la cámara (depth > 0).

### `visualizer.py` (usando Rerun.io)
*   `PipelineLogger`: Wrapper alrededor de `import rerun as rr`. Registra `rr.log("world/camera", rr.Pinhole(...))`, `rr.log("world/lots", rr.Boxes3D(...))`. NO usar Open3D para UI compleja.

## 4. Guía de Manejo de Errores (Troubleshooting Interno)
1.  **Jittering/Vibración 3D:** El `CRSManager` falló. Revisa si olvidaste restar el `centro_local` a la cámara o al lote.
2.  **Lotes Desfasados del COLMAP:** El catastro de Lima tiene error de GPS. Modifica `offset_config.json` para hacer micro-ajuste, NO alteres la cámara.
3.  **Oclusiones en SAM:** Si SAM recorta el árbol, el `ZBufferProjector` debe generar puntos de sampleo en los píxeles con $Z_{real} < Z_{edificio}$ y pasarlos a la Fase 2 como `negative_prompts`.
4.  **Error Offline SAM en Khipu:** Instancia el modelo con rutas estáticas: `MobileSAM(checkpoint="./weights/mobile_sam.pt")`.

*(Fin del Contexto Estático)*
