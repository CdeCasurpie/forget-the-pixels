# Plan de Implementación V3: Entorno 3D Unificado (Estilo Desktop)

## 1. El Concepto: Un Solo Mundo 3D
En lugar de tener una pantalla dividida (mapa 2D a un lado y visor 3D al otro), la aplicación será un **Entorno 3D Unificado** interactivo.
Funcionará de manera idéntica a un software de escritorio 3D (como Blender, Rhino o Google Earth), donde el usuario puede alternar la cámara libremente:
- **Modo Vista Superior (Top-Down):** La cámara mira directamente hacia abajo (Pitch = 0°). Funciona como un mapa 2D clásico. Aquí ves los 14,000 lotes planos sobre el mapa base.
- **Modo Perspectiva 3D:** El usuario inclina la cámara (Pitch > 0°). Puede orbitar y ver la ciudad en tres dimensiones.

## 2. Stack Tecnológico para Entorno Unificado
- **Motor 3D Principal:** **`pydeck` (Deck.gl)**. Es un motor WebGL ultrarrápido controlado 100% desde Python. Es la herramienta perfecta porque:
  1. Dibuja los 14,000 polígonos sin esfuerzo.
  2. Tiene un **`ScenegraphLayer`** que permite inyectar modelos `.glb` en coordenadas exactas (latitud/longitud).
  3. Soporta la transición fluida de cámara 2D (top-down) a 3D (perspectiva).
- **Interfaz (GUI):** Se puede montar sobre **Dash** para tener paneles flotantes elegantes (al estilo de una UI de escritorio), o embeber en una ventana nativa de sistema operativo usando `PyQtWebEngine` / `webview` si se desea un `.exe` puro (aunque correrlo localmente en el navegador, como un entorno tipo Jupyter/Gradio, es lo más rápido de desarrollar).

## 3. Flujo de Usuario en el Visor Único

1. **Exploración (Modo 2D):**
   - El usuario abre la app y ve el mapa satelital de Barranco desde arriba.
   - Todos los lotes se muestran como huellas (polígonos planos translúcidos).

2. **Selección y Cámaras:**
   - El usuario hace clic en **un lote**.
   - El lote se ilumina. Automáticamente aparecen pequeños orbes o pines 3D alrededor representando las cámaras GSV.
   - Un **panel flotante** (Superpuesto en la esquina de la pantalla) muestra las fotos miniatura de esas cámaras para que el usuario confirme cuáles usar.

3. **Generación (Procedural al vuelo):**
   - El usuario pulsa "Generar".
   - El backend descarga fotos, estima la altura y ejecuta el algoritmo procedural.
   - *Magia Visual*: El polígono plano desaparece y, en su lugar exacto, **emerge el modelo 3D (.glb)** recién generado, posado exactamente sobre la superficie terrestre del mapa.

4. **Inspección (Modo 3D):**
   - El usuario arrastra el mouse con clic derecho para inclinar la cámara.
   - Ve el modelo 3D de la casa en su contexto geográfico real. 
   - Si genera un segundo lote al lado, ambos conviven en el mismo mundo 3D.

## 4. Arquitectura de Capas de PyDeck
El motor 3D manejará las siguientes capas simultáneas:
1. `BaseMap`: Mapa de calles o satélite.
2. `PolygonLayer`: Los 14,000 lotes catastrales (Z=0).
3. `ScatterplotLayer`: Puntos de cámaras GSV (Z=2m, altura del auto).
4. `ScenegraphLayer`: Los edificios `.glb` generados proceduralmente, posicionados, rotados y escalados para encajar perfectamente en los vértices del lote seleccionado.
