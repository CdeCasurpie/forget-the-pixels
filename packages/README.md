# Código compartido por las aplicaciones

Esta carpeta es necesaria para las aplicaciones A y B:

- `barranco_data/`: persistencia JSON, revisiones del catastro, operaciones sobre
  lotes, agrupación de manzanas y vistas guardadas.
- `barranco_imaging/`: proyección angular de fotografías/cámaras y dibujo del
  prisma de referencia, incluido el renderizador Canvas compartido.

Las gramáticas se organizan por separado: `house_grammar/` contiene la gramática
de edificios; una futura `public_space_grammar/` podrá consumir estos mismos datos.
