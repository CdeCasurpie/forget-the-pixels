# PERUVIAN REALISM PLAN V2: Debate y Arquitectura Procedural

A continuación se presenta la transcripción completa del debate técnico de 5 rondas y el Plan Arquitectónico V2, simulando a los tres expertos solicitados.

---

## Participantes del Comité de Arquitectura Procedural
1. **Arquitecto Especialista en Autoconstrucción (AA):** Experto en la lógica estructural informal, pórticos de concreto y consolidación progresiva (ladrillo pandereta).
2. **Ingeniero de Geometría Procedural (IGP):** Experto en Python, `Shapely`, `Trimesh`, operaciones booleanas y topología de mallas 3D.
3. **Director de Arte PBR (DAP):** Especialista en mapeo UV métrico, decals, PBR shaders (Roughness/Normal) y blending de materiales.

---

### Ronda 1: Lluvia de Ideas y Lógica Real

**AA:** La autoconstrucción peruana no es aleatoria; obedece a una lógica de "crecimiento progresivo". Los muros laterales suelen ser medianeros, pegados al lindero, sin tarrajear (ladrillo pandereta expuesto) por ahorro y falta de acceso. Las fachadas principales sí se tarrajean y pintan (a veces a medias). Las vigas y columnas de concreto (los pórticos) suelen estar a ras del muro o sobresalir unos centímetros. Y vital: las ventanas son asimétricas porque la distribución interna manda; a menudo un baño o escalera rompe la grilla de la fachada.

**IGP:** Traduciendo esto a nuestro script en Python: actualmente generamos la malla extruyendo "bandas horizontales" (pisos). Para modelar las columnas y vigas visibles, ya no podemos solo extruir la huella 2D (`Shapely.Polygon`). Necesitamos segmentar los bordes de la huella, instanciar "nodos" en las intersecciones (columnas de 0.25x0.25m) y conectar esos nodos con cajas booleanas (vigas). Las ventanas asimétricas requieren una distribución estocástica basada en partición espacial de la fachada.

**DAP:** Si vamos a separar vigas, columnas y muros, necesitamos IDs de material independientes (`material_index` en la malla). El problema del ladrillo pandereta es la escala. Si aplicamos un `triplanar mapping` global, perderemos las juntas de mortero alineadas. Necesitamos mapeo UV métrico: que 1 unidad UV corresponda a 1 metro real en el espacio del mundo. Además, las manchas de humedad en los techos planos y la base de los muros requieren *vertex colors* o una máscara procedural de AO (Ambient Occlusion) precalculada.

### Ronda 2: Crítica de Factibilidad Geométrica

**IGP:** Destruyendo un poco tu idea, DAP: si usamos operaciones booleanas en `Trimesh` (`trimesh.boolean.difference`) para perforar ventanas o insertar columnas, la topología resultante suele ser terrible (triángulos delgados, *non-manifold edges*), lo que arruinará tus UVs. Propongo un enfoque constructivo modular: no perforar. Construimos muros mediante polígonos 2D de `Shapely`, aplicamos recortes booleanos 2D (más robustos) para los huecos de ventanas, y extruimos eso en 3D. Las columnas y vigas son paralelepípedos simples generados e insertados en el `scene graph`.

**AA:** Eso me gusta, es literalmente como se construye en la realidad: primero las columnas (paradas), luego asientan el ladrillo (muro), y luego vacían la viga (solera). Sin embargo, recuerda que en los laterales los muros van al límite de propiedad, a veces las columnas están *rehundidas* o expuestas solo por un lado. 

**IGP:** Exacto. Usaremos `Shapely` para identificar los "Bordes Medianeros" (intersección con lotes vecinos) vs "Bordes de Fachada". Los pilares (columnas) se posicionarán con un offset interno si es medianero, y a plomo si es fachada.

### Ronda 3: Estrategias de Mapeo UV y Texturas

**DAP:** Si IGP generará los muros por extrusión 2D, el mapeo UV es fácil. Podemos usar proyección `Box Mapping` calculando los bounding boxes por pared. Para las columnas y vigas expuestas, el concreto necesita variaciones. Propongo usar *Decals* proyectados de forma aleatoria para añadir roturas, fierros oxidados expuestos y grafitis en la fachada. El desgaste es clave: la base (los primeros 30cm) siempre tiene salitre o suciedad. Pasaremos un atributo por vértice (`Z_height` relativo al nivel del suelo) al shader para mezclar la textura de humedad.

**AA:** Excelente adición el salitre. Y ojo en los techos: casi nunca son losas limpias. Hay muretes de 1 metro (parapetos) para "esperar" el siguiente piso, fierros de construcción (`rebars`) que sobresalen de cada columna, y cuartos de calamina (techo ligero) irregulares, más el tanque de agua elevado (Rotoplas). 

**IGP:** Los fierros de espera son muy caros de renderizar si los hacemos con mallas cilíndricas. ¿Los manejamos con "alpha cards"?
**DAP:** Sí, o polígonos en cruz (2 quads interceptados) con una textura con canal Alpha de varillas oxidadas. Mucho más ligero y a lo lejos funciona perfecto.

### Ronda 4: Casos Borde y Resolución de Conflictos

