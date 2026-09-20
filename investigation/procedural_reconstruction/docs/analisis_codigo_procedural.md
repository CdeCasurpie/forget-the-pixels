# Análisis de la Arquitectura de Modelado Procedural

Este documento detalla cómo está estructurado el código de modelado procedural (`layout.py`, `grammar.py`, `mesh_builder.py`, etc.) para comprender las mecánicas y planificar futuras inyecciones de elementos realistas propios de la arquitectura de la zona (ej. ladrillo desnudo, calaminas, tanques y fierros expuestos).

---

## 1. Identificación de Fachadas vs Laterales/Traseros

**Mecanismo actual:**
La identificación ocurre en `layout.py` (aprox. líneas 97-105). El algoritmo recorre cada segmento perimetral de la huella del edificio y calcula su vector normal (`n`). Luego, compara este vector mediante un producto punto contra la normal de los bordes frontales explícitamente designados (`front_edges` o `sn`). Si las normales son casi idénticas (`np.dot(n, sn) > 0.98`) y el segmento se encuentra geográficamente cerca de la línea frontal del lote (`close_to_front`), el segmento se clasifica marcando la variable `front = True`.
Esta clasificación se almacena permanentemente en el objeto `FacadeSpecification` bajo el atributo booleano `is_front`.

**Asignación de materiales diferenciados:**
Sí, es completamente posible con la estructura actual. El modelo de datos de `FacadeSpecification` recibe una propiedad `wall_material` (que hoy tiene como predeterminado `"plaster"`). Bastaría con modificar el constructor en `layout.py` para introducir una condicional:
```python
wall_material="plaster" if front else "brick" # (asumiendo que "brick" exista en los materiales de textura)
```
Dado que en `grammar.py` el renderizado geométrico toma la propiedad `f.wall_material`, los muros laterales pasarían a usar la textura de ladrillo expuesto de forma nativa sin alterar la lógica geométrica.

---

## 2. Construcción Vertical de Pisos y Losas

**Mecanismo actual:**
La geometría no se genera piso por piso como prismas independientes, sino por "bandas" paramétricas sobre toda la pared de la fachada. En `grammar.py` (función `facade()`, líneas 418-447), el motor compila una lista ordenada de todas las divisiones de alturas en Z (`zs`) donde algo cambia de estado (la base 0.0, la altura del techo, y las cotas de inicio/fin de todas las ventanas y puertas).
Luego itera construyendo rectángulos (`mb.box(...)`) para rellenar los espacios macizos de la pared donde no existan colisiones con los vanos de las aberturas.

**Inyección teórica de la losa de concreto (20cm) en los laterales:**
Las elevaciones reales de cada piso habitado están guardadas en el array `f.floor_levels_m`. Actualmente, la lógica decorativa (`f.ornamented`) aprovecha esto en la fachada principal para proyectar una banda de acento.
Para aplicar la banda de losa visible a los laterales, la intervención ideal sería agregar este bloque en `grammar.py` (función `facade`):
```python
if not f.is_front:
    for z in f.floor_levels_m[1:]:
        # Extruir una delgada banda de 20cm de altura ("concrete") que sobresalga ligeramente (-0.01m)
        # para interrumpir o reemplazar visualmente el ladrillo desnudo subyacente.
        mb.box(a, t, n, 0, length, z - 0.20, z, -0.21, 0.01, "concrete", "slab_band")
```

---

## 3. Generación de Techos y Azoteas

**Mecanismo actual:**
La generación topológica sucede enteramente en `grammar.py`, dentro de la función `roof_details()` (líneas 537-647).
Allí se crea primeramente la losa principal (`roof_slab`), junto con parapetos o muretes perimetrales usando el polígono base recortado.

* Si el techo es plano, busca por "fuerza bruta" una pequeña zona ortogonal totalmente libre de colisiones e interna (un *platform*) donde ubicar de forma segura los cuartos de azotea (`terrace_room`), aleros de calamina (`canopy`), y tanques de agua (`water_tank`).
* Si el techo es a dos aguas o inclinado (`shed`, `gable`), reemplaza la plataforma por extrusiones apoyadas en una función paramétrica o campo de alturas inclinado que respeta la forma del lote.

**Enganche de elementos de realismo:**
* **Calaminas y Tanques:** El código ya cuenta con *placeholders* procedurales bajo las condicionales `if roof.canopy:` e `if roof.water_tank:`. Es en estas líneas exactas (aprox. 625 y 640 de `grammar.py`) donde se sustituiría la actual geometría primitiva `mb.solid("corrugation")` por una llamada a los objetos pre-fabricados (ej. `build_prefab(..., "calamina_peruana")`) utilizando como origen geométrico el `platform` (coordenadas x0, y0, x1, y1 calculadas).
* **Fierros expuestos:** Actualmente no existen en el código. Para incorporarlos, se agregaría una iteración al final de `roof_details()` que localice las esquinas del polígono (`poly.exterior.coords`) de los vértices y emita cilindros delgados (`mb.beam()`) de acero emergiendo 1 a 2 metros verticalmente sobre el nivel del parapeto (`h + roof.parapet_height_m`).

---

## 4. Gestión del Retiro (Setback) y Límite de Lote

**Mecanismo actual:**
El manejo está elegantemente dividido en dos pasos cronológicos:

1. **Retracción de la masa habitable (en `layout.py`):** 
   El edificio nace partiendo del límite estricto de propiedad (`parcel`). Luego de aplicarle un pequeño margen (-0.20m) por seguridad de cálculo, el motor traza líneas imaginarias asociadas a las veredas frontales. Sobre estas calles, realiza una operación Booleana espacial (`footprint.difference`) restando un colchón equivalente al tamaño exacto de `setback_m`. Como resultado, la masa habitable colapsa o retrocede, dejando espacio vacío delante sin modificar el polígono de propiedad original.
2. **Uso del espacio vacío y Cercos (en `grammar.py`):**
   Dentro de la función `boundary_and_garden()` (línea 649), el generador procedural traza el muro perimetral ciego y la reja (`boundary_wall`, `gate`) usando directamente las coordenadas originales intocadas del límite del lote (`mb.parcel.exterior.coords`).
   El vacío resultante entre este cerco y la nueva cara frontal del edificio (`garden = mb.parcel.difference(poly).buffer(...)`) se procesa espacialmente para plantar arbustos y maceteros, pero reserva con estricta prioridad pasillos libres o corredores ("pedestrian approach corridors") para que la vegetación procedural no obstruya el ingreso a las puertas de la vivienda.
