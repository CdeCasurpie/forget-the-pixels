"""Render the R5 bank: roofs and eaves drawn from the catalog.

    PYTHONPATH=house_grammar/src python3 house_grammar/experiments/r5/run.py \
        --output /tmp/opencode/r5-review

The output directory must not exist. The R4 images are untouched.

Every case re-uses the exterior route. R5 slabs each exposed storey top: the
top floor takes its language's roof, a setback ledge becomes a flat terrace,
the eave overhangs the sidewalk but stays flush at the party walls, a plain
language raises a capped parapet, and a fronton is met behind with flashing.
"""
import argparse
import json
from pathlib import Path

from shapely.geometry import Point, Polygon, shape

from planning.envelope import plan_envelope
from planning.envelope_export import export_envelope
from planning.roof_catalogue import materialize_roofs
from planning.roof_plan import _street_envelope, plan_roofs

STYLE_FORM = {'republicano': 'gable', 'barroco': 'hip', 'clasico': 'hip',
              'madera': 'gable', 'moderno': 'flat'}


def _case(style='republicano', levels=(0, 3.2, 6.2), operations=()):
    return dict(version='intent-v1', seed=17,
                context=dict(parcel=[[0, 0], [11, 0], [11, 18], [0, 18]],
                             fronts={'street': 0}, levels_m=list(levels)),
                building=dict(profile='barranco_residential', style=style,
                              operations=list(operations)))


def cases():
    result = {}
    for style in STYLE_FORM:
        result[f'roof_{style}'] = _case(style)
    result['setback_ledge'] = _case(operations=[dict(id='sb', kind='setback', body='main',
                                                     front='street', floors=[3], depth='medium')],
                                    levels=(0, 3.2, 6.2, 9.4))
    result['crowned_roof'] = _case(operations=[dict(id='c0', kind='crown', body='main',
                                                    front='street')])
    result['tall_house'] = _case(style='barroco', levels=(0, 3.2, 6.2, 9.4))
    result['azotea_moderno'] = _case(style='moderno')
    explicit = _case(style='moderno')
    explicit['building']['roof'] = dict(objects=['water_tank', 'laundry'])
    result['azotea_objects'] = explicit
    absent = _case(style='moderno')
    absent['building']['roof'] = dict(objects=[])
    result['azotea_absent'] = absent
    slab = _case(style='republicano')
    slab['building']['roof'] = dict(cover='slab')
    result['slab_republicano'] = slab
    mixed = _case(style='moderno')
    mixed['building']['roof'] = dict(cover='mixed', objects=[])
    result['tile_band_moderno'] = mixed
    tile = _case(style='moderno')
    tile['building']['roof'] = dict(cover='tile')
    result['tile_moderno'] = tile
    patio = _case(style='republicano', operations=[dict(id='patio', kind='courtyard', body='main')])
    patio['context']['parcel'] = [[0, 0], [14, 0], [14, 20], [0, 20]]
    result['courtyard'] = patio
    garden = _case(style='republicano')
    garden['building']['site'] = dict(front_space=dict(front='street', depth='medium', use='garden'))
    result['front_garden'] = garden
    driveway = _case(style='republicano')
    driveway['building']['site'] = dict(front_space=dict(front='street', depth='medium', use='driveway'))
    result['front_driveway'] = driveway
    balcony = _case(style='republicano', operations=[dict(id='bal', kind='balcony',
                              body='main', front='street', floors=[2], width='wide', depth='medium')])
    balcony['building']['site'] = dict(front_space=dict(front='street', depth='medium', use='garden'))
    result['planted_balcony'] = balcony
    wing = _case(style='republicano', levels=(0, 3.2, 6.2, 9.4))
    wing['context']['parcel'] = [[0, 0], [14, 0], [14, 20], [0, 20]]
    wing['building']['bodies'] = [dict(id='main', floors=[1, 2, 3]),
                                  dict(id='wing', floors=[1], position='rear', width='narrow')]
    wing['building']['roof'] = dict(cover='mixed')
    result['secondary_wing'] = wing
    shade = _case(style='moderno')
    shade['building']['roof'] = dict(shade=True)
    result['azotea_shade'] = shade
    return result


