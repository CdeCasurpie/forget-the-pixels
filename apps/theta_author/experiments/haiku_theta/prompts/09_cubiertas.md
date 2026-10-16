# 09 · Solo cubiertas, aleros y marquesinas

Devuelve roof, roofs, roof_assemblies y canopies completos para esta etapa.
Recibe masas, niveles, remates y referencias de frontones. Mantén el número de pisos.

Separa techo básico plano de cubierta detallada shed/gable/hip/pavilion/band/compound.
roof.kind y cada component.roof/roofs/roof_bodies[].roof solo admiten flat;
slope_deg básico debe ser null. Corrugada también se autoriza exclusivamente como
roof_assemblies.design.covering=corrugated. Usa detail=full salvo pedido explícito
de simplificación. rotation_deg mide la dirección ascendente desde +X local XY;
la cumbrera gable es perpendicular. No infieras este ángulo del norte geográfico.
Describe material de recubrimiento, pendiente, alero, parapeto y props solo según
evidencia o supuesto explícito. Cuando no se ve el fondo, no inventes una cubierta
ornamental; conserva una solución sobria y explica la incertidumbre.

Para encuentros behind/gable referencia un crown_ref existente. Las cubiertas
detalladas reemplazan superficies básicas, no son una masa adicional. Verifica
que parapeto, aleros y tejas quepan y que no dupliquen una cubierta de galería.
props=[] indica ausencia de objetos solicitados, no un reconocimiento visual de
ausencia. props_mode=off evita inventar objetos en cubiertas poco observables.

Este piloto no añade roof_bodies después de cerrar masas; si se observa un cuerpo
habitable omitido, debe volver a etapa 02 sin aumentar los pisos humanos.
