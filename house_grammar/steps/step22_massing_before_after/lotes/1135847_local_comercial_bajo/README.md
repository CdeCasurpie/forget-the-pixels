# 1135847 — local comercial bajo (medianero)

Lote original: cuadrilátero ~58.8 m², frente angosto ~4 m (arista 2 en orden
de anillo; `street_edge_indices=[1]` en `lot_fronts.json`), fondo ~14 m.
Edificio real (3 fotos present / 2 absent): local angosto de 2 niveles entre
medianeras — planta baja con cafetería "Coffee & Waffles" (escaparate y acceso
vidriado), planta alta con **celosía prefabricada blanca** de pantalla completa.
Vecinos: local blanco con paradero Cabify (izquierda), torre residencial 1430
(derecha). Ver `_overlay.jpg` (máscara verde) y `_masked.jpg` (fondo a negro)
para el foco; `_lot.jpg` muestra el prisma catastral guía.

## before/ (gramática actual)

`request.json`: parcela original trasladada a metros locales, `fronts=[2]`,
`mixed_use`, 6.6 m, 2 pisos, semilla 11. Sin masas explícitas. Fachada frontal
explícita (solo vanos): dos paños vidriados de cafetería en planta baja,
panel de letrero sin texto y un paño superior con lamas horizontales blancas.
Lados medianeros sin vanos; cubierta plana con parapeto bajo.
`analisis_theta.json` registra esos controles; se probaron primero los vanos
repetidos de `mixed_use`, descartados por inventar balcón, ventana y toldo.
Salidas: `building.glb` (884 triángulos, envolvente OK), `resolved_theta.json`,
`render_<camera>.jpg` — un render por cada vista present, con **el mismo ojo,
orientación y FOV que el recorte Street View** (1280×900, renders colocados en
la posición con desfase para comparación píxel a píxel; la geometría deriva de
la forma catastral original).

Brecha visible: el prefab `louver` produce lamas horizontales opacas; la
celosía real es una trama perforada repetitiva. El rótulo real tiene texto
propio pero el catálogo de glifos solo admite LOCAL/TALLER/TIENDA, por eso
el panel queda sin texto antes que poner un letrero incorrecto. El volumen
de dos pisos sigue el lote catastral entero y la vegetación no se modela.
El `after` deberá añadir esas capacidades manteniendo parcela, frentes,
altura, semilla y puntos de vista.

## after/ (pendiente)