def audit(name, plan):
    data = plan.to_dict()
    roofs = plan_roofs(plan)
    enclosed = {row['floor'] for row in data['massing']['storeys'] if row['kind'] == 'enclosed'}
    assert roofs, f'{name}: an enclosed building has no roof'
    assert {r['floor'] for r in roofs} <= enclosed, f'{name}: a roof floats over no storey'
    style = data['request']['building'].get('style', 'republicano')
    controls = data['request']['building'].get('roof', {}) or {}
    top = max(r['floor'] for r in roofs)
    main = next(r for r in roofs if r['floor'] == top)
    if 'cover' not in controls:
        assert main['design']['form'] == STYLE_FORM[style], \
            f'{name}: the top roof leaves its language form'
    for roof in roofs:
        assert roof['faces'], f'{name}: {roof["id"]} has no face'
        assert all(Polygon(f['polygon'], f['holes']).is_valid for f in roof['faces'])
        body_top = max(r['floor'] for r in data['massing']['storeys']
                       if r['kind'] == 'enclosed' and r['body'] == roof['body'])
        if roof['floor'] < body_top:
            assert roof['design']['form'] == 'flat', f'{name}: a ledge is not a flat terrace'
        kinds = [p['kind'] for p in roof['props']]
        assert kinds.count('stair_bulkhead') <= 1, f'{name}: the stair head is doubled'
        if roof['design']['form'] == 'flat':
            field = Polygon(roof['support'], roof.get('support_holes', ()))
            for prop in roof['props']:
                assert field.buffer(1e-6).contains(Point(*prop['position'])), \
                    f'{name}: {prop["kind"]} floats beyond the azotea'
        for hole in roof.get('support_holes', ()):
            assert Polygon(hole).area > 1., f'{name}: collapsed courtyard hole'
    if (data['request']['building'].get('roof', {}) or {}).get('objects') == []:
        assert all(not r['props'] for r in roofs), f'{name}: explicit absence ignored'
    shade_requested = (data['request']['building'].get('roof', {}) or {}).get('shade', False)
    assert sum(bool(r.get('shade')) for r in roofs) == int(shade_requested), \
        f'{name}: explicit roof shade ignored or duplicated'
    for roof in roofs:
        shade = roof.get('shade')
        if shade:
            cover = Polygon(shade['support'])
            assert Polygon(roof['support'], roof.get('support_holes', ())).covers(cover)
            assert shade['datum_m']-shade['post_base_m'] >= 2.
            for prop in roof['props']:
                assert not cover.intersects(Point(*prop['position'])), \
                    f'{name}: canopy collides with roof equipment'
    if any(c['base_z_m'] > 0 for c in data.get('crowns', ())):
        assert main['junction'] == 'behind', f'{name}: the fronton is not met behind'
        assert main['wall_joints'], f'{name}: the fronton junction is not flashed'
    envelope = _street_envelope(data['request']['context'])
    mesh = materialize_roofs(plan)
    allowed = envelope.buffer(.2, join_style=2)
    for vertex in mesh.vertices:
        assert allowed.contains(Point(vertex[0], vertex[1])), f'{name}: roof outside the envelope'
    free = shape(data['massing']['site']['free'])
    for prop in data['outdoor_details']:
        footprint = shape(prop['footprint'])
        if 'space_id' in prop:
            space = next(s for row in data['massing']['storeys']
                         for s in row.get('spaces', ()) if s['id'] == prop['space_id'])
            assert shape(space['geometry']).covers(footprint), f'{name}: planter leaves balcony'
            door = next(o for o in data['openings'] if o.get('access_for') == space['id'])
            assert footprint.distance(shape(door['geometry'])) >= .55-1e-6, \
                f'{name}: planter blocks a balcony door'
        else:
            assert free.covers(footprint), f'{name}: planter outside free ground'
            for route in data['site']['routes']:
                passage = shape(route['geometry'])
                assert footprint.distance(passage) >= .45-1e-6, \
                    f'{name}: planter blocks an access'
    return data, roofs, mesh


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = []
    for name, request in cases().items():
        plan = plan_envelope(request)
        data, roofs, mesh = audit(name, plan)
        report = export_envelope(plan, output/name, preview=True)
        manifest.append(dict(
            name=name,
            roofs=[(r['floor'], r['design']['form'], r['design']['covering'], r['junction'])
                   for r in roofs],
            props=[[p['kind'] for p in r['props']] for r in roofs],
            shade=[r['id'] for r in roofs if r.get('shade')],
            faces=report['roofs']['faces'], watertight=report['audit']['watertight'],
            dressing_faces=report['dressings']['faces'],
            outdoor_faces=report['outdoor_details']['faces'],
            semantics=report['roofs']['semantics']))
        print(f'{name}: roofs {manifest[-1]["roofs"]} props {manifest[-1]["props"]} '
              f'faces {report["roofs"]["faces"]} dressing {report["dressings"]["faces"]} '
              f'outdoor {report["outdoor_details"]["faces"]} '
              f'watertight {manifest[-1]["watertight"]}')
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()
