"""R4: exterior site catalogue — fence form, gates, shared access and routes."""
import json
from copy import deepcopy

import pytest
from shapely.geometry import shape

from domain.architectural_plan import PlanningError
from planning.envelope import plan_envelope
from planning.envelope_export import export_envelope
from planning.site_catalogue import materialize_site
from planning.site_plan import ACCESS_WIDTH, FENCE_HEIGHT, GATE_WIDTH, plan_site


def request(site=None, parcel=((0, 0), (9, 0), (9, 18), (0, 18)),
            fronts=None, levels=(0, 3.2, 6.)):
    building = dict(profile='barranco_residential')
    if site is not None:
        building['site'] = site
    return dict(version='intent-v1', seed=17,
                context=dict(parcel=[list(p) for p in parcel],
                             fronts=fronts or {'F1': 0},
                             levels_m=list(levels)),
                building=building)


def open_fence(form='open', height='low', style=None, **site_extra):
    spec = dict(front='F1', form=form, height=height)
    if style is not None:
        spec['style'] = style
    site = dict(fence=spec)
    site.update(site_extra)
    return request(site)


def site_of(r):
    return plan_envelope(r).to_dict()['site']


def members(plan):
    return {part['name'] for part in materialize_site(plan).parts}


def test_fence_form_and_height_come_from_the_intent():
    high = site_of(open_fence(form='solid', height='high'))
    assert high['fence']['form'] == 'solid'
    assert high['fence']['height_m'] == FENCE_HEIGHT['high']
    low = site_of(open_fence(form='base_and_rail', height='low'))
    assert low['fence']['form'] == 'base_and_rail'
    assert low['fence']['height_m'] == FENCE_HEIGHT['low']


def test_explicit_absence_leaves_no_fence_or_gate():
    plan = plan_envelope(request(dict(fence=False)))
    site = plan.to_dict()['site']
    assert site['fence'] is None and site['gates'] == []
    assert any(d['source'] == 'explicit' and 'absence' in d['reason']
               for d in site['decisions'])
    assert members(plan) == set()


def test_front_garden_completes_a_low_open_fence():
    site = site_of(request(dict(front_space=dict(front='F1', depth='medium'))))
    assert site['fence'] is not None
    assert site['fence']['form'] == 'open' and site['fence']['height_m'] == FENCE_HEIGHT['low']
    assert any(d['source'] == 'completion' for d in site['decisions'])


@pytest.mark.parametrize('style,member', [
    ('barroco', 'fence_scroll'), ('republicano', 'fence_ring'),
    ('madera', 'fence_picket'), ('moderno', 'fence_louver'),
])
def test_street_styles_render_their_own_catalogue_members(style, member):
    plan = plan_envelope(open_fence(style=style))
    assert plan.to_dict()['site']['fence']['style'] == style
    assert member in members(plan)


@pytest.mark.parametrize('style,member', [
    ('barroco', 'fence_scroll'), ('republicano', 'fence_ring'),
    ('madera', 'fence_picket'), ('moderno', 'fence_louver'),
])
def test_solid_form_is_a_wall_whatever_the_style(style, member):
    solid = members(plan_envelope(open_fence(style=style, form='solid')))
    opened = members(plan_envelope(open_fence(style=style)))
    assert 'fence_wall' in solid and 'fence_wall' not in opened
    assert member in opened


def test_pedestrian_gate_aligns_with_the_entrance_and_keeps_its_clear_width():
    plan = plan_envelope(open_fence())
    data = plan.to_dict()
    gate = next(g for g in data['site']['gates'] if g['kind'] == 'pedestrian')
    access = next(a for a in data['site']['accesses'] if a['kind'] == 'pedestrian')
    entrance = next(o for o in data['openings'] if o['kind'] == 'entrance')
    assert access['to_id'] == entrance['id']
    assert gate['width_m'] == GATE_WIDTH['pedestrian']
    assert access['clear_width_m'] == pytest.approx(
        entrance['width_m']-2*entrance['frame_width_m'], abs=.05)
    # the gate sits in front of its door, not elsewhere on the front
    u = shape(data['site']['fence']['geometry']).project(
        shape(gate['geometry']).centroid)
    v = shape(data['site']['fence']['geometry']).project(
        shape(entrance['geometry']).centroid)
    assert abs(u-v) < 1.2


