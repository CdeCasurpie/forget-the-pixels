"""R5: roofs and eaves drawn from the catalog on the exposed storey tops."""
import json
from pathlib import Path

import pytest
from shapely.geometry import Point, Polygon

from domain.architectural_plan import PlanningError
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


def test_courtyard_roof_keeps_its_open_court():
    data = request(operations=[dict(id='patio', kind='courtyard', body='main')])
    data['context']['parcel'] = [[0, 0], [14, 0], [14, 20], [0, 20]]
    plan = plan_envelope(data)
    roof = plan_roofs(plan)[0]
    assert len(roof['support_holes']) == 1
    court = Polygon(roof['support_holes'][0])
    assert court.area > 1.
    assert all(not Polygon(f['polygon'], f['holes']).covers(court.representative_point())
               for f in roof['faces'])
    assert len(materialize_roofs(plan).faces) > 0


def test_a_shorter_secondary_body_gets_its_own_cover_not_the_main_terrace():
    case = Path(__file__).parents[1]/'experiments/phase0/cases/evaluation/20_complex_combination.json'
    plan = plan_envelope(json.loads(case.read_text())['request'])
    roofs = plan_roofs(plan)
    main_ledge = next(r for r in roofs if r['body'] == 'main' and r['floor'] == 1)
    wing = next(r for r in roofs if r['body'] == 'wing' and r['floor'] == 1)
    assert main_ledge['design']['form'] == 'flat'
    assert wing['design']['form'] == 'band'
    assert main_ledge['id'] != wing['id']
    assert sum(bool(r.get('shade')) for r in roofs) == 1


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


def _plan(roof, style='moderno'):
    data = request(style=style)
    if roof is not None:
        data['building']['roof'] = roof
    return plan_envelope(data)


def test_azotea_carries_its_stair_head_and_objects():
    props = plan_roofs(_plan(None))[0]['props']
    kinds = [p['kind'] for p in props]
    assert kinds.count('stair_bulkhead') == 1
    assert len(props) > 1
    names = {part['name'] for part in materialize_roofs(_plan(None)).parts}
    assert 'stair_bulkhead' in names and 'water_tank' in names


def test_explicit_roof_objects_are_respected():
    props = plan_roofs(_plan(dict(objects=['water_tank', 'laundry'])))[0]['props']
    assert {p['kind'] for p in props} <= {'water_tank', 'laundry'}
    assert props


def test_explicit_absence_of_roof_objects_is_respected():
    assert plan_roofs(_plan(dict(objects=[])))[0]['props'] == []
    names = {part['name'] for part in materialize_roofs(_plan(dict(objects=[]))).parts}
    assert not (names & {'water_tank', 'caseta_wall', 'laundry_line', 'stair_bulkhead'})


def test_roof_cover_can_force_a_slab():
    roof = plan_roofs(_plan(dict(cover='slab'), style='republicano'))[0]
    assert roof['design']['form'] == 'flat'
    assert roof['design']['parapet_m'] > 0.


def test_explicit_tile_cover_drains_even_on_a_modern_building():
    roof = plan_roofs(_plan(dict(cover='tile')))[0]
    assert roof['design']['form'] == 'shed'
    assert roof['design']['covering'] == 'curved_tile'
    assert roof['design']['parapet_m'] == 0.


def test_explicit_mixed_cover_has_a_street_tile_band_and_flat_rear():
    plan = _plan(dict(cover='mixed'))
    roof = plan_roofs(plan)[0]
    assert roof['design']['form'] == 'band'
    assert roof['design']['covering'] == 'curved_tile'
    assert any(abs(f['plane'][0])+abs(f['plane'][1]) > .01 for f in roof['faces'])
    assert any(abs(f['plane'][0])+abs(f['plane'][1]) < .01 for f in roof['faces'])
    assert len(materialize_roofs(plan).faces) > 0


def test_explicit_stair_head_only_does_not_sample_from_an_empty_vocabulary():
    props = plan_roofs(_plan(dict(objects=['stair_bulkhead'])))[0]['props']
    assert [p['kind'] for p in props] == ['stair_bulkhead']


def test_requested_shade_is_a_supported_clear_roof_canopy():
    plan = _plan(dict(shade=True))
    roof = plan_roofs(plan)[0]
    shade = roof['shade']
    footprint = Polygon(shade['support'])
    assert Polygon(roof['support']).covers(footprint)
    assert shade['datum_m']-shade['post_base_m'] > 2.
    assert all(not footprint.intersects(Point(*p['position'])) for p in roof['props'])
    names = {part['name'] for part in materialize_roofs(plan).parts}
    assert {'roof_slats', 'roof_shade_beam', 'member_shaft'} <= names


def test_explicit_absence_of_shade_stays_absent():
    assert not any(r.get('shade') for r in plan_roofs(_plan(dict(shade=False))))


def test_shade_on_a_pitched_roof_reports_a_capacity_conflict():
    with pytest.raises(PlanningError, match='roof_shade_capacity'):
        _plan(dict(shade=True), style='republicano')


def test_props_stand_on_the_roof_not_beyond_it():
    plan = _plan(None)
    spec = plan_roofs(plan)[0]
    field = Polygon(spec['support'])
    for prop in spec['props']:
        assert field.buffer(1e-6).contains(Point(*prop['position']))


def test_roof_props_are_deterministic():
    first = plan_roofs(_plan(None))[0]['props']
    second = plan_roofs(_plan(None))[0]['props']
    assert first == second


def test_occupancy_changes_do_not_rewrite_the_roof_or_its_stair_head():
    occupied = request(style='moderno')
    occupied['building']['program'] = dict(occupancy='occupied')
    vacant = request(style='moderno')
    vacant['building']['program'] = dict(occupancy='vacant')
    a, b = plan_envelope(occupied), plan_envelope(vacant)
    assert a.roofs == b.roofs
    assert a.dressings == b.dressings
