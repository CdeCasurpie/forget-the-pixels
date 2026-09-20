# PLAN ARQUITECTÓNICO: Realismo Peruano (Procedural)

Basado en el análisis de las imágenes de referencia y la estructura del código procedimental, el siguiente plan detalla las estrategias exactas de implementación para inyectar características de la arquitectura peruana informal/formal en el generador 3D.

## A. Diferenciación de Materiales
**Objetivo:** Mostrar tarrajeo y pintura en la fachada principal y dejar ladrillo expuesto ("pandereta" o "king kong") en los muros laterales y traseros.
**Estrategias de Implementación:**
*   **Archivo a modificar:** `layout.py`
*   **Dónde:** En la lógica de construcción de los segmentos del muro (aprox. líneas 97-105) y la instanciación de `FacadeSpecification`.
*   **Cómo:** 
    *   Actualmente el código determina si un muro es frontal verificando su vector normal frente a la calle (`is_front = True`).
    *   Se debe interceptar el atributo `wall_material` durante la creación del muro. Se utilizará una condicional para asignar `"plaster"` si el muro es `front`, y `"brick"` si es un muro lateral o trasero.
    *   Asegurarse de que el motor de renderizado soporte la textura de ladrillo asignada.

## B. Losa de Concreto y Columnas Expuestas
**Objetivo:** Exponer la estructura aporticada o confinada (concreto gris) marcando líneas horizontales (losas) y verticales (columnas) sobre los lienzos de ladrillo en las colindancias.
**Estrategias de Implementación:**
*   **Archivo a modificar:** `grammar.py`
*   **Dónde:** Dentro de la función `facade()` que genera la malla de las paredes por bandas.
*   **Cómo (Losas Horizontales):**
    *   Añadir un bloque `if not f.is_front:` para aislar los laterales.
    *   Iterar sobre `f.floor_levels_m` (que contiene las alturas de cada piso).
    *   Para cada nivel, inyectar un rectángulo/banda (`mb.box()`) de unos 20 cm de altura (`z - 0.20` a `z`), asignándole el material `"concrete"`. Proyectar esta banda ligeramente hacia afuera del muro de ladrillo (ej. `depth = -0.01m`) para que reemplace visualmente el ladrillo.
*   **Cómo (Columnas Verticales):**
    *   En las aristas o esquinas del polígono perimetral, proyectar pilares verticales de material `"concrete"`, cruzando la pared desde la base hasta la cima, para formar la retícula estructural.

## C. Ecosistema de Azotea
**Objetivo:** Simular las azoteas habitadas y en evolución con tanques de agua, calaminas y fierros oxidados sobresalientes ("esperas").
**Estrategias de Implementación:**
*   **Archivo a modificar:** `grammar.py`
*   **Dónde:** Dentro de la función `roof_details()` (aprox. líneas 537-647).
*   **Cómo (Fierros "Esperas"):**
    *   Al final de `roof_details()`, iterar por las coordenadas de los vértices de la losa (`poly.exterior.coords`).
    *   Emitir cilindros delgados (`mb.beam()`) de material de metal oxidado, emergiendo verticalmente 1.0 a 1.5 metros por encima de los parapetos existentes (`roof.parapet_height_m`).
*   **Cómo (Calaminas y Tanques):**
    *   En los condicionales `if roof.canopy:` e `if roof.water_tank:`, sustituir la creación actual de sólidos simples (como `mb.solid("corrugation")`) por la instanciación de "prefabs" hiper-detallados.
    *   El tanque debe pasar a ser un objeto modelado que incluya anillos, base de concreto y material de plástico oscuro. La calamina debe ser una cubierta corrugada sobre una estructura ligera en las coordenadas `platform` precalculadas.

## D. Lógica de Desgaste e Imperfecciones
**Objetivo:** Romper con la perfección procedural, añadiendo asimetría y desgaste propio de la autoconstrucción.
**Estrategias de Implementación:**
*   **Archivo a modificar:** `layout.py` y `grammar.py`
*   **Cómo (Imperfecciones Geométricas):**
    *   En `layout.py`, en las secciones encargadas del posicionamiento de ventanas y aberturas, aplicar una función de "ruido aleatorio" (jitter) a las coordenadas horizontales. Desplazamientos sutiles (ej. ± 0.05 a 0.15 metros) evitarán que las ventanas entre diferentes pisos estén alineadas con precisión milimétrica.
*   **Cómo (Desgaste Textural):**
    *   En `grammar.py` (`facade()` y `boundary_and_garden()`), se implementará la superposición de geometría muy delgada (decals) en las zonas bajas de los muros (z < 1.0m) para mapear texturas con manchas de salitre o humedad.
    *   Para los cercos ciegos y frontales, añadir variabilidad en la tonalidad de la pintura asignando un mapa de suciedad en las colisiones o uniones con el suelo.
