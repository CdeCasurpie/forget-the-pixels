"""R2 exterior-only route: the stair matters, invisible rooms do not."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from shapely.geometry import shape

from domain.architectural_plan import PlanningError
from planning.chart import surface_chart
from planning.envelope import plan_envelope
from planning.envelope_export import export_envelope, solids
from planning.exterior_envelope import plan_exterior_envelope


def request():
    return dict(version='intent-v1', seed=17,
                context=dict(parcel=[[0, 0], [12, 0], [12, 18], [0, 18]],
                             fronts={'F1': 0}, levels_m=[0, 3.2, 6.]),
                building=dict(profile='barranco_residential',
                              site=dict(front_space=dict(front='F1', depth='medium'))))


def narrow_request():
    r = request()
    r['context']['parcel'] = [[0, 0], [5.8, 0], [5.8, 17], [0, 17]]
    r['context']['levels_m'] = [0, 3.1]
    r['building'].pop('site')
    return r


def test_implicit_two_window_rhythm_reduces_count_before_dropping_all_bays():
    plan = plan_envelope(narrow_request())
    windows = [o for o in plan.openings if o['kind'] == 'window']
    assert len(windows) == 1
    assert windows[0]['width_m'] >= 1.
    assert any('reduced from 2 to 1' in d.get('reason', '') for d in plan.decisions)


def test_explicit_unfittable_two_window_request_still_reports_capacity():
    r = narrow_request()
    r['building']['facades'] = [dict(body='main', front='F1', floors=[1],
                                    windows=dict(count=2, proportion='vertical'))]
    with pytest.raises(PlanningError, match='window_capacity'):
        plan_envelope(r)


def test_explicit_window_on_a_panel_without_space_reports_capacity():
    r = narrow_request()
    r['context']['parcel'] = [[0, 0], [3.2, 0], [3.2, 17], [0, 17]]
    r['building']['facades'] = [dict(body='main', front='F1', floors=[1],
                                    windows=dict(count=1, proportion='vertical'))]
    with pytest.raises(PlanningError, match='window_capacity'):
        plan_envelope(r)


def test_wide_residential_front_adapts_its_bay_count_without_tiny_windows():
    r = request()
    r['context']['parcel'] = [[0, 0], [17, 0], [17, 23], [0, 23]]
    plan = plan_envelope(r)
    for floor in (1, 2):
        windows = [o for o in plan.openings if o['kind'] == 'window' and o['floor'] == floor]
        assert len(windows) == 4
        assert all(o['width_m'] >= 1. for o in windows)


def with_balcony():
    r = request()
    r['building']['operations'] = [dict(id='bal', kind='balcony', body='main',
                                         front='F1', floors=[2])]
    return r


def test_exterior_route_has_no_rooms_partitions_or_internal_doors():
    r = request(); original = deepcopy(r)
    plan = plan_envelope(r)  # the exterior-only route is the default
    assert r == original
    assert 'interior' not in plan.to_dict()
    assert plan.core['stairs']['type'] != 'GeometryCollection'
    assert shape(plan.core['stairs']).area > 2.2 * 3.
    assert not any(part['kind'] == 'partition' or 'room' in part['id'] for part in plan.parts)
    assert not any(op['surface'] is None for op in plan.openings)
    assert len([op for op in plan.openings if op['kind'] == 'entrance']) == 1
    assert [op['kind'] for op in plan.openings].count('window') == 4
    assert plan.checks['aperture_intrusion_m3'] == pytest.approx(0.)


def test_balcony_has_a_real_access_door_on_the_enclosure_wall():
    plan = plan_exterior_envelope(with_balcony())
    balconies = [space for row in plan.massing['storeys'] for space in row.get('spaces', [])
                if space['kind'] == 'balcony']
    assert len(balconies) == 1
    space = balconies[0]
    access = [op for op in plan.openings if op['access_for'] == space['id']]
    assert len(access) == 1
    door = access[0]
    assert door['kind'] == 'exterior_space'
    assert door['floor'] == 2
    assert door['sill_m'] == 0.
    assert door['width_m'] - 2 * door['frame_width_m'] >= .70
    assert shape(space['access']['geometry']).buffer(1e-6).intersects(shape(door['geometry']))
    assert len([op for op in plan.openings if op['kind'] == 'window' and op['floor'] == 2]) == 2
    assert not any(part['kind'] == 'partition' for part in plan.parts)
    assert plan.checks['aperture_intrusion_m3'] == pytest.approx(0.)


def test_chart_anchors_openings_on_the_wall_behind_the_balcony():
    plan = plan_exterior_envelope(with_balcony())
    chart = surface_chart(plan, enclosed=True)
    for op in plan.openings:
        hosts = [s for s in chart.surfaces if s.facade.edge_id == op['surface'].rsplit('/part', 1)[0]]
        assert len(hosts) == 1
        assert any(abs(w.width_m-op['width_m']) < 1e-5
                   for w in hosts[0].facade.openings)
    meshes, audit = solids(plan)
    assert meshes and audit['watertight']


def test_window_count_zero_and_site_door_false_are_respected():
    r = request()
    r['building']['site']['door'] = False
    r['building']['facades'] = [dict(body='main', front='F1', floors=[1, 2],
                                    windows=dict(count=0))]
    plan = plan_exterior_envelope(r)
    assert not plan.openings
    assert all(part['kind'] not in ('partition', 'jamb_left') for part in plan.parts)


def test_no_street_door_does_not_remove_a_required_balcony_door():
    r = with_balcony()
    r['building']['site']['door'] = False
    plan = plan_envelope(r)
    assert not any(op['kind'] == 'entrance' for op in plan.openings)
    assert len([op for op in plan.openings if op['access_for'] == 'bal/floor2']) == 1


def test_unchanged_upper_storeys_repeat_window_axes_around_one_stair():
    r = request()
    r['context']['levels_m'] = [0, 3.2, 6., 8.8]
    plan = plan_envelope(r)
    chart = surface_chart(plan, enclosed=True)
    fronts = [s for s in chart.surfaces if s.facade.is_front]
    upper = sorted((s for s in fronts if s.base_z > 0), key=lambda s: s.base_z)
    assert len(upper) == 2
    assert [(round(op.u_m, 5), round(op.width_m, 5)) for op in upper[0].facade.openings] == [
        (round(op.u_m, 5), round(op.width_m, 5)) for op in upper[1].facade.openings]
    assert shape(plan.core['stairs']).area > 0
    upper_type = [t for t in plan.facade['floor_types'] if t['floors'] == [2, 3]]
    assert len(upper_type) == 1
    assert len(upper_type[0]['axes_m']) == 3
    for level in (1, 2):
        slab = next(part for part in plan.parts if part['id'] == f'level{level}/slab')
        assert shape(slab['geometry']).intersection(shape(plan.core['stairs'])).area < 1e-7


def test_local_program_changes_use_not_internal_geometry():
    r = request()
    r['building']['program'] = dict(use='mixed', residential='multi_family')
    plan = plan_exterior_envelope(r)
    assert plan.program['use'] == 'mixed'
    assert {op['kind'] for op in plan.openings} >= {'entrance', 'window'}
    assert not any(part['kind'] == 'partition' for part in plan.parts)


def test_front_sector_override_changes_only_its_window_program():
    r = request()
    r['building']['program'] = {'use': 'residential', 'floors': [
        {'body': 'main', 'floor': 1,
         'sectors': [{'front': 'F1', 'use': 'commercial'}]}]}
    plan = plan_envelope(r)
    ground = [op for op in plan.openings if op['floor'] == 1 and op['kind'] == 'window']
    upstairs = [op for op in plan.openings if op['floor'] == 2 and op['kind'] == 'window']
    assert len(ground) == 1 and ground[0]['use'] == 'commercial'
    assert ground[0]['width_m'] >= 3.5
    assert ground[0]['width_m'] > max(op['width_m'] for op in upstairs)
    assert len(upstairs) == 2 and all(op['use'] == 'residential' for op in upstairs)
    sectors = {sector['floor']: sector for sector in plan.facade['sectors']}
    assert sectors[1]['use'] == 'commercial' and sectors[2]['use'] == 'residential'


def test_typology_changes_facade_without_creating_internal_rooms():
    scenarios = [('single_family', {'use': 'residential', 'residential': 'single_family'}, 2),
                 ('multi_family', {'use': 'residential', 'residential': 'multi_family'}, 3),
                 ('office', {'use': 'office'}, 3),
                 ('commercial', {'use': 'commercial'}, 1)]
    for name, program, expected in scenarios:
        r = request();r['building']['program'] = program
        plan = plan_envelope(r)
        upper = [o for o in plan.openings if o['kind'] == 'window' and o['floor'] == 2]
        assert len(upper) == expected, name
        assert not any(p['kind'] == 'partition' for p in plan.parts)


def test_requested_crown_reserves_its_exposed_sector_not_a_fixed_triangle():
    r = request()
    r['building']['operations'] = [dict(id='remate', kind='crown', body='main',
                                         front='F1', position='right')]
    plan = plan_envelope(r)
    coronation, = plan.facade['coronations']
    assert coronation['sector_id'] == 'main/floor2/F1'
    assert coronation['host_surface_id'] in next(
        sector['surface_ids'] for sector in plan.facade['sectors']
        if sector['id'] == coronation['sector_id'])
    left, right = coronation['support_span_m']
    assert right-left > 2.4  # no universal 2.4 m triangular cap
    assert coronation['axis_m'] == pytest.approx((left+right)/2)
    assert not any(part['kind'] == 'crown' for part in plan.parts)


def test_opening_clearances_are_measured_from_edges_not_centres():
    plan = plan_envelope(with_balcony())
    hosts = {s['id']: s for row in plan.massing['storeys'] for s in row['surfaces']}
    for opening in plan.openings:
        line = shape(opening['geometry']);host = shape({'type': 'LineString',
                                                        'coordinates': hosts[opening['surface']]['line']})
        distances = sorted(host.project(shape({'type': 'Point', 'coordinates': list(p)}))
                           for p in line.coords)
        margin = 1.0 if opening['kind'] == 'entrance' else .85
        assert distances[0] >= margin-1e-6
        assert host.length-distances[1] >= margin-1e-6


def test_default_export_has_front_and_oblique_without_room_plans(tmp_path):
    plan = plan_envelope(with_balcony())
    report = export_envelope(plan, tmp_path/'exterior')
    output = tmp_path/'exterior'
    assert (output/'front.png').exists() and (output/'preview.png').exists()
    assert (output/'envelope.glb').exists()
    assert not (output/'floors').exists()
    assert 'no room partitions' in report['scope']


@pytest.mark.parametrize('case', sorted((Path(__file__).parents[1]/'experiments/phase0/cases').glob('*/*.json')))
def test_exterior_route_on_existing_massing_bank_without_bsp(case):
    request = json.loads(case.read_text())['request']
    plan = plan_envelope(request)
    assert 'interior' not in plan.to_dict()
    assert not any(part['kind'] == 'partition' for part in plan.parts)
    assert plan.checks['aperture_intrusion_m3'] == pytest.approx(0., abs=1e-6)
    for row in plan.massing['storeys']:
        for space in row.get('spaces', []):
            if space['kind'] in ('balcony', 'loggia', 'portico', 'vestibule'):
                assert len([o for o in plan.openings if o['access_for'] == space['id']]) == 1
