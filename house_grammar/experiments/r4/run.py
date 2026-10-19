"""Render the R4 bank: catalogue fence, street access and anchored fronton.

    PYTHONPATH=house_grammar/src python3 house_grammar/experiments/r4/run.py \
        --output /tmp/opencode/r4-review

The output directory must not exist. The output tree of R3 is untouched.

Every case re-uses the exterior route. R4 adds: a fence whose *form* is a
physical axis independent of the local style, an explicit absence respected, a
pedestrian gate aligned to the building entrance, a shared cochera that adds no
second pedestrian leaf, exterior routes kept inside the free ground, fence
remates (coping and a supported portal roof) and a fronton anchored to its
reserved sector axes rather than a fixed triangle centred on the facade.
"""
import argparse
import json
from pathlib import Path

from shapely.geometry import LineString, Point, shape

from planning.envelope import plan_envelope
from planning.envelope_export import export_envelope
from planning.site_plan import ACCESS_WIDTH, GATE_WIDTH


def _base(floors=2, width=11., depth=18., style=None):
    building = dict(profile='barranco_residential', organization='compact')
    if style:
        building['style'] = style
    return dict(version='intent-v1', seed=17,
                context=dict(parcel=[[0, 0], [width, 0], [width, depth], [0, depth]],
                             fronts={'street': 0},
                             levels_m=[round(3.2*i, 2) for i in range(floors+1)]),
                building=building)


def cases():
    result = {}
    for style in ('republicano', 'clasico', 'barroco', 'moderno', 'madera'):
        for form in ('solid', 'open', 'base_and_rail', 'partial'):
            case = _base(style=style)
            case['building']['site'] = dict(
                fence=dict(front='street', form=form, height='high', style=style, cap='tile'))
            result[f'{style}_{form}'] = case
    absent = _base()
    absent['building']['site'] = dict(fence=False)
    result['no_fence'] = absent
    garden = _base()
    garden['building']['site'] = dict(front_space=dict(front='street', depth='medium'))
    result['front_garden'] = garden
    garage = _base()
    garage['building']['site'] = dict(fence=dict(front='street', form='open', height='high',
                                                 cap='corrugated'), garage=True)
    result['shared_cochera'] = garage
    garage_only = _base()
    garage_only['building']['site'] = dict(fence=dict(front='street', form='solid', height='high'),
                                           garage=True, door=False)
    result['cochera_only'] = garage_only
    corner = _base(width=9.)
    corner['context']['parcel'] = [[0, 0], [9, 0], [9, 14], [0, 14]]
    corner['building']['site'] = dict(fence=dict(front='street', form='base_and_rail',
                                                 height='low', style='republicano'))
    result['corner_lot'] = corner
    for style in ('republicano', 'clasico', 'barroco', 'moderno'):
        case = _base(style=style)
        case['building']['operations'] = [dict(id='crown0', kind='crown', body='main',
                                               front='street')]
        result[f'crown_{style}'] = case
    return result


def _free(data):
    return shape(data['massing']['site']['free'])


def audit(name, plan):
    data = plan.to_dict()
    site = data['site']
    fence = site['fence']
    if fence is None:
        if site['gates']:
            raise ValueError(f'{name}: gates without a fence')
    else:
        line = shape(fence['geometry'])
        length = line.length
        intervals = sorted(tuple(g['interval_m']) for g in site['gates'])
        for low, high in intervals:
            if low < -1e-6 or high > length+1e-6:
                raise ValueError(f'{name}: a gate leaves the fence run')
        for (a0, a1), (b0, b1) in zip(intervals, intervals[1:]):
            if b0-a1 < .2-1e-6:
                raise ValueError(f'{name}: gates share a pier')
        entrances = [o for o in data['openings'] if o['kind'] == 'entrance']
        pedestrian = next((g for g in site['gates'] if g['kind'] == 'pedestrian'), None)
        if entrances and pedestrian is not None:
            u = line.project(shape(pedestrian['geometry']).centroid)
            v = line.project(shape(entrances[0]['geometry']).centroid)
            if abs(u-v) > 1.2:
                raise ValueError(f'{name}: the pedestrian gate is not in front of its door')
    free = _free(data)
    for access in site['accesses']:
        if access['clear_width_m'] < (.75 if access['kind'] == 'pedestrian' else 2.10)-1e-6:
            raise ValueError(f'{name}: {access["id"]} has insufficient clearance')
    for route in site['routes']:
        footprint = shape(route['geometry'])
        if not footprint.is_empty and not free.buffer(1e-5).covers(footprint):
            raise ValueError(f'{name}: {route["id"]} leaves the free ground')
        if route['width_m'] != ACCESS_WIDTH[route['kind']]:
            raise ValueError(f'{name}: {route["id"]} has an unexpected width')
    for gate in site['gates']:
        if abs(gate['width_m']-GATE_WIDTH[gate['kind']]) > 1e-6:
            raise ValueError(f'{name}: {gate["id"]} has an unexpected width')
    for crown in data['crowns']:
        host = next(s for row in data['massing']['storeys'] for s in row.get('surfaces', [])
                    if s['id'] == crown['host_surface_id'])
        line = LineString(host['line'])
        if crown['width_m'] >= line.length:
            raise ValueError(f'{name}: {crown["id"]} blindly spans the whole panel')
        floor = max(o['floor'] for o in data['openings'])
        tops = [o['top_m'] for o in data['openings']
                if o['floor'] == floor and o['surface'] == crown['host_surface_id']]
        if tops and crown['base_z_m'] < max(tops)-1e-6:
            raise ValueError(f'{name}: {crown["id"]} intersects a window of its sector')
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = []
    for name, request in cases().items():
        plan = plan_envelope(request)
        data = audit(name, plan)
        report = export_envelope(plan, output/name, preview=True)
        manifest.append(dict(
            name=name,
            fence=None if data['site']['fence'] is None else data['site']['fence']['form'],
            height_m=None if data['site']['fence'] is None else data['site']['fence']['height_m'],
            gates=[g['kind'] for g in data['site']['gates']],
            accesses=[a['kind'] for a in data['site']['accesses']],
            transitions=[r['transition'] for r in data['site']['routes']],
            decisions=[d['path'] for d in data['site']['decisions']],
            crowns=[(c['design']['family'], round(c['width_m'], 2)) for c in data['crowns']],
            site_faces=report['site']['faces'], crown_faces=report['crowns']['faces'],
            site_semantics=report['site']['semantics'],
            watertight=report['audit']['watertight']))
        print(f'{name}: fence {manifest[-1]["fence"]} gates {manifest[-1]["gates"]} '
              f'crowns {manifest[-1]["crowns"]} watertight {manifest[-1]["watertight"]}')
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()
