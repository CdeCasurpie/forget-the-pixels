# Fase 2 y 3: Extrusión Estructural y Proyección Fotométrica

**Fecha:** 2026-08-31
**Contexto:** Tras lograr la georeferenciación perfecta de la nube de puntos sparse con nuestro framework en Khipu (ver `03b_experiments_khipu_success.md`), comenzamos a cruzar la geometría abstracta (lotes catastrales) con la data visual del dron. Este es el corazón de la tesis "Olvida los Píxeles".

---

## 1. Hito Alcanzado: Extrusión Paramétrica (LOD1)

Se desarrolló el script `extrude_lotes.py`, el cual levanta algorítmicamente la ciudad en 3D prescindiendo de las nubes densas. 

### Pipeline Matemático de la Extrusión:
1. **Fusión Espacial (UTM 18S):** La nube de puntos ECEF fue transformada al sistema UTM para coincidir milimétricamente con el Shapefile de Barranco.
2. **Filtrado de Vegetación y Ruido:**
   - Se aplicó un **Índice de Exceso de Verde (ExG = 2G - R - B > 0.05)** para detectar y aislar los puntos que corresponden a copas de árboles.
   - Se aplicó un filtro estadístico para eliminar ruido flotante y subterráneo.
   - *Nota:* Estos puntos se aíslan solo para el cálculo de alturas, pero no se borran del render final para dar contexto visual.
3. **Spatial Join (Cruce Geoespacial):** Usando `geopandas`, se cruzaron las coordenadas XY de los puntos limpios con los polígonos del catastro. Esto permite saber exactamente qué puntos de la nube cayeron dentro del perímetro de cada casa.
4. **Cálculo Robusto de Altura:** En lugar de usar la altura máxima absoluta (vulnerable a ruido), se utilizó el **percentil 90** del eje Z para estimar el techo (roof) de cada edificio.
5. **Generación de Mallas:** Se usó `trimesh` para extruir los polígonos 2D a bloques sólidos 3D (LOD1) que reposan exactamente sobre el nivel del suelo (percentil 5 global).

---

## 2. Hallazgo: Desalineación de la Nube Densa Antigua

Se descargó el resultado de la prueba densa (`fused.ply` - Job 50353) para hacer una comparación "Abstracto vs Denso". 
**Problema:** Al inspeccionar los vértices, se descubrió que no está georeferenciada.
**Causa:** Ese job se ejecutó *antes* de descubrir el bug de la doble conversión GPS en COLMAP (`--ref_is_gps 0`). Por lo tanto, el modelo denso existe en un espacio local flotante arbitrario y no puede superponerse directamente sobre el mapa 2D sin aplicar un algoritmo ICP (Iterative Closest Point) o volver a ejecutar el pipeline denso en Khipu.

---

## 3. Hoja de Ruta Inmediata: Texturizado Directo (El Clímax)

Para resolver el hecho de que los edificios extruidos son mallas blancas/grises, pasaremos a la **Fase 3: Proyección Fotométrica**.

En lugar de reconstruir una malla densa que pesa decenas de GB, usaremos las poses de cámara de COLMAP (`images.bin`, `cameras.bin`) para hacer un raycasting desde las caras de los edificios hacia las 195 fotografías originales del dron.

**Estrategia técnica diseñada:**
- No se crearán pesados "Atlas de texturas" UV.
- Se creará un archivo `.mtl` donde **cada foto del dron es declarada como un material único**.
- Las coordenadas (u, v) de cada pared se calcularán multiplicando los vértices 3D del edificio por la matriz intrínseca/extrínseca de la mejor cámara que lo haya observado.
- Resultado esperado: Un archivo `.obj` extremadamente ligero (abstracto) pero con texturas fotorrealistas en ultra-alta resolución, logrando eficiencia metropolitana.
