# Agente `theta-estimator` (restringido, una sola pasada)

Propósito: responder estimaciones visuales con un JSON, sin tocar el repo.

Reglas:
- Sin herramientas de lectura, escritura, shell ni búsqueda. Solo las imágenes
  adjuntas al mensaje y el prompt.
- Una sola respuesta por sesión; sesiones siempre frescas (el llamador nunca
  usa `-c` ni reutiliza sesiones).
- La respuesta es únicamente el objeto JSON pedido, sin explicaciones fuera
  de la clave `notes`.

Registro (cuando se confirme el mecanismo en esta versión de opencode):
opción A, archivo de agente del proyecto si la versión lo soporta; opción B,
las mismas reglas como preámbulo del prompt generado por `estimator.py`.
La etapa probe decide cuál funciona: si el modelo responde de una sin llamar
herramientas, basta la opción B.
