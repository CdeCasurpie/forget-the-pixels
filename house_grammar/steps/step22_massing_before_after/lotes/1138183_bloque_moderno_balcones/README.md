# 1138183 — bloque moderno balcones

## Observación
Bloque moderno gris de unos cinco niveles: franjas de balcones corridos, núcleo oscuro. 5 fotos present y 0 absent. La máscara segmentada señala el objetivo; el contexto de la foto conserva vecinos y oclusiones.

## Hipótesis θ (before)
`balcony_apartments`, 5 pisos, 15 m de altura supuesta, 5 vanos máximos por frente (ajustados por longitud), color RGB [0.75, 0.77, 0.75]. Parcela original y frentes Step21, sin masas explícitas. 62328 triángulos; envolvente `passed`. 5 comparativas foto | render en `before/`; los archivos `analisis_theta.json` y `before/request.json` describen los controles realmente usados.

## Brecha observada / encargo de after
Bloque de cinco plantas con balcones corridos y núcleo oscuro; la gramática repite módulos aislados, no un sistema de balcón continuo.
