"""Render the R3 bank: joint bay sizing, family typology and catalogue reserves.

    PYTHONPATH=house_grammar/src python3 house_grammar/experiments/r3/run.py \
        --output /tmp/opencode/r3-review

The output directory must not exist. The R2 images are untouched.

Every case re-uses the R2 exterior route. R3 adds: widths taken from disjoint
window-family bands, edge margins measured from the aperture edge to the panel
end, a reserved volume for a catalogue door portal, and one catalogue piece per
opening with the very contour that was cut in the wall.
"""
import argparse
import json
from pathlib import Path

from shapely.geometry import LineString, Point, shape

from planning import catalogue_openings, openings_plan
from planning.envelope import plan_envelope
from planning.envelope_export import export_envelope

EDGE = openings_plan.WINDOW_EDGE_M
DOOR_EDGE = openings_plan.DOOR_EDGE_M


def _base(floors=2, width=12., depth=18.):
    return dict(version='intent-v1', seed=17,
                context=dict(parcel=[[0, 0], [width, 0], [width, depth], [0, depth]],
                             fronts={'street': 0},
                             levels_m=[round(3.2*i, 2) for i in range(floors+1)]),
                building=dict(profile='barranco_residential', organization='compact'))


def cases():
    single = _base()
    single['building']['program'] = {'use': 'residential', 'residential': 'single_family'}
    multi = _base(3)
    multi['building']['program'] = {'use': 'residential', 'residential': 'multi_family'}
    commerce = _base(1)
    commerce['building']['program'] = {'use': 'commercial'}
    office = _base(3)
    office['building']['program'] = {'use': 'office'}
    mixed = _base(3)
    mixed['building']['program'] = {'use': 'mixed', 'residential': 'multi_family'}
    balcony = _base()
    balcony['building']['site'] = {'front_space': {'front': 'street', 'depth': 'medium'}}
    balcony['building']['operations'] = [dict(id='bal', kind='balcony', body='main',
                                             front='street', floors=[2])]
    mixed_families = _base()
    mixed_families['building']['facades'] = [dict(
        body='main', front='street', floors=[1, 2],
        windows=dict(count=3, proportions=['horizontal', 'vertical', 'small_high']))]
    narrow_lot = _base(width=6.)
    narrow_lot['building']['facades'] = [dict(body='main', front='street', floors=[1, 2],
                                              windows=dict(count=2))]
    wide_lot = _base(width=20.)
    wide_lot['building']['facades'] = [dict(body='main', front='street', floors=[1, 2],
                                            windows=dict(count=3))]
    arches = _base()
    arches['building']['style'] = 'republicano'
    arches['building']['facades'] = [dict(
        body='main', front='street', floors=[1, 2],
        windows=dict(count=2, proportion='vertical', shape='arch', grille=True))]
    circles = _base()
    circles['building']['facades'] = [dict(
        body='main', front='street', floors=[1, 2],
        windows=dict(count=2, proportion='square', shape='circle'))]
    ellipses = _base()
    ellipses['building']['facades'] = [dict(
        body='main', front='street', floors=[1, 2],
        windows=dict(count=2, proportion='horizontal', shape='ellipse', sill=False))]
    portal_pilasters = _base()
    portal_pilasters['building']['site'] = {'door': dict(position='center',
                                                         portal='pilasters')}
    portal_columns = _base()
    portal_columns['building']['style'] = 'barroco'
    portal_columns['building']['site'] = {'door': dict(
        position='left', portal='columns', transom='glass')}
    storefront_transom = _base(1)
    storefront_transom['building']['program'] = {'use': 'commercial'}
    storefront_transom['building']['site'] = {'door': dict(position='right',
                                                           transom='open')}
    corner = _base(2)
    corner['context']['fronts']['side'] = 1
    corner['building']['organization'] = 'corner'
    weathered = _base(2)
    weathered['building']['program'] = {'use': 'residential', 'condition': 'weathered',
                                        'occupancy': 'vacant'}
    progressive = _base(3)
    progressive['building']['program'] = {'use': 'residential', 'residential': 'multi_family',
                                          'evolution': 'progressive'}
    adapted = _base(3)
    adapted['building']['program'] = {'use': 'mixed', 'residential': 'multi_family',
                                      'evolution': 'adapted'}
    return dict(single_family=single, multi_family=multi, commerce_storefront=commerce,
                office=office, mixed_use=mixed, balcony_access=balcony,
                mixed_families=mixed_families, narrow_lot=narrow_lot, wide_lot=wide_lot,
                arched_windows=arches, circular_panels=circles, elliptic_panels=ellipses,
                portal_pilasters=portal_pilasters, portal_columns=portal_columns,
                storefront_transom=storefront_transom, corner=corner,
                weathered_vacant=weathered, progressive=progressive, adapted=adapted)


