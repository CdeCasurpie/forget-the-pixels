# Heurística de Extracción Estructural (Proxy de Wireframe Parsing)

Este experimento es un Minimum Viable Product (MVP) algorítmico diseñado para sustituir temporalmente la detección de conectividad de modelos de Deep Learning pesados como **Co-PLNet** o **HAWP**. 

## El Problema
Los modelos de *Wireframe Parsing* requieren altos recursos computacionales para inferir no solo esquinas, sino también qué esquinas se conectan formando la topología.

## La Solución Propuesta
Aprovechando que el número de nodos estructurales en una fachada $V$ es muy bajo, el grafo completo de posibles aristas es minúsculo: $\frac{|V|(|V|-1)}{2}$. Por tanto, es viable computacionalmente trazar todas las aristas posibles y aplicar un algoritmo determinista para filtrar cuáles son topológicamente correctas.

### Algoritmo
1. **Mock de Nodos:** Al no disponer de Co-PLNet en local, se utiliza una interfaz de `cv2` para colocar manualmente las predicciones de los nodos.
2. **Detección de Bordes (Canny):** Se extrae un mapa de gradientes usando Canny.
3. **Fuerza Bruta de Aristas:** Se genera el conjunto de todas las combinaciones de líneas entre nodos.
4. **Cálculo de Score (Intersección Espacial):** Por cada línea teórica, se dibuja temporalmente con un grosor de $T$ píxeles y se intersecta lógicamente (`bitwise AND`) con Canny. 
   La función de costo es:
   $$ \text{Score} = \frac{\text{Píxeles Coincidentes con Canny}}{\text{Longitud de la Línea}} $$
5. **Filtrado:** Si el score supera un umbral empírico $\gamma$ (ej. 35%), se acepta la arista.

## Ejecución
Requiere un entorno Python con OpenCV y Numpy:
```bash
python main.py
```
