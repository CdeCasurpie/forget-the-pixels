"""1137619_banco_neoclasico: solo su masa y su envio directo al generador."""
import json
from pathlib import Path

# --- Lo unico que describe la masa ---
MASA = {'components': [{'id': 'bank',
                 'kind': 'enclosed',
                 'levels_m': [0.0, 5.25],
                 'region': {'depth': [0.0, 1.0],
                            'depth_m': None,
                            'fit': 'parcel',
                            'front_edge': 7,
                            'u': [0.0, 1.0],
                            'width_reference': 'parcel'},
                 'roof': None,
                 'slab_m': 0.18,
                 'support': {'column_width_m': 0.25,
                             'inset_m': 0.4,
                             'kind': 'bearing',
                             'max_cantilever_m': 0.0,
                             'spacing_m': 4.0}}]}

# Parcela y frentes del lote (dato catastral, no geometria inventada).
PARCELA = [[6.455, 0.0], [0.0, 20.597], [23.003, 27.847], [26.805, 25.633], [28.542, 7.249], [28.554, 7.124], [9.474, 0.954], [8.455, 0.625]]
FRENTES = [1, 2, 3]
FAMILIA = 'republicano'
COLOR = [0.39, 0.41, 0.39]
TECHO = {'kind': 'flat', 'parapet_m': 0.06, 'slope_deg': None}


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
            finish=None, roof_bodies=[]),
        nuisance=dict(seed=12, curtains=False),
        config=dict(implementation="theta-candidate-v0", grammar_reference="grammar-v1.0",
                    completion_policy="conservative-0.2", detail=3),
        observations=[], evidence={})


def generar(salida='masa_1137619.glb'):
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
        f = out / 'masa_1137619.json'
        f.write_text(json.dumps(MASA, indent=2) + "\n")
        print(f.read_text())
