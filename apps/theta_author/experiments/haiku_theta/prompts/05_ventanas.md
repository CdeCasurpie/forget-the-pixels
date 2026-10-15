# 05 · Solo ventanas, respetando las puertas aceptadas

Recibe puertas aceptadas con posiciones y tablas de paredes/índices. Devuelve
placements nuevos de kind=window; no reenvíes puertas ni las muevas para hacer espacio.
Cada id es único entre todas las aberturas. Conserva alineación por piso y ejes
visibles; no conviertas la fachada en una retícula simétrica si la foto no lo es.

Incluye forma, receso, dimensiones, divisiones, marco, reja y alféizar observables.
Un arco es distinto de una moldura curva superpuesta. Un óculo de muro puede ser
circle/ellipse; uno dentro del frontón se construirá en etapa 08, no aquí.

Con estilo global, las ventanas vinculadas admiten legacy/slim_window/storefront/open;
no wood_panel/screen/louver. Para una ventana sobria usa dimensiones/perfil moderados.
No modeles un balcón cajón como una hilera de ventanas de pared duplicada: separa
la abertura del muro de la carpintería saliente que se añadirá en etapa 06.

Respeta los dominios expuestos y las puertas. Si falta espacio porque masas o
puertas están mal, informa el problema con su etapa en blockers; no alteres pisos.