def _edge_distances(plan, opening):
    hosts = {s['id']: s for row in plan.massing['storeys'] for s in row['surfaces']}
    line = LineString(hosts[opening['surface']]['line'])
    return sorted(line.project(Point(p)) for p in shape(opening['geometry']).coords), line.length


def audit(name, plan):
    """Invariants R3 must hold on every generated facade, not just in fixtures."""
    spaces = [s for row in plan.massing['storeys'] for s in row.get('spaces', [])
              if s['kind'] in ('balcony', 'loggia', 'portico', 'vestibule')]
    if any(sum(op['access_for'] == s['id'] for op in plan.openings) != 1 for s in spaces):
        raise ValueError(f'{name}: transitable space lacks exactly one facade door')
    if any(part['kind'] == 'partition' for part in plan.parts):
        raise ValueError(f'{name}: an interior partition was emitted')
    for opening in plan.openings:
        (start, end), length = _edge_distances(plan, opening)
        margin = DOOR_EDGE if opening['kind'] in ('entrance', 'vehicle_entry') else EDGE
        if start < margin-1e-6 or length-end < margin-1e-6:
            raise ValueError(f'{name}: {opening["id"]} violates the {margin} m edge margin')
        if opening['kind'] == 'window':
            low, high = openings_plan.band(opening['family'])
            if not low-1e-6 <= opening['width_m'] <= high+1e-6:
                raise ValueError(f'{name}: {opening["id"]} width leaves its band')
    for opening in plan.openings:
        if opening['kind'] != 'entrance':
            continue
        reserve = openings_plan.portal_reserve(opening.get('portal', 'none'))
        if opening['reserve_m'] < DOOR_EDGE+reserve-1e-6:
            raise ValueError(f'{name}: door portal volume is not reserved')
    mains = [o for o in plan.openings if o['family'] in ('horizontal', 'vertical', 'storefront')]
    vents = [o for o in plan.openings if o['family'] == 'small_high']
    if vents and min(o['width_m'] for o in mains) <= max(o['width_m'] for o in vents):
        raise ValueError(f'{name}: a main window is not wider than a ventilator')
    return spaces


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = []
    for name, request in cases().items():
        plan = plan_envelope(request)
        spaces = audit(name, plan)
        catalogue = catalogue_openings.materialize_openings(plan)
        semantics = sorted({part['name'] for part in catalogue.parts})
        report = export_envelope(plan, output/name, preview=True)
        windows = [o for o in plan.openings if o['kind'] == 'window']
        manifest.append(dict(
            name=name, openings=len(plan.openings),
            windows=len(windows), doors=len(plan.openings)-len(windows),
            families={f: sum(o['family'] == f for o in windows)
                      for f in sorted({o['family'] for o in windows})},
            portals=sorted({o['portal'] for o in plan.openings if o['portal'] != 'none'}),
            shapes=sorted({o['shape'] for o in windows}),
            catalogue_faces=len(catalogue.faces), catalogue_semantics=semantics,
            contoured_hosts=len(plan.contoured_walls), balcony_accesses=len(spaces),
            watertight=report['audit']['watertight'], fence_intent=plan.program['fence']))
        print(f'{name}: {manifest[-1]["doors"]} doors, {manifest[-1]["windows"]} windows, '
              f'families {manifest[-1]["families"]}, contoured {manifest[-1]["contoured_hosts"]}')
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()
