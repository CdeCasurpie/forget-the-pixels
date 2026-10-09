# 1135370 — edificio crema balcones

## Observación
Edificio crema de tres niveles con balcones, vanos y entrada central. 3 fotos present y 2 absent. La máscara segmentada señala el objetivo; el contexto de la foto conserva vecinos y oclusiones.

## Hipótesis θ (before)
`balcony_apartments`, 3 pisos, 9.2 m de altura supuesta, 3 vanos máximos por frente (ajustados por longitud), color RGB [0.76, 0.73, 0.64]. Parcela original y frentes Step21, sin masas explícitas. Tras revisar el área frontal se agregó `front_setback_m=0.5`, `fence=concreto_bajo`, `garden=false`: muro bajo con reja y franja de separación, sin afirmar un jardín profundo. 4936 triángulos; envolvente `passed`. 3 comparativas foto | render en `before/`; `analisis_theta.json` y `before/request.json` describen los controles usados.

## Brecha observada / encargo de after
Balcones, forma escalonada y vanos reales no coinciden con repetición simple; hay volumen vecino en las fotos.
