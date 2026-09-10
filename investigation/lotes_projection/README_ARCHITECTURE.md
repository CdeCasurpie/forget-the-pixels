# 🏙️ Arquitectura: Geo-Proyector de Lotes Generativo

Este documento describe la arquitectura oficial para el pipeline de **Reconstrucción Urbana Generativa**. El objetivo de este experimento es usar polígonos del Catastro (GIS) como "anclas espaciales" para extraer máscaras perfectas de edificios desde Google Street View, y posteriormente usar esas imágenes en IAs Generativas (Image-to-3D), resolviendo el problema de falta de escala y posicionamiento global de las IAs actuales.

---

## 1. Diseño del Sistema: "Director y Obrero" (Cliente-Servidor)
Para mantener la fluidez interactiva y evitar saturar recursos, el pipeline se divide rígidamente en dos fases:

### Fase 1: El Visualizador de Auditoría ("El Director" - Local en Laptop)
*   **Propósito:** Interfaz interactiva a 60 FPS para auditar que la matemática de proyección 3D a 2D sea perfecta.
*   **Tecnología:** Matemática de matrices (NumPy, PyProj) y **Rerun.io** (Visualizador nativo de tensores). *NO USA OPEN3D* para la interfaz 2D/3D dual para evitar sobrecarga del event-loop.
*   **Sin IA:** No se ejecutan redes neuronales aquí para mantener la laptop fría.
*   **Output:** Genera un archivo con las coordenadas 2D (Bounding Boxes) aprobadas.

### Fase 2: La Fábrica de Máscaras ("El Obrero" - Batch en Khipu)
*   **Propósito:** Recortar miles de imágenes masivamente usando inteligencia artificial.
*   **Tecnología:** SLURM Job, **MobileSAM / FastSAM** (inferencia ultrarrápida de 40MB).
*   **Modo Offline:** Para evadir la falta de internet en los nodos de cómputo de Khipu, los pesos del modelo (`.pth`/`.pt`) se descargan previamente desde el nodo de acceso (Login Node) y se cargan localmente.

---

## 2. Los 4 Módulos del Código (POO)

El código se divide en 4 pilares estrictamente modulares:

### A. GIS & Alineación (`CRSManager` & `GISLoader`)
*   **Problema resuelto:** El GPS crudo sufre de deriva y curvatura terrestre (jitter en Float32).
*   **Mecanismo:** Divide Lima en *Tiles* (cuadrículas) de 500x500m. Transforma coordenadas esféricas WGS84 a un plano Euclidiano Local **ENU (East-North-Up)** con cota cero localizada. Esto ancla firmemente las cámaras de COLMAP al catastro.

### B. Proyección Geométrica (`ZBufferProjector`)
*   **Mecanismo:** Cruza la nube de puntos con los polígonos del catastro para hallar la altura real del techo. Extruye el lote creando un "Prisma Fantasma 3D".
*   Aplica la ecuación $x = K[R|t]X$ para proyectar los vértices del prisma sobre el plano de imagen de la cámara.
*   Renderiza un mapa de profundidad matemático para obtener el Bounding Box exacto.

### C. Visión Computacional (`CVPipelineOrchestrator` - Khipu)
*   **Problema resuelto:** El Bounding Box recuadra el edificio, pero también incluye postes, árboles y cielo.
*   **Mecanismo de "Depth-Prompted SAM":**
    1. Prompt Positivo: El Bounding Box completo.
    2. Prompt Negativo (Puntos Rojos): Usa un mapa de profundidad para encontrar objetos "más cerca" que la pared del edificio (ej. autos, árboles) y los marca como negativos. Marca también las casas vecinas proyectadas.
    3. Resultado: MobileSAM extrae una máscara con precisión de píxel del edificio aislado.

### D. Visualización (`PipelineLogger`)
*   Singleton que envía logs secuenciales a `Rerun.io`. Permite usar un slider en la línea de tiempo para navegar cámara por cámara, viendo a la izquierda el mapa 3D y a la derecha la foto 2D con los Bounding Boxes dibujados encima, sin programar GUIs personalizadas.

---

## 3. Flujo de Trabajo (Step-by-Step)

1. **Preparación (Local):** Ejecutar el script base apuntando a la ruta descargada de Street View y el Shapefile del distrito.
2. **Auditoría (Local):** Abrir Rerun.io. Deslizar la línea de tiempo. Si los rectángulos verdes calzan sobre los edificios, exportar configuración.
3. **Despliegue (Local -> Khipu):** Subir carpeta a Khipu junto con el archivo de coordenadas.
4. **Procesamiento (Khipu):** Lanzar `sbatch job_masks.sh`. Khipu usará MobileSAM offline.
5. **Generación 3D (Futuro):** Las imágenes aisladas (fondo transparente) se envían a CRM/TripoSR para generar mallas hiper-realistas que reemplazarán los prismas simples.

---

## 4. Guía de Debugging y Solución de Problemas 🚨

Si algo falla durante el desarrollo o la ejecución, sigue esta guía:

### A. Los edificios "tiemblan" o flotan en el visor 3D (Jittering)
*   **Causa:** Se te olvidó aplicar el `CRSManager`. Estás usando coordenadas WGS84 o UTM globales directo en un motor gráfico de 32-bits.
*   **Solución:** Verifica que el centroide del *Tile* (500x500m) se esté restando a todas las coordenadas (cámaras y vértices) para forzar el origen $(0,0,0)$ local (Sistema ENU).

### B. El Bounding Box sale movido unos metros a la izquierda/derecha
*   **Causa:** Desfase clásico del catastro estatal vs el GPS de Google.
*   **Solución:** Usa los controles de Offset ($X, Y, Rotación$) en el `PipelineLogger` para micro-ajustar el Shapefile. Estos valores se guardan en `offset_config.json`.

### C. MobileSAM falla en Khipu por "Connection Timeout"
*   **Causa:** Khipu está intentando descargar los pesos de HuggingFace/PyTorch desde un nodo de cómputo sin salida a internet.
*   **Solución:** Entra al nodo de acceso de Khipu vía SSH. Escribe un script corto en Python que importe MobileSAM para forzar la descarga de los pesos en la caché (`~/.cache/torch/hub/checkpoints/`). Asegúrate de que tu script en Khipu apunte a esta ruta local.

### D. La máscara de SAM se está llevando el árbol de adelante
*   **Causa:** El Z-Buffer no está inyectando correctamente los *Puntos Negativos*.
*   **Solución:** Activa el flag de depuración visual `DEBUG_DEPTH=True`. Esto exportará una foto donde verás puntos rojos sobre el árbol. Ajusta el umbral de tolerancia de profundidad (ej. considerar "oclusión" a cualquier cosa que esté > 2 metros por delante del plano de la fachada).

### E. Rerun.io se pone súper lento o congela la laptop
*   **Causa:** Estás cargando toda la ciudad (cientos de miles de vértices y cientos de imágenes de alta resolución) en la misma línea de tiempo, saturando la RAM.
*   **Solución:** Llama a `flush_memory()` al cambiar de *Tile* o procesa rutas de máximo 50 panoramas por sesión de auditoría.
