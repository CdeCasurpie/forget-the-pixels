# 01 · Leer y separar lo observado

Recibe base humana, parcela, frentes, cámaras y todas las fotos seleccionadas.
Identifica la casa objetivo y describe sus partes. No modifiques geometría aún.

Devuelve target_description, inventory y occlusions. Cada elemento de inventory
necesita ID estable, categoría, ubicación comprensible (cara/piso/lado), descripción,
view_ids y certeza. Incluye masas/retiros, puertas/portones, ventanas, balcones,
miembros, silueta superior, cubiertas visibles, cercos/suelo y materiales.

Distingue una puerta de vivienda de una puerta del cerco; una baranda de una reja;
un volumen de un balcón; un frontón de una habitación. Describe ejes y cantidades
de vanos visibles por piso sin inventar los tapados. Marca qué parte del fondo o
techo no se ve. No calcules cotas precisas todavía ni cambies los pisos humanos.

Este inventario se transmite a las demás etapas para que no vuelvan a interpretar
todo desde cero. Si discrepas del estilo sugerido, anótalo; su decisión es etapa 03.
