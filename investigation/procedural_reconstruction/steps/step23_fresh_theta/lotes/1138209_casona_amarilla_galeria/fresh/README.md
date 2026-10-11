# 1138209 — casona amarilla y galería (rehecho)

**Objetivo en las dos `_lot.jpg`:** casona crema con un bloque a línea de vereda (puerta + dos ventanas abajo, triple ventana con rombos y ventana lateral arriba, mansarda marrón) y un bloque retirado con galerías blancas de dos niveles, jardín y cerco con portón. La vivienda de balcones a la izquierda y la casa blanca a la derecha son vecinas y no se modelan.

## 1. Masas (corregidas tras la crítica)

`../massing_preview/` guarda cuatro volúmenes sin decoración y sus dos comparativas. El error anterior era usar un `gable` cuya cumbrera quedaba perpendicular a la calle y mostraba un triángulo frontal inexistente. Ahora los dos bloques delanteros son poco profundos con `tile_shed` de alero paralelo a la calle, y los traseros son planos y quedan ocultos desde las cámaras bajas:

- `street_front` $(\approx 7.7,m)$ profundidad $0-3.8,m$, dos pisos hasta $6.9,m$, `tile_shed` $35^{\circ}$ (máximo de la gramática).
- `street_rear` mismo ancho, $3.8-15.5,m$, plano.
- `garden_front` $(\approx 9.8,m)$ frente a $2.35,m$ de la calle, hasta $6.35,m$, `tile_shed` $20^{\circ}$.
- `garden_rear` $7.0-15.5,m$, plano.

La división del frente se movió de $.52$ a $.44$ porque el bloque de calle ocupaba demasiado ancho y dejaba un paño ciego de $\approx 3,m$ hacia la galería. El cerco va solo delante del jardín ($7.83-17.40,m$ del borde 4) con el portón al extremo oeste, donde la foto lo muestra abierto.

## 2. Detalles

`fresh/` añade en el bloque de calle puerta hundida con vestíbulo oscuro, ventanas de retícula $3\times4$, triple ventana de una sola abertura con reja de rombos y ventana lateral estrecha, cercos moldeados, bandas y cornisa dentada. En el bloque de galería: puertas acristaladas y ventanas tras dos galerías `classical` blancas (balaustres torneados) con alero, y zona de jardín. La base del cerco `reja` usa el slot `brick` reteñido a gris porque el material base es rojizo y no coincide con la foto.

## 3. Qué se parece y qué no

Las comparativas muestran ya el retiro del jardín, las dos alturas, las galerías blancas y el cerco donde corresponde. **Siguen sin parecerse:**

- La mansarda real es casi vertical abajo con buhardillas salientes; la gramática limita la pendiente a $35^{\circ}$ y no tiene `dormer`, así que el techo renderizado se ve como una banda fina en escorzo, no como el faldón alto de la foto.
- La triple ventana y sus molduras son más simples; faltan ménsulas, calados y el ritmo fino de carpinterías.
- Las galerías procedurales tienen postes y capiteles regulares; faltan cruces de madera, macetas y la reja fina del cerco.
- La proyección catastral disponible deja el conjunto algo desplazado respecto de la foto en la cámara cercana.

`manifest.json`: `envelope_test: passed`, 20284 triángulos, 2 vistas. Eso solo valida límites, no fidelidad. Regenerar con `python3 steps/step23_fresh_theta/lotes/1138209_casona_amarilla_galeria/build_fresh.py --massing-only` y luego sin flag.
