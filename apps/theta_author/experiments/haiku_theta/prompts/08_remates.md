# 08 · Coronación, molduras y relieve de fachada

Devuelve crowns, entablatures, trim y wall_details. Cada wall_detail identifica
mass_ref/edge y contiene top_profile y projections; el programa conserva sus vanos.

Elige el mecanismo correcto: top_profile modifica la silueta continua del muro;
crowns construye un frontón volumétrico anclado; entablatures crea bandas continuas;
trim produce cornisa/zócalo; projections añade relieve local. No dupliques el mismo
remate con dos mecanismos. No añadas balcones/pilastras por projections si ya existen.

Un frontón/óculo no crea piso. Para opening_top usa opening_index actual. Para una
silueta curva observada distingue curvatura arquitectónica de la proyección angular.
top_profile y trim perimetral no combinan actualmente: deshabilita las cornisas y
zócalos de trim cuando esa combinación sea incompatible, no cambies el perfil
observado para ocultar el error. Un entablamento absolute necesita mass_refs que
alcancen su cota; no aplicarlo indiscriminadamente a anexos más bajos.

Las cubiertas se diseñan después de estos remates para que puedan referenciarlos.
No asumas un frontón detrás de un parapeto simple ni una habitación tras una cartela.
