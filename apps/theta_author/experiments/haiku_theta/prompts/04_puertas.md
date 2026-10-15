# 04 · Solo puertas y portones del edificio

Recibe tablas de paredes resueltas, masas, niveles, inventario, estilo y fotos.
Devuelve placements con id de autoría, mass_ref, edge y Opening completo para cada
puerta/portón del muro construido. kind solo door/gate. El cerco queda para etapa 10.

Prioriza ubicación, ancho y alto del acceso; define también forma, número de hojas,
tipo de relleno y marco observables. Las puertas detalladas usan Opening.door.
No uses frame_profile en una puerta sin ese bloque. Los accesos a balcones también
son puertas: ubicarlos ahora permite anclar el balcón después sin inventar vanos.

u_m/v_m son métricos en la pared original. Verifica el dominio visible y la altura
del piso correspondiente. Deja margen para jambas, portal y cornisas. No hagas que
una puerta atraviese una losa intermedia. El ancho aparente en la foto está afectado
por proyección y perspectiva; usa ancho métrico de la pared y varias vistas.

Todavía no añadas ventanas, peldaños, balcón ni marquesina. Se devolverá una tabla
con índices resueltos para que las etapas posteriores anclen esos ensambles.
