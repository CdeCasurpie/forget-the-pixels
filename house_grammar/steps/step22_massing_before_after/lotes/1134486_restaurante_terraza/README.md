# 1134486 — restaurante terraza

## Observación
Restaurante blanco con mesas exteriores y terraza; baja comercial y ventanas pequeñas arriba. 4 fotos present y 1 absent. La máscara segmentada señala el objetivo; el contexto de la foto conserva vecinos y oclusiones.

## Hipótesis θ (before)
`mixed_use`, 2 pisos, 6.4 m de altura supuesta, 3 vanos máximos por frente (ajustados por longitud), color RGB [0.84, 0.83, 0.79]. Parcela original y frentes Step21, sin masas explícitas. 6928 triángulos; envolvente `passed`. 4 comparativas foto | render en `before/`; los archivos `analisis_theta.json` y `before/request.json` describen los controles realmente usados.

## Brecha observada / encargo de after
No reproduce mesas móviles/terraza abierta ni la rotulación propia del negocio; la baja comercial y la alta blanca son aproximaciones.
