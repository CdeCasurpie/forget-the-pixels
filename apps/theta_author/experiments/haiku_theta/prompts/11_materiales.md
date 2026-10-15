# 11 · Solo materiales y colores

Devuelve primary_color, side_material, materials y wall_materials. Estos últimos
identifican mass_ref/edge y material_regions en coordenadas de fachada. No modifiques
formas, alturas ni vanos; los cambios de geometría corresponden a sus etapas.

Usa slots existentes y template válidos. Distingue pintura, piedra, ladrillo,
madera, metal y vidrio. Elige color de material, no color de sombra, reflejo o
vegetación. Una moldura de revoque puede usar frame con template=plaster; una
puerta de madera no obliga a que la casa tenga estilo madera.

Las texturas PBR reales pueden cambiar la apariencia en el visor. La comparación
automática usa color base sin texturas ni transparencia: no oscurezcas/aclarees
geometría para compensar artificialmente esa limitación. Si un slot se comparte
entre varias piezas, considera el efecto del override en todas ellas.

Conserva materiales de superficies ocultas como supuesto sobrio, no como observación.
