# Step 22 — revisión visual de composición 0.3

Se regeneraron los **19 lotes con evidencia `present` y sus 64 comparativas**
foto | render, usando en `after/` las mismas cámaras, FOV, parcela original,
frentes y semilla de `before/`. `1138310` no tiene evidencia válida ni carpeta
actual: no se creó un `after` ficticio. `before/` permanece intacto.

Método: inspección de **todas** las vistas `after/compare_*.jpg` junto a las
planchas `before` y las máscaras. La ocupación indicada es el área de las
masas **cerradas que tocan suelo** dividida por área del lote, no superficie
construida observada. La comparación visual se refiere a la forma en las
vistas disponibles, no a fotorealismo; vehículos, árboles y construcciones
vecinas permanecen en la foto, pero no en el render blanco. Los parámetros
de profundidad son hipótesis de baja confianza hasta ajuste multivista.

| Lote (vistas) | Ocupación before → after | Diagnóstico visual del after |
| --- | --- | --- |
| 1134299 casa salmón (4) | ~100% → 70% | Dos cuerpos, retiro y cerco: se ve por primera vez separación edificio/lindero. La casa aún tiene exceso de profundidad y la reja no reproduce su traza exacta. |
| 1134486 restaurante terraza (4) | ~100% → 69% | Planta baja abierta y cuerpo alto separado; mejora la lectura de terraza. La fachada blanca y la máscara del restaurante son ambiguas respecto al comercio magenta vecino: ancho/posición todavía no calzan de manera estable desde ambos ángulos. |
| 1135369 esquina en demolición (5) | ~100% → 71% | Hueco interior y arcos abiertos mejoran la condición de cascarón. Sigue pareciendo un edificio intacto: faltan paños demolidos, daño y valla temporal. Patio posterior inferido, no observado. |
| 1135370 casa crema (3) | ~100% → 74% | Dos cuerpos de distinta altura y cerco reemplazan el prisma uniforme de tres pisos. El torreón/arcos de la foto son más complejos, y el ancho de las aberturas sigue aproximado. |
| 1135382 casa esquinera (5) | ~100% → 100% | Planta baja de una altura y volumen alto parcial: mejor roofline. El solar aún lleno y la falta de garaje lateral/jardín hacen que el perfil posterior y los vacíos no sean equivalentes. |
| 1135384 comercio ladrillo/blanco (2) | ~100% → 91% | Garaje bajo y cuerpo posterior alto; corrige la altura uniforme. Portones/arcos y colores aún no corresponden al muro rojo y la cubierta de tejas observados. |
| 1135572 casa terracota (3) | ~100% → 68% | Cuerpo bajo frontal, alto posterior y corredor lateral con reja: silueta más defendible. El patio es más ancho/regular que el observado y quedan huecos genéricos. |
| 1135847 local con celosía (3) | ~100% → 100% | Masa del before ya era razonable: se conserva; la pantalla ahora **perforada** distingue estructura de persiana opaca. No reproduce dibujo exacto, letrero ni profundidad real. |
| 1137173 grifo (3) | ~100% → 9% cerrado | Mejora estructural dominante: losa de marquesina **abierta sobre columnas**, patio pavimentado y caseta baja. Forma/orientación de la cubierta y ubicación de la caseta aproximadas; no hay surtidores ni aviso alto. Vistas de épocas distintas. |
| 1137568 comercio/terraza (2) | ~100% → 67% | Segundo nivel abierto con cubierta ligera y baja porticada. En la foto solo parte del frente corresponde al local; todavía aparecen demasiados arcos y la posición de la terraza no coincide. |
| 1137619 banco (5) | ~100% → 100% | Se mantiene volumen largo de una planta y fachadas por cara; cornisa/pilastras mejoran lectura. La gran cara gris carece de portón monumental y ventanas con rejas correctas. El volumen amarillo BanBif contiguo puede ser **otro predio**: no incorporarlo sin nueva evidencia. |
| 1138183 bloque de balcones (5) | ~100% → 34% | Varios cuerpos/frentes con alturas distintas, retiro y balcones corridos: mayor mejora de masa en lote grande. Sobran vanos lineales y los cuerpos de esquina/fondo no reproducen exactamente el edificio; uno aparece como masa aislada desde cierto ángulo. |
| 1138209 casona con galería (2) | ~100% → 74% | Ala derecha retranqueada, galería parcial, frontón/gable y cerco. La foto tiene cubierta compuesta con buhardillas y galería detallada; techo y vanos siguen esquemáticos. |
| 1138261 edificio azul (3) | ~100% → 10% | Se evita extruir los 70 m del lote como edificio; fachada estrecha, gran baja abierta y aletas verticales. Aún no hay carpintería vertical continua ni precisión en la planta baja y vecino contiguo. |
| 1138283 vivienda verde (2) | ~100% → 60% | Edificio retraído tras muro/portón; alta parcial y patio: ahora se distingue cerco del volumen. La fachada y posición del vano alto difieren y el cerco resulta más regular/alto que en foto. |
| 1138316 muro/local (4) | ~100% → 6% cerrado | Desaparece la tira falsa de ventanas; muro perimetral largo y caseta hipotética. La evidencia segmentada mezcla tramos y vecinos: la caseta y su profundidad no son observaciones fiables. |
| 1138323 casona amarilla (5) | ~100% → 80% | Dos frentes con arcos reales, pilastras, cornisa y frontones. Mejora la arquitectura observable de esquina, pero remates escalonados y portal monumental siguen demasiado simples; el patio interior es prior. |
| 1138401 comercio rojo (2) | ~100% → 43% | Local bajo de portones grandes y resto libre, sin hilera falsa de ventanas. La secuencia real de locales/cerco y la cubierta ligera todavía no se reproduce. |
| 1138477 edificio blanco (2) | ~100% → 40% | Retiro de estacionamiento, dos niveles principales y alta parcial. Mejora su separación del lindero; siguen sin resolverse la planta baja verdaderamente abierta/pilotis, rampa exacta y volumen vecino. |

