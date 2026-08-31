# 📐 Experimentos: Heurística de Wireframes

**Ubicación de los scripts:** `investigation/wireframe_heuristic/`

Este conjunto de experimentos se enfocó en un MVP (Minimum Viable Product) algorítmico para extraer **topología estructural (Wireframes)** de las fachadas, eludiendo la necesidad de usar costosos modelos de Deep Learning (como Co-PLNet o HAWP) para predecir las aristas.

## 1. El Problema de la Conectividad (Wireframe Parsing)
Las redes neuronales pesadas no solo intentan adivinar dónde están las esquinas (nodos) de un edificio, sino también qué esquina se conecta con cuál (topología). Esto consume mucha RAM de GPU y es difícil de entrenar.

## 2. La Solución Algorítmica (Fuerza Bruta + Heurística Determinista)
César propuso una aproximación algorítmica brillante aprovechando la baja complejidad de una fachada plana:
Dado que el número de esquinas o nodos ($V$) en una fachada es muy bajo (ej. las esquinas de una ventana o puerta), el número total de posibles conexiones es minúsculo: $\frac{|V|(|V|-1)}{2}$. ¡Podemos probarlas todas!

### El Pipeline del Algoritmo
1. **Predicción de Nodos (Mock):** El script `mock_coplnet.py` permite al usuario marcar manualmente los nodos estructurales en una imagen, simulando lo que haría una IA que solo predice puntos (nodos).
2. **Detección de Gradientes (Canny):** `edge_detector.py` aplica el filtro Canny para extraer los bordes físicos reales de la imagen.
3. **Generación Exhaustiva de Aristas:** `main.py` genera todas las líneas teóricas posibles conectando todos los nodos entre sí.
4. **Función de Costo (Intersección de Píxeles):** 
   - Se traza cada línea teórica con un grosor empírico ($T$).
   - Se realiza una intersección lógica (`bitwise AND`) con la imagen de bordes Canny.
   - El *Score* se define como la proporción de píxeles que caen exactamente sobre un borde físico detectado (Píxeles coincidentes / Longitud de la línea).
5. **Filtrado:** Si el score es mayor a un umbral $\gamma$ (e.g., 35%), la arista se clasifica como *verdadera* y forma parte del Wireframe estructural final.

## Conclusión
Este experimento demostró que, si logramos detectar correctamente los nodos o vértices clave de una fachada (usando un prior geométrico o IA ligera), podemos deducir matemáticamente la conectividad de la estructura (el Wireframe) usando los gradientes de la imagen y geometría pura, *sin requerir redes neuronales pesadas*.
