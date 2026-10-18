# R3 — Primer puente de vanos de catálogo

La ruta exterior de `plan_envelope()` reserva los huecos en el muro, sin crear
habitaciones, y `planning.catalogue_openings.materialize_openings(plan)` llama a
`opening_catalog.build_opening` para **cada** ventana y puerta. La exportación
incluye esas piezas reales en el GLB y en las vistas, sin emitir `_joinery` en
la ruta nueva. La ruta interior histórica (`interiors=True`) no cambia.

`tests/test_catalogue_openings_exterior.py` espía el constructor, verifica
semántica de ventana/puerta, cotas reales de pisos superiores, profundidad y
reserva del umbral en losa.

Esto es el **puente**, no la aceptación completa de R3: faltan expresiones
automáticas de arcos, rejas, mecanismos, portales y sobreluces desde la
intención de fachada, más banco visual por familia. No reemplazar sus perfiles
de catálogo por geometría simplificada.
