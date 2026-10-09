# Auditoría de área libre, cerco y estacionamiento en θ 0.2

Se probó `massing.front_setback_m` = 0.5, 1, 2, 3 y 4 m sobre los
`before/request.json` de los 20 lotes, manteniendo P, frentes y demás θ.
**Solo `1135370` resolvió el retiro de 0.5 m.** Los otros 19 fallaron por
`Partially exposed edges require a future interval schema` (retiro corta un
muro) o `front setback: disconnected, holed, tiny or too narrow geometry`
(recorte de frentes en parcela irregular divide/colapsa la huella).

`1135370` fue regenerado con retiro de 0.5 m, `fence=concreto_bajo` y
`garden=false`: malla y tres comparativas actualizadas. Representa un
muro bajo con reja y una franja frontal, no un jardín profundo.

## Áreas libres observadas que el before aún representa mal

| Lote | Observación de las vistas segmentadas | Resultado θ actual |
| --- | --- | --- |
| 1134299 | Casa salmón, jardín y estacionamiento tras muro bajo y reja | Retiro falla por exposición parcial; sin retiro el cerco no aparece. |
| 1135382 | Casa de esquina con garaje/lateral libre | Retiro falla por exposición parcial. |
| 1138283 | Torre verde tras cerco de ladrillos y patio | Retiro colapsa el recorte de frentes; `fence=ladrillos` sin retiro no crea espacio. |
| 1138477 | Edificio blanco y estacionamiento abierto | Retiro colapsa la huella; θ no tiene superficie de aparcamiento. |
| 1138183 | Bloque moderno con retiro amplio | Retiro falla por exposición parcial. |
| 1138209 | Casona con pórtico y área de acceso | Retiro falla por exposición parcial. |
| 1134486 | Restaurante con terraza exterior | Retiro colapsa la huella; no hay programa terraza. |
| 1137173 | Grifo con playa abierta, surtidores y marquesina exenta | Retiro falla; no hay patrón para gasolinera. |
| 1135370 | Muro frontal bajo con reja | Retiro de 0.5 m y `concreto_bajo` funcionan. |

La máscara de imagen no equivale a una huella edificada medida; la proporción
de área libre observada sigue siendo una estimación.

## Lo que sí existe en src

- `domain/theta.py:MassingControls.front_setback_m` retrae la masa respecto
  de **todos** los frentes declarados a la vez, no por arista independiente.
- `SiteControls.fence`: `none`, `reja`, `concreto`, `ladrillos`,
  `concreto_bajo`; `site.runs` admite tramos con puertas/portones, pero
  `modeling/boundaries.py` solo coloca cercos en tramos del lindero **no
  ocupados por la masa**. `single_block` llenando el lote deja cero tramos.
- `SiteControls.garden` es booleano; `modeling/site.py:plant_garden` agrega
  plantación en el remanente libre. No controla porcentaje ni forma.
- No hay en θ área pavimentada, plazas de estacionamiento, rampa, terraza
  de mesas, ni marquesina exenta. Existen primitivas legacy de sitio en
  `modeling/layout.py` y `grammar.py`, pero no son controles de θ 0.2.

## Requisitos para la ampliación

1. Soportar intervalos de muros parcialmente expuestos y parcelas irregulares
   al retraer la masa, sin dibujar `theta.masses` manualmente.
2. Implantación procedimental por arista y profundidad: huella de edificio
   distinta del lote catastral con restricciones de soporte.
3. Áreas exteriores tipadas (jardín, patio pavimentado, estacionamiento,
   acceso, terraza) con proporción/superficie controlable.
4. Cercos por tramo con puertas y portones alineados a esas áreas.
5. Marquesina exenta y voladizos para comercio/grifo.