**No todos los `after` superan visualmente a su `before` en cada vista.** Las
hipótesis de caras/altura de `1134486`, `1137568`, `1135384`, `1138316` son
especialmente inciertas. En `1135382` y `1137619` casi no cambió la ocupación;
es honesto dejarlo registrado. Ninguna cifra de ocupación representa una
medición del footprint real. Las comparativas demuestran capacidad del nuevo
sistema, no optimización automática ni correspondencia perfecta.

## API y reproducción

Schema opt-in `theta.schema_version="0.3"`; el antiguo 0.1/0.2 y `reconstruct()`
siguen operativos. `massing.components` sustituye el `pattern` legacy cuando
se usa; `region` proyecta una franja parametrizada desde un frente canónico,
`cutouts` sustrae patio/corredor, `levels_m` define escalones, `kind="open"`
produce cubierta/losas **sin muros** con apoyos parametrizados, y `faces`
asigna programa de fachadas por cuerpo/cara/banda Z. `site.zones` clasifica
el remanente; `site.runs` sigue definiendo cercos por tramo. `roofs` y el
`roof` opcional por componente seleccionan cubiertas; `gable` se compone de
dos planos. `Evidence(state="prior")` permite señalar profundidad no vista.

Ejemplo mínimo (el frente es el anillo **canónico** devuelto por el resolutor):

```json
{
  "context": {"parcel": [[0,0],[12,0],[12,20],[0,20]], "fronts": [0]},
  "theta": {
    "schema_version": "0.3",
    "massing": {"components": [
      {"id": "main", "region": {"front_edge": 0, "depth_m": [3,14]}, "levels_m": [0,3,6]},
      {"id": "rear_top", "region": {"front_edge": 0, "u": [0,0.5], "depth_m": [6,14]}, "levels_m": [6,9]}
    ]},
    "facade": {"mode": "explicit", "openings": []},
    "site": {"fence": "reja", "zones": [{"id": "antejardin", "kind": "garden", "region": {"front_edge": 0, "depth_m": [0,3]}}]}
  }
}
```

Marquesina aislada: un único `component` con `kind="open"`,
`support={"kind":"columns", "spacing_m":4, "column_width_m":0.25}` y
`levels_m=[0,4.5]`; `site.zones=[{"id":"playa","kind":"parking"}]`.
Para hacer una baja porticada con volumen alto, situar debajo un `open`
`[0,3]` y encima un `enclosed` `[3,6]` del mismo alcance: el resolver calcula
columnas, cubierta parcialmente tapada y fachadas expuestas.

Desde `investigation/procedural_reconstruction`:

```bash
PYTHONPATH=src:. /home/cesar/Escritorio/UTEC/PFC1_Lima/venv310/bin/python -m pytest tests -q
/home/cesar/Escritorio/UTEC/PFC1_Lima/venv310/bin/python steps/step22_massing_before_after/build_after.py
/home/cesar/Escritorio/UTEC/PFC1_Lima/venv310/bin/python steps/step22_massing_before_after/build_after.py --lot 1137173
```

Cada `lotes/<id>_<nombre>/after/` contiene `request.json`,
`resolved_theta.json`, `building.glb`, `manifest.json`, `cameras.json`,
`render_<camera>.jpg` y `compare_<camera>.jpg`. Para una comparación concreta:
`lotes/1137173_grifo_marquesina/after/compare_<camera>.jpg` o
`lotes/1134486_restaurante_terraza/after/compare_8lkDlm03dQBhhhQOXjdfog.jpg`.

Para seguir hacia semejanza precisa hace falta un módulo de ajuste multivista
que optimice los parámetros contra siluetas/rooflines con incertidumbre,
anotación de qué edificio corresponde a cada máscara y control de oclusión.
No se puede demostrar igualdad 3D de azoteas/patios ocultos solo con estas
fotos ni restaurar el estado de demolición de otra fecha sin datos adicionales.
