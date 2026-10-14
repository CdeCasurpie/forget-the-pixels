"""Banco neoclasico 1137619: reconstruccion nueva desde cero.

Solo usa las 5 fotos *_lot.jpg como evidencia visual y la parcela catastral
como apoyo metrico. No reutiliza ningun theta de etapas anteriores.
Dos fases: (1) resuelve la masa y descubre los bordes reales; (2) asigna
vanos, pilastras y carteles por borde con aserciones geometricas.
Estilo clasico: pilastras de panel, entablamento con dentellones, parapeto
con tapa, rejas diamante, portada vidriada de esquina y zocalo de piedra.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path[:0] = ['src', 'steps/step22_massing_before_after']

import geopandas as gpd
import numpy as np
from domain.theta import from_json, canonical
from pipeline.theta import reconstruct
from modeling.theta import resolve_theta
from modeling.validation import validate_mesh
from modeling.exporters.glb_exporter import export_glb
from domain.architecture import ParcelContext
from modeling.grammar import street_envelope
from shapely.geometry import Polygon
from build_after import render_case
from build_lot_before import fingerprint

LOT_ID = 1137619
OUT = HERE / 'gramatica_nueva'
WALL_H = 4.5


def op(kind, u, v, w, h, prefab='slim_window', **kw):
    return dict(kind=kind, u_m=round(u, 3), v_m=v, width_m=round(w, 3),
                height_m=h, prefab=prefab, **kw)


def pr(kind, u, v, w, h, d, slot='frame', **kw):
    return dict(kind=kind, u_m=round(u, 3), v_m=v, width_m=round(w, 3),
                height_m=h, depth_m=d, material_slot=slot, **kw)


def member(i, edge, u):
    return dict(id=f'pilastra_{i}', mass_ref='bank:0', edge=edge, u_m=u,
                bottom_m=.5, height_m=3.4, width_m=.34, depth_m=.16,
                design=dict(style='clasico', variant='panel_pilaster', material='frame'))


def base_theta(parcel):
    comp = dict(id='bank', region=dict(front_edge=5, u=[0., 1.], depth=[0., 1.],
                                       depth_m=None, fit='parcel', width_reference='parcel'),
                levels_m=[0, WALL_H], roof=dict(kind='flat', parapet_m=.85),
                facade=None, faces=[], zones=[])
    return dict(
        schema_version='0.3', architectural_style='clasico', family='neoclasico_esquina',
        massing=dict(pattern='composition', components=[comp], parcel_tolerance_m=.2),
        facade=dict(mode='explicit', openings=[], projections=[], material_regions=[]),
        facades=[],
        roof=dict(kind='flat', parapet_m=.85, props=[]),
        site=dict(fence='none', garden=False, runs=[]),
        trim=dict(cornice=dict(enabled=False),
                  plinth=dict(design='stepped', height_m=.45, relief_m=.03, material='stone')),
        primary_color=[.55, .57, .52], side_material='plaster',
        materials=[dict(slot='frame', template='plaster', color=[.93, .93, .89]),
                   dict(slot='stone', template='stone', color=[.42, .43, .41]),
                   dict(slot='metal', template='metal', color=[.10, .16, .22]),
                   dict(slot='glass', template='glass', color=[.30, .42, .42]),
                   dict(slot='sign', template='plaster', color=[.25, .27, .26])])


def discover(parcel, ox, oy):
    r = dict(context=dict(parcel=parcel, fronts=[3, 4, 5, 6, 7], crs='EPSG:32718',
                          metric_origin=[ox, oy, 0.], locked_height_m=None),
             theta=base_theta(parcel), nuisance=dict(seed=7, curtains=False))
    req = from_json(json.dumps(r))
    res = resolve_theta(req.context, req.theta)
    walls = {}
    for w in res.walls:
        n = tuple(np.round(w.facade.normal_xy, 3))
        walls[w.edge] = dict(L=round(w.facade.width_m, 2), n=n,
                             a=tuple(np.round(w.facade.vertex_a, 2)),
                             b=tuple(np.round(w.facade.vertex_b, 2)))
    south = [e for e, w in walls.items() if w['L'] > 15 and w['n'][1] < -.7]
    assert len(south) == 1, walls
    east = sorted(e for e, w in walls.items()
                  if w['L'] > 2.5 and w['n'][0] > .7 and w['a'][1] < 20)
    assert len(east) == 2, walls
    assert abs(sum(walls[e]['L'] for e in east) - 18.46) < .2, walls
    assert abs(walls[south[0]]['L'] - 20.04) < .2, walls
    # Tramos colineales este, de sur a norte.
    east = sorted(east, key=lambda e: walls[e]['a'][1])
    north = [e for e, w in walls.items() if w['L'] > 20 and w['n'][1] > .7]
    assert len(north) == 1, walls
    # Frentes en orden de parcela para el contexto: los bordes
    # descubiertos (diagonal sur + este + norte) cubren la metadata
    # (este, NE, norte) mas la diagonal probada en fotos.
    def seg_dist(p, a, b):
        a, b, p = np.asarray(a), np.asarray(b), np.asarray(p)
        t = np.clip((p - a) @ (b - a) / max(np.sum((b - a) ** 2), 1e-12), 0, 1)
        return float(np.linalg.norm(a + t * (b - a) - p))
    ring = res.masses[0].footprint
    owner = {}
    for j, (a, b) in enumerate(zip(ring, ring[1:] + ring[:1])):
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        owner[j] = next(i for i in range(len(parcel))
                        if seg_dist(mid, parcel[i], parcel[(i + 1) % len(parcel)]) < 1e-2)
    fronts = sorted({owner[e] for e in [south[0]] + east + north})
    print('frentes parcela:', fronts, flush=True)
    return south[0], east, north[0], fronts


def build():
    lots = gpd.read_file('data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    utm = [[round(x, 2), round(y, 2)]
           for x, y in lots[lots.objectid == LOT_ID].iloc[0].geometry.exterior.coords[:-1]]
    ox, oy = min(x for x, _ in utm), min(y for _, y in utm)
    parcel = [[round(x - ox, 2), round(y - oy, 2)] for x, y in utm]
    edge_s, (edge_e0, edge_e1), edge_n, fronts = discover(parcel, ox, oy)
    blue_door = dict(model='auto', leaves=2, construction='glazed', leaf_material='metal',
                     frame_material='frame', portal='pilasters', portal_material='frame',
                     threshold=True, threshold_material='stone')
    diamond = dict(recess_m=.18, grille=True, grille_pattern='diamond',
                   mullion_columns=2, mullion_rows=3, sill=True)
    # Fachada sur: portada vidriada de esquina + 4 ventanas altas con reja.
    s_ops = [op('door', 16.1, .05, 1.7, 3.3, 'storefront', recess_m=.20,
                mullion_columns=2, mullion_rows=2, door=blue_door),
             *[op('window', u, 1.1, 1.6, 2.35, **diamond) for u in (1.6, 5.6, 9.6, 12.9)]]
    s_projs = [pr('moulded_surround', 15.9, .0, 2.1, 3.6, .22, 'frame', border_width_m=.20),
               pr('sign_box', 15.7, 3.98, 2.5, .36, .10, 'sign', label='BCP')]
    for w in [o for o in s_ops if o['kind'] == 'window']:
        s_projs.append(pr('moulded_surround', w['u_m'] - .14, w['v_m'] - .14,
                          w['width_m'] + .28, w['height_m'] + .28, .14, 'frame', border_width_m=.12))
    # Fachada este en dos tramos: servicio al sur + 3 ventanas altas con reja.
    e0_ops = [op('door', 1.1, .05, 1.5, 3.0, 'metal_gate', recess_m=.19,
                 door=dict(model='auto', leaves=1, construction='panelled', leaf_material='metal',
                           frame_material='frame', portal='pilasters', portal_material='frame',
                           threshold=True, threshold_material='stone')),
              op('window', 4.6, 1.1, 1.6, 2.35, **diamond),
              op('window', 8.7, 1.1, 1.6, 2.35, **diamond)]
    e1_ops = [op('window', 3.1, 1.1, 1.6, 2.35, **diamond)]
    e_projs = [pr('moulded_surround', .96, .0, 1.78, 3.3, .2, 'frame', border_width_m=.14),
               pr('sign_box', 7.9, 3.98, 2.5, .36, .10, 'sign', label='BCP')]
    for w in [o for o in e0_ops if o['kind'] == 'window']:
        e_projs.append(pr('moulded_surround', w['u_m'] - .14,
                          w['v_m'] - .14, w['width_m'] + .28, w['height_m'] + .28, .14, 'frame',
                          border_width_m=.12))
    e1_projs = []
    for w in [o for o in e1_ops if o['kind'] == 'window']:
        e1_projs.append(pr('moulded_surround', w['u_m'] - .14,
                           w['v_m'] - .14, w['width_m'] + .28, w['height_m'] + .28, .14, 'frame',
                           border_width_m=.12))
    members = [member(f's{i}', edge_s, u) for i, u in enumerate((.35, 4.0, 8.0, 11.9, 15.2, 19.35))]
    members += [member(f'e{i}', edge_e0, u) for i, u in enumerate((.35, 3.6, 7.6))]
    members += [member(f'n{i}', edge_e1, u) for i, u in enumerate((1.6, 6.1, 7.55))]
    # Fachada norte (frente segun metadata, sin fotos): mismo vocabulario,
    # sin accesos inventados.
    n_ops = [op('window', u, 1.1, 1.6, 2.35, **diamond) for u in (2., 7., 12., 17.)]
    n_projs = []
    for w in n_ops:
        n_projs.append(pr('moulded_surround', w['u_m'] - .14,
                          w['v_m'] - .14, w['width_m'] + .28, w['height_m'] + .28, .14, 'frame',
                          border_width_m=.12))
    members += [member(f'b{i}', edge_n, u) for i, u in enumerate((.35, 5.2, 10.2, 15.2, 20.2, 23.4))]
    r = dict(
        context=dict(parcel=parcel, fronts=fronts, crs='EPSG:32718',
                     metric_origin=[ox, oy, 0.], locked_height_m=None),
        theta={**base_theta(parcel),
               'facades': [dict(mass_role='bank:0', edge=edge_s,
                                 controls=dict(mode='explicit', openings=s_ops,
                                               projections=s_projs, material_regions=[])),
                            dict(mass_role='bank:0', edge=edge_e0,
                                 controls=dict(mode='explicit',
                                               openings=e0_ops, projections=e_projs, material_regions=[])),
                            dict(mass_role='bank:0', edge=edge_e1,
                                 controls=dict(mode='explicit',
                                               openings=e1_ops, projections=e1_projs, material_regions=[])),
                            dict(mass_role='bank:0', edge=edge_n,
                                 controls=dict(mode='explicit',
                                               openings=n_ops, projections=n_projs, material_regions=[]))],
                   'vertical_members': members,
                   'entablatures': [dict(id='coronacion', height_m=.60, projection_m=.24,
                                         scope='exposed', ornament='dentils')],
                   'entrances': [dict(id='ingreso', mass_ref='bank:0', edge=edge_s, opening_index=0,
                                      kind='steps', landing_m=.7, cheek_height_m=.12)]},
        nuisance=dict(seed=7, curtains=False),
        observations=[dict(view_id=p.name.removesuffix('_lot.jpg'), image_path=str(p))
                      for p in sorted(HERE.glob('*_lot.jpg'))],
        evidence={})
    req = from_json(json.dumps(r))
    res = reconstruct(req)
    ctx = res.resolved.context
    val = validate_mesh(res.mesh, Polygon(ctx.parcel),
                        envelope=street_envelope(ParcelContext(ctx.parcel, explicit_fronts=ctx.fronts)))
    assert val['envelope_test'] == 'passed', val
    OUT.mkdir(exist_ok=True)
    export_glb(res.mesh, OUT / 'building.glb')
    (OUT / 'request.json').write_text(json.dumps(r, indent=2) + '\n')
    (OUT / 'resolved_theta.json').write_text(canonical(res.resolved) + '\n')
    (OUT / 'validation.json').write_text(json.dumps(val, indent=2) + '\n')
    (OUT / 'medidas.md').write_text(
        '# Banco 1137619: medidas estimadas de fotos\n\nAltura de puerta 3.30 m '
        '(~2x escala humana 1.70), ventanas 1.10-3.45, entablamento 3.90-4.50 '
        'con dentellones, parapeto 4.50-5.35 con tapa, zocalo 0-0.45. '
        f'Muros: {len(res.resolved.walls)}, vanos: '
        f'{sum(len(w.facade.openings) for w in res.resolved.walls)}, '
        f'miembros: {len(res.resolved.vertical_members)}, '
        f'triangulos: {len(res.mesh.faces)}.\n')
    geom = lots[lots.objectid == LOT_ID].iloc[0].geometry
    poses = json.load(open('data/poses_barranco/metadata.json'))['panoramas']
    offset = json.load(open('data/cadastral_offset.json'))
    n = render_case(res, OUT, LOT_ID, geom, poses, offset, after_label='BANCO GRAMATICA NUEVA')
    (OUT / 'manifest.json').write_text(json.dumps(dict(
        lot=LOT_ID, comparisons=n, triangles=len(res.mesh.faces), validation=val,
        mesh_sha256=fingerprint(res.mesh)), indent=2) + '\n')
    print(OUT, 'VALID', val['envelope_test'], len(res.mesh.faces), n)
    (OUT / 'README.md').write_text(
        '# Banco neoclasico: gramatica nueva desde cero\n\nSolo fotos *_lot.jpg + '
        'parcela catastral. Abrir building.glb; comparativas compare_*.jpg.\n')


if __name__ == '__main__':
    build()
