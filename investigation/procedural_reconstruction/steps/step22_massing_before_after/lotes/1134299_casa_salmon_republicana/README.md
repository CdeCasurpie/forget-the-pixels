# 1134299 — casa salmón republicana

Lote original irregular de ~261 m², frente calculado en `lot_fronts.json`.
Cuatro fotos present, una absent. Casa de dos plantas color salmón con
molduras blancas, vano bajo en arco, puerta arqueada, ventanas altas con
rejas y pequeño balcón a la derecha. Muro bajo y reja metálica blanca
delimitan jardín y estacionamiento al frente.

## Before

`analisis_theta.json` fija `republicano` con dos niveles y fachada principal
**explícita**: seis vanos en posiciones observadas, rejas blancas y un ledge
del balcón. Baja y alta salmón mediante override del slot `stone`.
`before/` contiene GLB válido de 3 608 triángulos y cuatro renders y
comparativas foto | render con los ángulos de Street View.

Se probó `front_setback_m=1.5`, pero `src` rechazó la exposición parcial
de aristas de esta parcela irregular. Sin ese retranqueo el cerco automático
no es visible porque la masa ocupa el lindero; `site.garden=true` solo
expresa presencia, no porcentaje. Los arcos reales siguen rectangulares
y falta el cuerpo lateral escalonado. Encargo para `after/`: arcos,
implantación con jardín/cerco y volumen lateral. No usar masas explícitas.
