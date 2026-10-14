# CrownProfile (theta 0.3)

`FacadeControls.crowns=(CrownProfile(u=(.35,.55),kind='stepped',height_m=1.4,depth_m=.2),)`
compone una coronación local en el chart de pared o FacadeZone. Solo se
admiten `triangular` y `stepped`. Los intervalos deben estar ordenados,
dentro de [0,1] y sin solapamientos; altura 0.20–3.0 m, profundidad
0.05–0.8 m. Un campo no vacío requiere schema 0.3. No se deduce de motifs.

El compositor crea `FacadeProjection` semántica `crown_triangular` o
`crown_stepped` con base en la cota superior del programa actual. El prefab
de fachada materializa un triángulo o tres escalones como un único polígono
extrudido en profundidad; no modifica `MassComponent`, niveles o roof.
`grammar.py` valida específicamente esas entidades con source `crown_profile`
sin relajar las demás proyecciones.

`VisibleFacadeBuilder.crown_panel()` extiende **solo** los intervalos U que
siguen expuestos en el borde superior de ese patch, y solo para la corona.
La zona compone localmente y `_facade_zone_wall()` traslada U/Z antes de
materializar; el helper de `_BandBuilder` desplaza Z y aplica el mask extendido.
Los vanos, otras proyecciones y paredes conservan el clipping original.

Metro: `python steps/step22_massing_before_after/build_metro_motif.py --crown`
genera `lotes/1138323_casona_amarilla_esquina/after_crown_profile/` desde el
AFTER monumental_portal, conservando cámaras, semillas, masas y cubiertas.
`review_all_views.jpg` muestra PHOTO | AFTER monumental_portal | AFTER CrownProfile.
En las vistas frontal y oblicuas aparece un escalonamiento sobre el acceso
central, visible incluso reducido. Aún es una silueta simple: no reproduce
la altura, curvaturas, logotipo ni el orden de pilastras del edificio real.

Validación: **18 tests CrownProfile**, **94 tests relacionados y 36 subtests**;
suite completa: **356 passed, 129 subtests passed in 66.03s**. Los
**21/21 fingerprints** y planes resueltos legacy permanecen idénticos con
`crowns=()`; las cinco cámaras de Metro pasan la prueba de envolvente.
