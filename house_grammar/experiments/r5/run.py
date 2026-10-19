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

from shapely.geometry import Point, Polygon

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
    return result


def audit(name, plan):
    data = plan.to_dict()
    roofs = plan_roofs(plan)
    enclosed = {row['floor'] for row in data['massing']['storeys'] if row['kind'] == 'enclosed'}
    assert roofs, f'{name}: an enclosed building has no roof'
    assert {r['floor'] for r in roofs} <= enclosed, f'{name}: a roof floats over no storey'
    style = data['request']['building'].get('style', 'republicano')
    top = max(r['floor'] for r in roofs)
    assert next(r for r in roofs if r['floor'] == top)['design']['form'] == STYLE_FORM[style], \
        f'{name}: the top roof leaves its language form'
    for roof in roofs:
        assert roof['faces'], f'{name}: {roof["id"]} has no face'
        assert all(Polygon(f['polygon'], f['holes']).is_valid for f in roof['faces'])
        if roof['floor'] < top:
            assert roof['design']['form'] == 'flat', f'{name}: a ledge is not a flat terrace'
    if any(c['base_z_m'] > 0 for c in data.get('crowns', ())):
        main = next(r for r in roofs if r['floor'] == top)
        assert main['junction'] == 'behind', f'{name}: the fronton is not met behind'
        assert main['wall_joints'], f'{name}: the fronton junction is not flashed'
    envelope = _street_envelope(data['request']['context'])
    mesh = materialize_roofs(plan)
    allowed = envelope.buffer(.2, join_style=2)
    for vertex in mesh.vertices:
        assert allowed.contains(Point(vertex[0], vertex[1])), f'{name}: roof outside the envelope'
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
            faces=report['roofs']['faces'], watertight=report['audit']['watertight'],
            semantics=report['roofs']['semantics']))
        print(f'{name}: roofs {manifest[-1]["roofs"]} faces {report["roofs"]["faces"]} '
              f'watertight {manifest[-1]["watertight"]}')
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()
