"""R6 architectural calibration bank, separate from the R1–R5 cases.

    PYTHONPATH=house_grammar/src python3 house_grammar/experiments/r6/run.py \
        --output /tmp/opencode/r6-holdout

Each case exports a GLB and front/oblique views. The manifest records real
opening edge clearances, roof and component geometry budgets, balcony-door
links, access clearance and watertightness. Numerical checks do not assert
Barranco visual fidelity: human comparison to independent street photographs
 is a separate R6 acceptance step. The narrow and wide cases have already
 informed adjustments to automatic window counts; this is not an untouched
 visual holdout.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from shapely.geometry import LineString, Point, shape

from planning.envelope import plan_envelope
from planning.envelope_export import export_envelope
from planning.openings_plan import DOOR_EDGE_M, WINDOW_EDGE_M


def _base(seed, width, depth, floors, style):
    return dict(version='intent-v1', seed=seed,
                context=dict(parcel=[[0, 0], [width, 0], [width, depth], [0, depth]],
                             fronts={'street': 0},
                             levels_m=[round(3.1*i, 2) for i in range(floors+1)]),
                building=dict(profile='barranco_residential', style=style))


def cases():
    narrow = _base(601, 5.8, 17., 1, 'madera')
    narrow['building']['program'] = dict(use='residential', residential='single_family')
    casona = _base(602, 17., 23., 2, 'republicano')
    casona['building']['operations'] = [dict(id='crown', kind='crown', body='main', front='street')]
    corner = _base(603, 9.5, 16., 3, 'moderno')
    corner['context']['fronts']['side'] = 1
    corner['building']['organization'] = 'corner'
    corner['building']['roof'] = dict(objects=['water_tank', 'stair_bulkhead'], shade=True)
    multi = _base(604, 10.8, 20., 4, 'clasico')
    multi['building']['program'] = dict(use='residential', residential='multi_family')
    shop = _base(605, 8.4, 15., 1, 'moderno')
    shop['building']['program'] = dict(use='commercial')
    fenced_shop = _base(606, 12.4, 19., 2, 'republicano')
    fenced_shop['building']['program'] = dict(use='mixed')
    fenced_shop['building']['site'] = dict(
        front_space=dict(front='street', depth='medium', use='mixed'),
        fence=dict(front='street', form='base_and_rail', cap='tile'))
    progressive = _base(607, 7.6, 18., 3, 'madera')
    progressive['building']['program'] = dict(use='residential', evolution='progressive')
    progressive['building']['roof'] = dict(cover='corrugated')
    weathered = _base(608, 10.2, 18.5, 2, 'barroco')
    weathered['building']['program'] = dict(use='residential', condition='weathered',
                                           occupancy='vacant')
    occupied = deepcopy(weathered)
    occupied['building']['program']['occupancy'] = 'occupied'
    return dict(narrow_house=narrow, wide_casona=casona, modern_corner=corner,
                multifamily=multi, shop_without_fence=shop, shop_with_fence=fenced_shop,
                progressive_house=progressive, vacant_weathered=weathered,
                occupied_weathered=occupied)


def audit(name, plan):
    data = plan.to_dict()
    surfaces = {s['id']: s for row in data['massing']['storeys'] for s in row.get('surfaces', ())}
    margins = []
    for opening in data['openings']:
        host = surfaces.get(opening['surface'])
        if host is None:
            continue
        line = LineString(host['line'])
        aperture = shape(opening['geometry'])
        ends = sorted(line.project(Point(p)) for p in aperture.coords)
        left, right = ends[0], line.length-ends[-1]
        limit = WINDOW_EDGE_M if opening['kind'] == 'window' else DOOR_EDGE_M
        if opening['kind'] in ('window', 'entrance') and min(left, right) < limit-1e-5:
            raise ValueError(f'{name}: {opening["id"]} misses the {limit:.2f}m edge reserve')
        margins.append(dict(id=opening['id'], family=opening['family'],
                            width_m=opening['width_m'], left_m=round(left, 3),
                            right_m=round(right, 3)))
    balconies = [s for row in data['massing']['storeys'] for s in row.get('spaces', ())
                 if s['kind'] == 'balcony']
    if any(sum(o.get('access_for') == s['id'] for o in data['openings']) != 1 for s in balconies):
        raise ValueError(f'{name}: balcony without exactly one real facade door')
    for access in data['site']['accesses']:
        if access['clear_width_m'] < (.75 if access['kind'] == 'pedestrian' else 2.10)-1e-5:
            raise ValueError(f'{name}: blocked street access')
    if any(part['kind'] == 'partition' for part in data['parts']):
        raise ValueError(f'{name}: interior partition appeared on the public route')
    return margins


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = []
    planned = {}
    for name, request in cases().items():
        plan = plan_envelope(request)
        planned[name] = plan
        margins = audit(name, plan)
        report = export_envelope(plan, output/name, preview=True)
        components = {key: report[key]['faces'] for key in
                      ('contoured_walls', 'catalogue_openings', 'site', 'crowns',
                       'pilasters', 'roofs', 'dressings', 'outdoor_details')}
        manifest.append(dict(name=name, margins=margins,
                             crowns=report['crowns']['count'],
                             roofs=report['roofs']['count'],
                             component_faces=components,
                             detail_faces=sum(components.values()),
                             watertight=report['audit']['watertight'],
                             glb=str((output/name/'envelope.glb').relative_to(output)),
                             front=str((output/name/'front.png').relative_to(output)),
                             oblique=str((output/name/'preview.png').relative_to(output))))
        print(f'{name}: {len(margins)} openings, {report["roofs"]["faces"]} roof faces, '
              f'watertight {report["audit"]["watertight"]}')
    vacant, occupied = planned['vacant_weathered'], planned['occupied_weathered']
    for field in ('openings', 'facade', 'parts', 'roofs', 'dressings', 'crowns'):
        if getattr(vacant, field) != getattr(occupied, field):
            raise ValueError(f'occupancy variant unexpectedly changes {field}')
    for field in ('massing', 'site'):
        va, vb = getattr(vacant, field), getattr(occupied, field)
        if {k: v for k, v in va.items() if k != 'request'} != \
           {k: v for k, v in vb.items() if k != 'request'}:
            raise ValueError(f'occupancy variant unexpectedly changes {field}')
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()
