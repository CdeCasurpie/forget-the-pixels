# 1134486 — únicamente el restaurante blanco

**Corrección del alcance:** El Tambo fucsia es el vecino y queda fuera del theta y del GLB. La versión previa lo incorporó por interpretar erróneamente la proximidad dentro del recuadro de la foto como pertenencia al mismo edificio. `fresh/request.json` tiene solo dos componentes, `restaurant` y `upper`; no contiene `side`, paños fucsia ni rótulos Tambo.

Las cuatro imágenes `_lot.jpg` de esta misma carpeta son la única evidencia visual. `after/request.json` se usa únicamente para geometría de parcela, frentes y cámaras. `build_fresh.py`, ejecutado desde `investigation/procedural_reconstruction`, regenera la carpeta `fresh/`.

## Geometría y fachadas

El local blanco ocupa dos plantas con tres ventanas reticulares verde turquesa en la planta alta, un letrero central «TERMINAL PESQUERO», PB profunda y abierta al comedor exterior, voladizo delantero sustentado en columnas. Del otro lado, la toma oblicua muestra tres vidrieras estrechas altas y portones de madera abajo. La cubierta es plana y discreta; no se inventaron objetos sobre ella.

Se expresa con `schema_version: 0.3` y dos `massing.components` `PlanRegion`: cuerpo PB `u:[0,.68]`, `depth_m:[2.2,11]`, `levels_m:[0,3.2]`; cuerpo alto `u:[0,.68]`, `depth_m:[.6,11]`, `levels_m:[3.2,6.4]`, soporte `columns`. La fracción `.68` acota el edificio blanco dentro de la parcela catastral, que se extiende hacia el local contiguo. Son medidas aproximadas; no se copiaron XY de un mesh anterior.

`FacadeControls(mode: explicit)` fija vanos de PB, tres ventanas altas turquesa con divisiones, el lado visto oblicuamente y dos `sign_box` discretos con el nombre del restaurante. `site.zones` representa el piso del área exterior; no hay cerco medianero espurio ni jardín bajo las mesas. `primary_color` blanco roto, `frame` turquesa y `wood` marrón. No se usa el programa automático de `mixed_use` para colocar escaparates ajenos.

## Comprobación y diferencias visibles

`manifest.json` informa `envelope_test: passed`, 3932 triángulos y cuatro comparativas `compare_*.jpg`. Los renders se alinean con las cámaras originales y ahora muestran **solo el edificio blanco**; el fucsia permanece exclusivamente en el panel fotográfico como contexto. La terraza de la fotografía tiene sombrillas, macetas, mesas, cerca de madera y personas: `theta` no contiene prefabs declarativos para ese conjunto; el piso y el porche están representados, pero la escena aún luce mucho más vacía. El fondo blanco del renderer y la ausencia de árboles/texturas tampoco se deben confundir con geometría faltante del local. Las letras del cartel son geometría esquemática y no igualan el arte original.