def test_shared_cochera_adds_a_vehicle_gate_and_route():
    plan = plan_envelope(open_fence(garage=True))
    data = plan.to_dict()
    assert any(o['kind'] == 'vehicle_entry' for o in data['openings'])
    vehicle = next(g for g in data['site']['gates'] if g['kind'] == 'vehicle')
    assert vehicle['width_m'] == GATE_WIDTH['vehicle']
    access = next(a for a in data['site']['accesses'] if a['kind'] == 'vehicle')
    assert access['clear_width_m'] >= 2.10
    assert 'vehicle_entry' in access['to_id']


def test_cochera_needs_no_second_pedestrian_door():
    plan = plan_envelope(request(dict(fence=dict(front='F1', form='solid', height='high'),
                                      garage=True, door=False)))
    data = plan.to_dict()
    assert not [o for o in data['openings'] if o['kind'] == 'entrance']
    kinds = {g['kind'] for g in data['site']['gates']}
    assert kinds == {'vehicle'}
    assert {a['kind'] for a in data['site']['accesses']} == {'vehicle'}


def test_gates_keep_their_piers_and_stay_within_the_run():
    plan = plan_envelope(open_fence(garage=True))
    site = plan.to_dict()['site']
    length = shape(site['fence']['geometry']).length
    intervals = sorted(tuple(g['interval_m']) for g in site['gates'])
    for low, high in intervals:
        assert low >= 0. and high <= length
    for (a0, a1), (b0, b1) in zip(intervals, intervals[1:]):
        assert b0-a1 >= 0.2


def test_devices_are_anchored_to_the_pedestrian_gate():
    plan = plan_envelope(open_fence())
    site = plan.to_dict()['site']
    details = site['fence']['details']
    assert {d['id'] for d in details} == {'site/detail/meter', 'site/detail/bell',
                                          'site/detail/number'}
    gate = next(g for g in site['gates'] if g['kind'] == 'pedestrian')
    assert all(d['anchor_id'] == gate['id'] for d in details)
    assert {'site/detail/meter', 'site/detail/bell', 'site/detail/number'} <= members(plan)


def test_fence_without_a_setback_reports_local_conflict():
    with pytest.raises(PlanningError) as err:
        plan_envelope(request(dict(front_space=False,
                                   fence=dict(front='F1', form='solid', height='high'))))
    assert err.value.code in ('fence_blocked', 'access_outside_free')


def test_street_edge_access_is_direct_and_invents_no_fence():
    plan = plan_envelope(request(dict(fence=False)))
    site = plan.to_dict()['site']
    assert site['gates'] == []
    route = site['routes'][0]
    assert route['transition'] == 'direct'
    assert shape(route['geometry']).is_empty


def test_access_routes_stay_inside_the_free_ground():
    plan = plan_envelope(open_fence(garage=True))
    data = plan.to_dict()
    free = shape(data['massing']['site']['free'])
    for route in data['site']['routes']:
        footprint = shape(route['geometry'])
        if not footprint.is_empty:
            assert free.buffer(1e-5).covers(footprint)
            assert route['width_m'] == ACCESS_WIDTH[route['kind']]


def test_site_plan_is_deterministic():
    r = open_fence(style='republicano', garage=True)
    first = plan_site(plan_envelope(deepcopy(r)))
    second = plan_site(plan_envelope(deepcopy(r)))
    assert json.dumps(first.to_dict(), sort_keys=True) == json.dumps(second.to_dict(),
                                                                     sort_keys=True)


def test_export_reports_the_site_catalogue(tmp_path):
    plan = plan_envelope(open_fence(style='barroco'))
    report = export_envelope(plan, tmp_path/'site')
    output = tmp_path/'site'
    assert (output/'envelope.glb').exists()
    assert report['site']['faces'] > 0
    assert 'fence_scroll' in report['site']['semantics']
    assert set(report['site']['semantics']) & {'boundary_post', 'gate_frame'}
