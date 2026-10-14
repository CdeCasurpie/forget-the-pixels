# ArchitecturalMotif v1: monumental_portal

API opt-in en schema θ 0.3:

```python
FacadeControls(
    bay_groups=(...),
    motifs=(ArchitecturalMotif(kind="monumental_portal", bay=3,
                               floor=0, opening_shape="arch", pediment=True),)
)
```

`bay` es el índice aplanado de OpeningEdit dentro del chart de FacadeControls;
en FacadeZone es local a la zona. Solo se permite `floor=0` y un motif por
target. No se infiere del `BayGroup.role`. Motifs no vacíos requieren schema
0.3 y modo repeat. `motifs=()` conserva los fingerprints anteriores.

Orden: generación de openings → OpeningEdit → monumental_portal → relief
global. Un suppress del bay señalado produce ValueError; un replace aporta
el opening que el motif decora. El target debe ser door/gate. El motif no
duplica la puerta; con `opening_shape="arch"` la transforma en arco con
`arch_rise_m` limitado por ancho y alto.

La compilación usa dos `FacadeProjection('pilaster')`, un `frame` profundo,
una `cornice` local y, opcionalmente, un `pediment`. Sus dimensiones derivan
del opening; los parámetros están juntos en `facade_composition.PORTAL`.
Se rechaza el conjunto si no cabe horizontal o verticalmente, sin escala
silenciosa. Los prefabs y meshes son los existentes. El relief global sigue
su pasada única; su cornisa no se duplica.

Solo Metro: `build_metro_motif.py` lee `after_bay_groups` y escribe
`lotes/1138323_casona_amarilla_esquina/after_monumental_portal/`.
La plancha `review_all_views.jpg` presenta PHOTO | AFTER BayGroup | AFTER
MONUMENTAL MOTIF en las cinco cámaras originales. Ocupación, masa, cubiertas,
cercos y semillas son las mismas; validación de envolvente pasó.

Revisión visual: en las vistas frontal y oblicuas de la fachada larga aparece
el arco en la puerta central, flanqueado por pilastras, marco profundo y
remate local. El centro se distingue mejor de las ventanas laterales. La
fachada corta de esquina no cambia. El pediment del portal es pequeño y plano:
no reproduce la composición histórica alta de la fotografía. No se añadieron
otros motifs ni una geometría específica por edificio.

Tests específicos: `tests/test_architectural_motifs.py`; cubren ocho contratos
solicitados, replace, targets inválidos, schema/roundtrip y pediment opcional.
Los 21 fingerprints y planes resueltos preexistentes permanecen idénticos
cuando `motifs=()`.
