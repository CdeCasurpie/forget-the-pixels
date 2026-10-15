# 06 · Solo balcones y galerías observados

Recibe aberturas completas e índices resueltos. Devuelve balconies, incluso [] si
no hay ninguno. Elige tipo projecting/gallery/box/terrace/juliet según la foto,
no por el estilo humano. El catálogo describe plataforma, baranda, cierre y cubierta.

Ancla a mass_ref/edge y un nivel existente floor_m (relativo a la base de masa).
Para opening_index usa la tabla actual. No conviertas una simple reja en balcón.
Verifica vuelo, ancho, límites y ausencia de colisión con otros cuerpos. terrace
requiere soporte existente y slab=false; juliet slab=false. stair necesita una
escalera existente: este piloto no sintetiza escaleras de fachada en otra etapa.

Los postes/columnas de una galería pueden ir en column_member. No los vuelvas a
añadir como miembros independientes. Brackets solo si hay ménsulas visibles o
una hipótesis de apoyo razonable anotada. Los soportes adicionales del porche
pueden describirse en notes para la etapa 07. No añadas ventanas/puertas nuevas.
