"""1138209_casona_amarilla_galeria: solo su masa y su envio directo al generador."""
import json
from pathlib import Path

# --- Lo unico que describe la masa ---
MASA = {'components': [{'id': 'street_front',
                 'kind': 'enclosed',
                 'levels_m': [0.0, 3.35, 6.9],
                 'region': {'depth': [0.0, 1.0],
                            'depth_m': [0.0, 3.8],
                            'fit': 'parcel',
                            'front_edge': 4,
                            'u': [0.0, 0.44],
                            'width_reference': 'edge'},
                 'roof': {'kind': 'flat', 'parapet_m': 0.0},
                 'slab_m': 0.18,
                 'support': {'column_width_m': 0.24,
                             'inset_m': 0.4,
                             'kind': 'bearing',
                             'max_cantilever_m': 0.0,
                             'spacing_m': 4.0}},
                {'id': 'street_rear',
                 'kind': 'enclosed',
                 'levels_m': [0.0, 3.35, 6.9],
                 'region': {'depth': [0.0, 1.0],
                            'depth_m': [3.8, 15.5],
                            'fit': 'parcel',
                            'front_edge': 4,
                            'u': [0.0, 0.44],
                            'width_reference': 'edge'},
                 'roof': None,
                 'slab_m': 0.18,
                 'support': {'column_width_m': 0.24,
                             'inset_m': 0.4,
                             'kind': 'bearing',
                             'max_cantilever_m': 0.0,
                             'spacing_m': 4.0}},
                {'id': 'garden_front',
                 'kind': 'enclosed',
                 'levels_m': [0.0, 3.15, 6.35],
                 'region': {'depth': [0.0, 1.0],
                            'depth_m': [2.35, 7.0],
                            'fit': 'parcel',
                            'front_edge': 4,
                            'u': [0.44, 1.0],
                            'width_reference': 'edge'},
                 'roof': {'kind': 'flat', 'parapet_m': 0.0},
                 'slab_m': 0.18,
                 'support': {'column_width_m': 0.24,
                             'inset_m': 0.4,
                             'kind': 'bearing',
                             'max_cantilever_m': 0.0,
                             'spacing_m': 4.0}},
                {'id': 'garden_rear',
                 'kind': 'enclosed',
                 'levels_m': [0.0, 3.15, 6.35],
                 'region': {'depth': [0.0, 1.0],
                            'depth_m': [7.0, 15.5],
                            'fit': 'parcel',
                            'front_edge': 4,
                            'u': [0.44, 1.0],
                            'width_reference': 'edge'},
                 'roof': None,
                 'slab_m': 0.18,
                 'support': {'column_width_m': 0.24,
                             'inset_m': 0.4,
                             'kind': 'bearing',
                             'max_cantilever_m': 0.0,
                             'spacing_m': 4.0}}]}

# Parcela y frentes del lote (dato catastral, no geometria inventada).
PARCELA = [[1.587, 0.0], [0.0, 19.748], [17.493, 21.425], [19.431, 1.625], [4.15, 0.187]]
FRENTES = [1]
FAMILIA = 'galeria_madera'
COLOR = [0.85, 0.82, 0.67]
TECHO = {'kind': 'flat', 'parapet_m': 0.0, 'slope_deg': None}
CUBIERTAS = [dict(id=name+'_roof',mass_ref=name+':0',design=dict(
    form='shed',covering='curved_tile',slope_deg=slope,
    rotation_deg=-84.52396504632391,detail='full',
    eave=dict(kind='clean',overhang_m=0.,fascia=False)))
    for name,slope in [('street_front',35.),('garden_front',20.)]]


def _componente(c):
    region = dict(c["region"])
    region.setdefault("depth", [0., 1.])
    return dict(id=c["id"], region=region, levels_m=c["levels_m"], kind=c["kind"], cutouts=[],
        support=dict(c.get("support") or dict(kind="bearing", spacing_m=4., column_width_m=.25, inset_m=.4, max_cantilever_m=0.)),
        facade=None, faces=[], roof=c.get("roof"), slab_m=c.get("slab_m", .18), zones=[])


def build_request():
    """Envuelve MASA en el request minimo valido: fachada ciega, sitio vacio."""
    return dict(
        context=dict(parcel=PARCELA, fronts=FRENTES, crs="EPSG:32718",
                     metric_origin=[0., 0., 0.], locked_height_m=None),
        theta=dict(schema_version="0.3", height_m=None, floors=None, family=FAMILIA,
            massing=dict(components=[_componente(c) for c in MASA["components"]], parcel_tolerance_m=0.),
            facade=dict(mode="explicit", openings=[], projections=[], material_regions=[]), facades=[],
            roof=dict(kind=TECHO["kind"], parapet_m=TECHO["parapet_m"], slope_deg=TECHO.get("slope_deg"), props=[]), roofs=[],
            site=dict(fence="none", garden=False, runs=[], zones=[]),
            primary_color=COLOR, side_material="plaster", masses=None, materials=[],
            finish=None, roof_bodies=[], roof_assemblies=CUBIERTAS),
        nuisance=dict(seed=12, curtains=False),
        config=dict(implementation="theta-candidate-v0", grammar_reference="grammar-v1.0",
                    completion_policy="conservative-0.2", detail=3),
        observations=[], evidence={})


def generar(salida='masa_1138209.glb'):
    import sys
    sys.path.insert(0, "src")
    from shapely.geometry import Polygon
    from domain.theta import from_json
    from domain.architecture import ParcelContext
    from modeling.grammar import street_envelope
    from modeling.validation import validate_mesh
    from modeling.exporters.glb_exporter import export_glb
    from pipeline.theta import reconstruct
    req = from_json(json.dumps(build_request()))
    res = reconstruct(req)
    parcel = Polygon(res.resolved.context.parcel)
    val = validate_mesh(res.mesh, parcel, envelope=street_envelope(
        ParcelContext(res.resolved.context.parcel, explicit_fronts=res.resolved.context.fronts)))
    out = Path(__file__).with_name("mass_only")
    out.mkdir(exist_ok=True)
    glb = out / salida
    export_glb(res.mesh, glb)
    print(glb, val["envelope_test"], len(res.mesh.faces), "triangulos,",
          len(res.resolved.walls), "muros,",
          sum(len(w.facade.openings) for w in res.resolved.walls), "vanos")


if __name__ == "__main__":
    import sys
    out = Path(__file__).with_name("mass_only")
    out.mkdir(exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "--generar":
        generar()
    else:
        f = out / 'masa_1138209.json'
        f.write_text(json.dumps(MASA, indent=2) + "\n")
        print(f.read_text())
