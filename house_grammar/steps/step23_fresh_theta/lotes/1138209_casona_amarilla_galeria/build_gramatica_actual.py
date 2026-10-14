"""Regenerate 1138209 with current grammar (windows, doors, trim, fences, members).

Base: fresh/request.json (massing, parcel, openings positions unchanged).
Migration only adds opt-in controls and replaces legacy plinth/cornice
projections now covered by trim. No new openings, balconies or accesses.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src'))
LOT = Path(__file__).parent

from domain.theta import from_json
from domain.architecture import ParcelContext
from modeling.grammar import street_envelope
from modeling.validation import validate_mesh
from modeling.exporters.glb_exporter import export_glb
from pipeline.theta import reconstruct
from shapely.geometry import Polygon


def migrate_opening(op):
    op = dict(op)
    op['frame_profile'] = 'auto'
    op.setdefault('frame_depth_m', 0.14)
    if op['kind'] == 'window':
        op['sill'] = True
        if op.get('grille'):
            op.setdefault('grille_spacing_m', 0.14)
    if op['kind'] == 'door':
        if op.get('prefab') == 'storefront':
            op['door'] = {'model': 'auto', 'leaves': 0,
                          'construction': 'glazed', 'portal': 'none'}
        else:  # open vestibule entrance: wooden glazed leaf, no invented portal
            op['door'] = {'model': 'auto', 'leaves': 1,
                          'construction': 'glazed', 'portal': 'none'}
    return op


def main():
    r = json.loads((LOT / 'fresh' / 'request.json').read_text())
    t = r['theta']
    t['architectural_style'] = 'republicano'
    # No global perimeter trim on this lot: the four masses share party
    # walls and pitched tile roofs, so a continuous cornice/plinth sweep has
    # no valid exposed path (verified against resolve_trims). Remates are
    # showcased on the fence plinth; walls keep their evidence projections.
    for facade in t['facades']:
        c = facade['controls']
        c['openings'] = [migrate_opening(op) for op in c.get('openings', [])]
        # Keep every evidence projection (panel plinth, denticulated
        # cornice, surrounds, sills, galleries, eave) unchanged.
        pass
    # 'reja' -> republicano high (1.65 m in photos), grey stepped base.
    for run in t['site']['runs']:
        run['kind'] = 'republicano'
        run['height_mode'] = 'high'
        run['base_height_m'] = 0.40
        run['plinth'] = {'design': 'stepped', 'height_m': 0.30,
                         'relief_m': 0.018, 'material': 'stone'}
    req = from_json(json.dumps(r))
    res = reconstruct(req)
    ctx = res.resolved.context
    val = validate_mesh(res.mesh, Polygon(ctx.parcel),
                        envelope=street_envelope(
                            ParcelContext(ctx.parcel, explicit_fronts=ctx.fronts)))
    assert val['envelope_test'] == 'passed', val
    out = LOT / 'gramatica_actual'
    out.mkdir(exist_ok=True)
    export_glb(res.mesh, out / 'building.glb')
    (out / 'request.json').write_text(json.dumps(r, indent=2) + '\n')
    (out / 'validation.json').write_text(json.dumps(val, indent=2) + '\n')
    names = sorted({p['name'] for p in res.mesh.parts})
    (out / 'semantics.txt').write_text('\n'.join(names) + '\n')
    print('triangles:', val['triangles'], 'parts:', val['parts'])
    print('has trim_cornice:', 'trim_cornice' in names,
          '| has member_shaft:', 'member_shaft' in names,
          '| has fence_ring:', 'fence_ring' in names)
    print('semantics:', ', '.join(names))


if __name__ == '__main__':
    main()
