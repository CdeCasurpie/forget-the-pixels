# TEXTURE_REALISM_PLAN

## Simulación de Debate Técnico

### Ronda 1: Propuestas Iniciales
**Technical Artist (Especialista PBR/GLTF):** 
El 'tiling' de manchas oscuras es un problema clásico al exportar a GLB estándar. Para solucionarlo propongo tres opciones:
1. Limpiar el mapa albedo actual (quitar contrastes altos en Photoshop/GIMP usando filtros) para que el tile sea imperceptible.
2. Vertex Colors para añadir suciedad macro. Rompería la repetición, pero requeriría subdividir las mallas de los muros.
3. Decals: Añadir mallas superpuestas (quads) con texturas de humedad/suciedad con canal alpha.

**Ingeniero de Geometría Procedural:** 
Desde Python/Trimesh evalúo:
- Limpiar texturas es un trabajo offline, no afecta el código.
- Subdividir mallas (Vertex Colors) en `mesh_builder.py` pasaría muros de 1 quad a cientos, arruinando la optimización, y mapear pintura por vértice en Python es complejo.
- Decals: Es muy viable. Podemos generar quads procedimentales con la misma orientación del muro, aplicando un offset mínimo para evitar colisiones.

**Director de Arte:** 
Para capturar la estética del "desgaste peruano" (humedad evidente en el zócalo por el clima, escurrimientos bajo las ventanas), la opción de Decals es la mejor. Nos da control para que la humedad nazca desde el piso y la suciedad caiga de las ventanas de forma realista.

### Ronda 2: Refinamiento y Críticas
**Technical Artist:** 
Si usamos Decals, crítico al ingeniero: deben tener un offset muy preciso (unos 2mm) en la dirección de la normal del muro para evitar z-fighting en el visor GLB. Además, el `glb_exporter.py` deberá soportar un material con `alphaMode: 'BLEND'` o `MASK`.
**Ingeniero de Geometría Procedural:** 
Aceptado. En `mesh_builder.py` podemos automatizar esto: detectamos el eje Z mínimo de la cara del muro para el zócalo, y el bounding box inferior de los huecos (ventanas) para spawnear los decals. 
**Director de Arte:** 
Para evitar que los decals también hagan tiling, asegúrense de estirar el decal a lo largo del muro o usar coordenadas UV que no se repitan para cada pared.

### Ronda 3: Pulido Final
**Technical Artist:** 
Acordado. Combinaremos la opción 1 (limpiar el mapa base) con la opción 3 (Decals procedimentales).
**Ingeniero de Geometría Procedural:** 
El código exportará el muro y los decals como nodos/primitivas separadas dentro del mismo GLB para facilitar la asignación de materiales.

---

## Plan de Acción (Modificaciones al Código Python)

1. **Pre-procesamiento (Offline / Assets)**
   - Editar la textura del muro actual para homogeneizarla y eliminar manchas oscuras repetitivas.
   - Añadir texturas en PNG con transparencia para `decal_humedad.png` y `decal_suciedad.png`.

2. **Modificación en `mesh_builder.py` / `v4_grammar.py`**
   - **Humedad en Zócalo:** Para cada muro vertical exterior, generar una malla (quad) que mida el ancho del muro y 0.6m a 1.0m de alto desde la base. Asignarle el material decal. Aplicar un desplazamiento (offset) de `0.002` unidades a lo largo de la normal de la cara.
   - **Escurrimientos:** Al generar ventanas, generar un quad de igual ancho que la ventana, posicionado justo debajo del alféizar, hacia abajo. Offset de `0.002`.

3. **Modificación en `glb_exporter.py`**
   - Añadir soporte para materiales con transparencia (Alpha). Al definir el material del decal en el JSON del glTF, incluir la propiedad `"alphaMode": "BLEND"` o `"MASK"`.
