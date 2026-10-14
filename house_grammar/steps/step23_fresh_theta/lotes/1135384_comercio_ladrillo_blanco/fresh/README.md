# 1135384 — frente ladrillo / cuerpo blanco retranqueado

**Límite de objetivo:** lote catastral del frente de ladrillo rojo con puerta estrecha arqueada de madera y portón ancho de madera, más el cuerpo blanco posterior visible sobre la azotea. Se excluyen expresamente el edificio alto de balcones a la izquierda y la cochera negra con teja a la derecha. Se revisaron ambas vistas `_lot.jpg` de esta carpeta. `after/request.json` aporta solo parcela, frente y cámaras: el nuevo programa se redactó desde las fotos.

## Estructura y profundidad

- `massing.components`: `garage` baja de 3.1 m a profundidad `0–4 m` respecto de la calle; `house` blanco de 6.7 m a profundidad `4–15 m`. Esta separación crea **azotea/terraza real por delante del cuerpo blanco**, no un paño blanco coplanar con la pared roja.
- Primer plano rojo: `FacadeMaterialRegion` en las dos aristas frontales del garage con slot `brick` rojo. Sobre la fachada larga, dos vanos con **recess_m .17**: puerta de arco (`legacy`, `arch_rise_m:.44`) y portón rectangular (`wood_panel`). Pilastras/jambas de piedra (`panel` a 0.18–.21 m), `segmental_surround` hueco para puerta, `frame` alrededor del portón, `ledge` y `sill_band` continuos en coronación. Las proyecciones son geometría materializada; no una textura pintada.
- Segundo plano blanco: dos ventanas horizontales anchas con carpintería gris sobre el muro retirado 4 m, puerta de madera a la terraza, alféizares individuales, baranda `balcony` metálica a menor profundidad y alero de remate. Cubierta plana con parapeto bajo y sin props inventados.
- Paleta: `plaster` blanco roto, `brick` rojo, `stone` gris concreto, `wood` oscuro, `metal` negro y `glass` oscuro. `finish` estándar; sin ornamentos neoclásicos, letreros ni persianas ajenas a la foto.

## Salidas y límites

`request.json`, `resolved_theta.json`, `building.glb`, dos `compare_*.jpg`, dos `render_*.jpg`, `cameras.json`, `manifest.json`. Reconstrucción reproducible desde la raíz `investigation/procedural_reconstruction`: `python3 steps/step23_fresh_theta/lotes/1135384_comercio_ladrillo_blanco/build_fresh.py`. `validate_mesh` pasa (`envelope_test: passed`, 5024 triángulos). Ambas comparativas fueron revisadas: el lote está en la zona correcta y el vecino negro no se incluyó.

Diferencias visibles todavía: la textura geométrica de los ladrillos no reproduce cada junta real, el marco continuo del portón queda demasiado grueso frente a la foto, la terraza real lleva una reja fina frontal y escalerilla metálica que el control actual no ubica correctamente a 4 m del cuerpo blanco. El árbol delante oculta parte de las fotografías y no se debe imitar como arquitectura. No confundir validación de contención con semejanza fotográfica.
