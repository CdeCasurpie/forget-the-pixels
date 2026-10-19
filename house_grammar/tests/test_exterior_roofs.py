"""R5: roofs and eaves drawn from the catalog on the exposed storey tops."""
import json

import pytest
from shapely.geometry import Point, Polygon

from planning.envelope import plan_envelope
from planning.envelope_export import export_envelope
from planning.roof_catalogue import materialize_roofs
from planning.roof_plan import _street_envelope, plan_roofs


def request(style='republicano', operations=None, levels=(0, 3.2, 6.2)):
    return dict(version='intent-v1', seed=17,
                context=dict(parcel=[[0, 0], [11, 0], [11, 18], [0, 18]],
                             fronts={'street': 0}, levels_m=list(levels)),
                building=dict(profile='barranco_residential', style=style,
                              operations=operations or []))


def roof_area(spec):
    return sum(Polygon(f['polygon'], f['holes']).area for f in spec['faces'])


def test_every_exposed_storey_top_is_roofed():
    roofs = plan_roofs(plan_envelope(request()))
    assert len(roofs) == 1
    assert roofs[0]['floor'] == 2
    assert roofs[0]['design']['form'] == 'gable'


def test_setback_ledge_becomes_a_flat_terrace():
    operations = [dict(id='sb', kind='setback', body='main', front='street',
                       floors=[3], depth='medium')]
    roofs = plan_roofs(plan_envelope(request(operations=operations,
                                             levels=(0, 3.2, 6.2, 9.4))))
    floors = {r['floor']: r['design']['form'] for r in roofs}
    assert floors == {2: 'flat', 3: 'gable'}


@pytest.mark.parametrize('style,form', [
    ('republicano', 'gable'), ('barroco', 'hip'), ('clasico', 'hip'),
    ('madera', 'gable'), ('moderno', 'flat'),
])
def test_style_chooses_the_roof_form(style, form):
    roof = plan_roofs(plan_envelope(request(style=style)))[0]
    assert roof['design']['form'] == form
    assert roof['style'] == style


def test_plain_language_raises_a_capped_parapet():
    roof = plan_roofs(plan_envelope(request(style='moderno')))[0]
    assert roof['design']['parapet_m'] > 0.
    assert roof['design']['cap'] != 'none'


def test_roof_is_materialized_from_the_catalog():
    mesh = materialize_roofs(plan_envelope(request(style='republicano')))
    names = {part['name'] for part in mesh.parts}
    assert len(mesh.faces) > 0
    assert 'roof_substrate' in names
    assert names & {'roof_tile_piece', 'roof_flat_tile', 'roof_corrugation', 'roof_cover'}


def test_crown_is_met_behind_not_crossed():
    plain = plan_roofs(plan_envelope(request()))
    operations = [dict(id='c0', kind='crown', body='main', front='street')]
    crowned = plan_roofs(plan_envelope(request(operations=operations)))
    assert crowned[0]['junction'] == 'behind'
    assert crowned[0]['wall_joints']
    assert roof_area(crowned[0]) < roof_area(plain[0])
    names = {part['name'] for part in materialize_roofs(plan_envelope(request(operations=operations))).parts}
    assert 'roof_crown_flashing' in names


def test_roof_stays_inside_the_street_envelope():
    plan = plan_envelope(request(style='republicano'))
    envelope = _street_envelope(plan.to_dict()['request']['context'])
    mesh = materialize_roofs(plan)
    allowed = envelope.buffer(.2, join_style=2)
    assert all(allowed.contains(Point(v[0], v[1])) for v in mesh.vertices)


def test_roof_plan_is_deterministic():
    first = plan_roofs(plan_envelope(request(style='barroco')))
    second = plan_roofs(plan_envelope(request(style='barroco')))
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_export_reports_the_roofs(tmp_path):
    report = export_envelope(plan_envelope(request(style='clasico')), tmp_path/'roof')
    assert (tmp_path/'roof'/'envelope.glb').exists()
    assert report['roofs']['count'] == 1
    assert report['roofs']['faces'] > 0
    assert report['roofs']['semantics']
