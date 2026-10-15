# 03 · Lenguaje de piezas, sin añadir ornamentación

Recibe masas aceptadas, inventario, fotos y estilo humano sugerido. Selecciona
architectural_style entre republicano/barroco/clasico/madera/moderno, o null si un
estilo global forzaría piezas incompatibles con la casa mixta observada.

Este control selecciona perfiles compatibles para futuras puertas/ventanas/piezas;
no cambia la masa, no colorea ni genera adornos por sí solo. family permanece
quiet_house con composición explícita. No confundir familia con estilo.

Justifica brevemente mantener o apartarte de la sugerencia humana con elementos
visibles. Si eliges null, en etapas futuras los ensambles deberán indicar estilos
locales explícitos; auto no tiene un estilo global que heredar.
