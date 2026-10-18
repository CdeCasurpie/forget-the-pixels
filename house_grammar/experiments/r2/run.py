"""Render a small R2 bank: actual exterior walls, stair reservation and access.

    PYTHONPATH=house_grammar/src python3 house_grammar/experiments/r2/run.py \
        --output /tmp/opencode/r2-review

The output directory must not exist. The previous R1 images are untouched.
"""
import argparse
import json
from pathlib import Path

from planning.envelope import plan_envelope
from planning.envelope_export import export_envelope


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
    mixed = _base(3)
    mixed['building']['program'] = {'use': 'mixed', 'residential': 'multi_family'}
    office = _base(3)
    office['building']['program'] = {'use': 'office'}
    balcony = _base()
    balcony['building']['site'] = {'front_space': {'front': 'street', 'depth': 'medium'}}
    balcony['building']['operations'] = [dict(id='bal', kind='balcony', body='main',
                                               front='street', floors=[2])]
    courtyard = _base(2, 16., 22.)
    courtyard['building']['operations'] = [dict(id='patio', kind='courtyard', body='main')]
    setback = _base(3)
    setback['building']['operations'] = [dict(id='upper', kind='setback', body='main',
                                               front='street', floors=[3])]
    corner = _base(2)
    corner['context']['fronts']['side'] = 1
    corner['building']['organization'] = 'corner'
    vacant = _base(2)
    vacant['building']['program'] = {'use': 'residential', 'condition': 'weathered',
                                     'occupancy': 'vacant'}
    fenced_commerce = _base(1)
    fenced_commerce['building']['program'] = {'use': 'commercial'}
    fenced_commerce['building']['site'] = {
        'front_space': {'front': 'street', 'depth': 'medium'},
        'fence': {'front': 'street', 'form': 'open'}}
    return dict(single_family=single, multi_family=multi, commerce=commerce,
                mixed_use=mixed, office=office, balcony_access=balcony,
                courtyard=courtyard, upper_setback=setback, corner=corner,
                vacant=vacant, commerce_with_fence=fenced_commerce)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = []
    for name, request in cases().items():
        plan = plan_envelope(request)
        spaces = [s for row in plan.massing['storeys'] for s in row.get('spaces', [])
                  if s['kind'] in ('balcony', 'loggia', 'portico', 'vestibule')]
        if any(sum(op['access_for'] == s['id'] for op in plan.openings) != 1 for s in spaces):
            raise ValueError(f'{name}: transitable space lacks exactly one facade door')
        if any(part['kind'] == 'partition' for part in plan.parts):
            raise ValueError(f'{name}: an interior partition was emitted')
        export_envelope(plan, output/name, preview=True)
        manifest.append(dict(name=name, doors=sum(o['kind'] != 'window' for o in plan.openings),
                             windows=sum(o['kind'] == 'window' for o in plan.openings),
                             sectors=len(plan.facade['sectors']),
                             floor_types=len(plan.facade['floor_types']),
                             partitions=0, balcony_accesses=len(spaces),
                             fence_intent=plan.program['fence']))
        print(f'{name}: {manifest[-1]["doors"]} doors, {manifest[-1]["windows"]} windows')
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()
