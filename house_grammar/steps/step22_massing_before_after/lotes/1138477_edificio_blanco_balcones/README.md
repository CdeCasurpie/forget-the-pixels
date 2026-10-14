# 1138477 — edificio blanco balcones

## Observación
Edificio blanco de tres pisos con balcones metálicos y planta baja retranqueada. 2 fotos present y 3 absent. La máscara segmentada señala el objetivo; el contexto de la foto conserva vecinos y oclusiones.

## Hipótesis θ (before)
`balcony_apartments`, 3 pisos, 9.6 m de altura supuesta, 3 vanos máximos por frente (ajustados por longitud), color RGB [0.83, 0.85, 0.82]. Parcela original y frentes Step21, sin masas explícitas. 2600 triángulos; envolvente `passed`. 2 comparativas foto | render en `before/`; los archivos `analisis_theta.json` y `before/request.json` describen los controles realmente usados.

## Brecha observada / encargo de after
Balcones metálicos, ritmos y retranqueo de planta baja difieren de los patrones automáticos.
