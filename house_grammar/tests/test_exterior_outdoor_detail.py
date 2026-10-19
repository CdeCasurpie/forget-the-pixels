"""R5: a requested front garden has restrained planting, never blocked access."""
from shapely.geometry import shape

from planning.envelope import plan_envelope
from planning.envelope_export import export_envelope
from planning.outdoor_detail import materialize_outdoor_details, plan_outdoor_details


def request(use='garden', garage=False, front_space=True):
    site = {}
    if front_space:
        site['front_space'] = dict(front='street', depth='medium', use=use)
    if garage:
        site['garage'] = True
    return dict(version='intent-v1', seed=17,
                context=dict(parcel=[[0, 0], [11, 0], [11, 18], [0, 18]],
                             fronts={'street': 0}, levels_m=[0, 3.2, 6.4]),
                building=dict(profile='barranco_residential', style='republicano', site=site))


def test_requested_garden_has_restrained_ground_planting():
    plan = plan_envelope(request())
    assert 1 <= len(plan.outdoor_details) <= 3
    assert {d['kind'] for d in plan.outdoor_details} == {'planter'}
    assert plan.outdoor_details == plan_outdoor_details(plan)


def test_driveway_or_unreserved_ground_stays_empty():
    assert plan_envelope(request(use='driveway')).outdoor_details == []
    assert plan_envelope(request(front_space=False)).outdoor_details == []


def test_fence_reservation_alone_is_not_a_requested_garden():
    data = request(front_space=False)
    data['building']['site'] = dict(fence=dict(front='street', form='open'))
    plan = plan_envelope(data)
    assert any(r['id'] == 'front_space' for r in plan.massing['site']['reservations'])
    assert plan.outdoor_details == []


def test_planters_do_not_block_access_or_leave_free_ground():
    plan = plan_envelope(request(garage=True))
    free = shape(plan.massing['site']['free'])
    for planter in plan.outdoor_details:
        footprint = shape(planter['footprint'])
        assert free.covers(footprint)
        for route in plan.site['routes']:
            assert footprint.distance(shape(route['geometry'])) >= .45-1e-6


def test_ground_planters_are_real_catalogue_objects():
    mesh = materialize_outdoor_details(plan_envelope(request()))
    names = {p['name'] for p in mesh.parts}
    assert {'planter', 'planting_soil', 'roof_shrub'} <= names
    assert len(mesh.faces) > 0
    assert mesh.vertices[:, 2].min() >= -1e-6


def test_wide_balcony_corners_can_carry_pots_without_blocking_the_door():
    data = request()
    data['building']['operations'] = [dict(id='bal', kind='balcony', body='main',
                                           front='street', floors=[2], width='wide',
                                           depth='medium')]
    plan = plan_envelope(data)
    balconies = [d for d in plan.outdoor_details if d.get('space_id')]
    assert 1 <= len(balconies) <= 2
    space = next(s for row in plan.massing['storeys'] for s in row.get('spaces', ())
                 if s['id'] == 'bal/floor2')
    door = next(o for o in plan.openings if o.get('access_for') == space['id'])
    for prop in balconies:
        footprint = shape(prop['footprint'])
        assert shape(space['geometry']).covers(footprint)
        assert footprint.distance(shape(door['geometry'])) >= .55-1e-6
        assert prop['z_m'] == space['bottom_m']


def test_export_reports_the_site_details(tmp_path):
    report = export_envelope(plan_envelope(request()), tmp_path/'garden')
    assert report['outdoor_details']['count'] > 0
    assert report['outdoor_details']['faces'] > 0
    assert (tmp_path/'garden'/'envelope.glb').exists()