**AA:** ¿Qué pasa si el lote está en esquina? Tendrá dos fachadas. La lógica del pandereta expuesto no aplica ahí, se debe tarrajear o dejar cara vista ambos lados.
**IGP:** El algoritmo analizará los bordes libres del polígono base (`Shapely.Polygon`). Si el borde tiene distancia > 2m a otra huella, es Fachada. Asignaremos etiquetas de borde: `FACHADA` o `MEDIANERA`. Las esquinas son la intersección de dos bordes `FACHADA`.
**DAP:** Eso me soluciona la vida. Si el `edge_tag == 'MEDIANERA'`, asigno el Material "Ladrillo_Pandereta_Expuesto". Si es `FACHADA`, asigno "Concreto_Tarrajeado" o "Ladrillo_Cara_Vista". 
**IGP:** Y para los fierros de espera: sabemos exactamente dónde instanciamos las columnas (nodos estructurales en 2D extruidos a 3D). Al calcular el último piso, en vez de instanciar un nuevo tramo de columna, disparamos el generador de `Alpha Cards` de varillas.

### Ronda 5: Síntesis Final y Plan de Acción

**AA:** Concluimos que la gramática no es solo aleatoriedad; es un sistema de reglas basadas en colindancia, pisos y economía.
**IGP:** Mi arquitectura será: 1. Análisis de contexto (Shapely), 2. Generación del Esqueleto (Pórticos), 3. Relleno de Muros (Booleanos 2D -> 3D), 4. Inserción de Techos y Props (Calamina, Tanques).
**DAP:** Mi parte requerirá UVs continuos por segmento, Atlas de materiales PBR específicos (Pandereta, Concreto crudo, Calamina oxidada, Plástico negro de tanque), y máscaras de vértice generadas en Python para controlar suciedad.

---

## PLAN ARQUITECTÓNICO V2 (Implementación Hiper-Detallada)

### 1. Fase de Análisis Topológico (El Contexto Dicta el Diseño)
**Módulo:** `LotAnalyzer.py`
- Entrada: Polígono 2D del Lote (`Shapely.Polygon`) y Lotes Vecinos.
- Operación: Determinar colindancias usando `polygon.distance(neighbor) < epsilon`.
- Salida: Polígono perimetral con bordes etiquetados (`EDGE_FACHADA`, `EDGE_MEDIANERA`, `EDGE_FONDO`).

### 2. Generación del Esqueleto Estructural (Pórticos)
**Módulo:** `StructureGenerator.py`
- Lógica: Encontrar los vértices del polígono y puntos intermedios a distancias regulares (ej. max 4m de luz).
- Generar Nodos de Columna (Puntos 2D + dimensión 0.25x0.25).
- Desfase: Si está en `EDGE_MEDIANERA`, la columna se desplaza hacia adentro del lote para no invadir.
- Extrusión: `Trimesh.creation.box()` en cada nodo desde $Z=0$ hasta $Z=H_{total}$.
- Asignación de Material: `MAT_CONCRETO_ESTRUCTURAL`.

### 3. Sistema Constructivo de Muros (Booleanos 2D -> Extrusión)
**Módulo:** `WallGenerator.py`
- Para cada segmento de borde 2D entre dos Columnas, se traza un `Polygon` que representa el muro en planta.
- Distribución de Ventanas: Generar cajas rectangulares 2D sobre la línea del muro (posiciones asimétricas, prefiriendo evitar columnas).
- Operación Booleana 2D: `Muro_Planta - Ventanas_Planta`.
- Extrusión 3D: Se levanta cada parche de muro del piso $N$ al piso $N+1$.
- Asignación de Material Dinámica: 
  - Si borde es `EDGE_MEDIANERA` $\rightarrow$ `MAT_PANDERETA`.
  - Si borde es `EDGE_FACHADA` $\rightarrow$ `MAT_TARRAJEO_PINTADO`.

### 4. Detalles de Azotea (El Caos Controlado)
**Módulo:** `RoofPropGenerator.py`
- **Fierros de Espera:** Sobre el tope de cada Columna en la última planta, spawnear mallas `Cross-Plane` texturizadas con `MAT_REBAR_ALPHA`.
- **Parapetos:** Extruir `EDGE_FACHADA` en el techo por 1.0m de altura, para simular la baranda/parapeto clásico.
- **Cuartos Precarios:** Encontrar el rectángulo inscripto más grande (`maximum_inscribed_rectangle` en Shapely) libre de escaleras. Levantar un prisma con `MAT_TRIPLAY` o `MAT_LADRILLO_CRUDO`, y coronar con un plano inclinado (5 grados) de `MAT_CALAMINA_CORRUGADA`.
- **Tanque Rotoplas:** Raycast desde arriba hacia el techo del cuarto precario (o la caja de escaleras). Instanciar cilindro pre-modelado de tanque negro.

### 5. Pipeline de Texturizado Métrico y Desgaste (Shading V2)
**Módulo:** `UVAndMaterialProcessor.py`
- **World-Space UVs:** Al crear las mallas en Trimesh, se asignan coordenadas UV donde `U = vértice.x` (o `.y` alineado a la normal) y `V = vértice.z`. Esto garantiza que los ladrillos mantengan tamaño real global de ~24x14x9cm.
- **Gradient Dirt Mask:** Se calcula un array de color de vértices `vertex_colors` basado en `np.clip(1.0 - (vertices[:, 2] / height_threshold), 0, 1)`. Esto permite al motor de render o exportador glTF mezclar lodo/salitre en las bases.
- **Decals de Fachada:** Generar planos poligonales superpuestos flotantes (+0.01m) en fachadas ciegas, mapeados con texturas PNG con alpha de desgaste de pintura y afiches chicha.
