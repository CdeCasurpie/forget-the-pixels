"""R3 seam: exterior apertures use the actual door/window catalog builders."""
import numpy as np
import pytest
from shapely.geometry import LineString, Point, shape

from domain.architectural_plan import PlanningError
from planning import catalogue_openings, openings_plan
from planning.envelope import plan_envelope
from planning.envelope_export import export_envelope
from planning.envelope import strip
from modeling.apertures import opening_shape


def request():
    return dict(version='intent-v1', seed=17,
                context=dict(parcel=[[0, 0], [12, 0], [12, 18], [0, 18]],
                             fronts={'street': 0}, levels_m=[0, 3.2, 6.]),
                building=dict(profile='barranco_residential', style='republicano',
                              site=dict(front_space=dict(front='street', depth='medium')),
                              operations=[dict(id='bal', kind='balcony', body='main',
                                               front='street', floors=[2])] ))


def plain(width=12., floors=2, levels=None):
    """Balcony-free intent so R3 sizing is exercised without the access door."""
    return dict(version='intent-v1', seed=17,
                context=dict(parcel=[[0, 0], [width, 0], [width, 18], [0, 18]],
                             fronts={'street': 0},
                             levels_m=levels or [round(3.2*i, 2) for i in range(floors+1)]),
                building=dict(profile='barranco_residential', style='republicano'))


def test_catalogue_called_once_per_exterior_opening(monkeypatch):
    plan = plan_envelope(request())
    observed = []
    original = catalogue_openings.build_opening

    def spy(builder, origin, tangent, normal, opening):
        observed.append((opening.kind, opening.frame_profile,
                         opening.recess_m, opening.frame_depth_m))
        return original(builder, origin, tangent, normal, opening)

    monkeypatch.setattr(catalogue_openings, 'build_opening', spy)
    mesh = catalogue_openings.materialize_openings(plan)
    assert len(observed) == len(plan.openings)
    assert {kind for kind, *_ in observed} == {'door', 'window'}
    assert all(style == 'republicano' for kind, style, *_ in observed if kind == 'window')
    assert min(recess for kind, _, recess, _ in observed if kind == 'door') >= max(
        recess for kind, _, recess, _ in observed if kind == 'window')
    assert {'door_moulding', 'door_glass', 'window_profile', 'window_glass'} <= {
        part['name'] for part in mesh.parts}
    assert not any(part['kind'] in ('jamb_left', 'leaf0_infill') for part in plan.parts)


def test_catalogue_upper_storey_is_at_its_real_world_height():
    plan = plan_envelope(request())
    mesh = catalogue_openings.materialize_openings(plan)
    for part in mesh.parts:
        if '/floor2/' not in part['assembly_id']:continue
        faces = mesh.faces[part['face_start']:part['face_start']+part['face_count']]
        low = 3.2-.035 if part['name'] == 'door_threshold' else 3.2
        assert np.min(mesh.vertices[np.unique(faces), 2]) >= low-1e-6


def test_door_thresholds_have_a_recess_in_the_floor_slab():
    plan = plan_envelope(request())
    for op in plan.openings:
        if op['kind'] == 'window':continue
        slab = next(part for part in plan.parts
                    if part['id'] == f'level{op["floor"]-1}/slab')
        assert slab['bottom_m'] == pytest.approx(op['bottom_m']-.035)
        threshold = strip(shape(op['geometry']), 0., op['width_m'], -.10, .12, op['inward'])
        assert shape(slab['geometry']).intersection(threshold).area < 1e-7


def test_export_combines_cut_wall_and_catalogue_pieces(tmp_path):
    plan = plan_envelope(request())
    report = export_envelope(plan, tmp_path/'catalogue')
    assert report['catalogue_openings']['faces'] > 0
    assert 'window_profile' in report['catalogue_openings']['semantics']
    assert 'door_glass' in report['catalogue_openings']['semantics']
    assert (tmp_path/'catalogue/envelope.glb').exists()
    assert plan.checks['aperture_intrusion_m3'] == pytest.approx(0.)


def test_arch_cut_uses_the_same_catalogue_contour_as_window(tmp_path):
    intent = request()
    intent['building']['facades'] = [dict(body='main', front='street', floors=[1, 2],
                                           windows=dict(count=2, shape='arch', grille=True))]
    plan = plan_envelope(intent)
    hosts = {s['id']: s for row in plan.massing['storeys'] for s in row['surfaces']}
    from planning.catalogue_openings import opening_for_record, materialize_contoured_walls
    for wall in plan.contoured_walls:
        domain = shape(wall['domain'])
        for op in plan.openings:
            if op['surface'] != wall['id']:continue
            aperture = opening_shape(opening_for_record(op, hosts[op['surface']]))
            assert domain.intersection(aperture).area < 1e-7
            if op['kind'] == 'window':
                assert op['arch_rise_m'] is not None
    shell = materialize_contoured_walls(plan)
    assert shell.faces.size and all(shape(w['domain']).is_valid for w in plan.contoured_walls)
    report = export_envelope(plan, tmp_path/'arched', preview=False)
    assert report['contoured_walls']['hosts'] == len(plan.contoured_walls)
    assert report['catalogue_openings']['faces'] > 0
    assert report['audit']['watertight']


def test_door_arch_and_transom_are_catalogued_without_changing_legacy_defaults():
    intent = request()
    intent['building']['site']['door'] = dict(shape='arch', transom='glass')
    plan = plan_envelope(intent)
    mesh = catalogue_openings.materialize_openings(plan)
    assert 'transom_glass' in {part['name'] for part in mesh.parts}
    assert len(plan.contoured_walls) == 1
    assert all(op['shape'] == 'rectangle' for op in plan.openings if op['kind'] == 'window')


# --- R3: joint dimensioning, reserves, families and repeated axes ----------

def _hosts(plan):
    return {s['id']: s for row in plan.massing['storeys'] for s in row['surfaces']}


def _span(line, geometry):
    distances = sorted(line.project(Point(p)) for p in shape(geometry).coords)
    return distances[0], distances[1]


def test_main_windows_are_clearly_larger_than_their_vents():
    intent = plain()
    intent['building']['facades'] = [dict(
        body='main', front='street', floors=[1, 2],
        windows=dict(count=3, proportions=['horizontal', 'vertical', 'small_high']))]
    plan = plan_envelope(intent)
    mains = [o for o in plan.openings if o['family'] in ('horizontal', 'vertical')]
    vents = [o for o in plan.openings if o['family'] == 'small_high']
    assert len(mains) == 4 and len(vents) == 2
    assert min(o['width_m'] for o in mains) > max(o['width_m'] for o in vents)
    assert min(o['sill_m'] for o in vents) > max(o['sill_m'] for o in mains)
    assert min(o['top_m']-o['bottom_m'] for o in vents) < min(
        o['top_m']-o['bottom_m'] for o in mains)


@pytest.mark.parametrize('width,count', [(6., 2), (8., 2), (20., 3)])
def test_lot_width_keeps_the_count_and_never_a_squeezed_window(width, count):
    intent = plain()
    intent['context']['parcel'] = [[0, 0], [width, 0], [width, 18], [0, 18]]
    intent['building']['facades'] = [dict(body='main', front='street', floors=[1, 2],
                                          windows=dict(count=count))]
    plan = plan_envelope(intent)
    ground = [o for o in plan.openings if o['kind'] == 'window' and o['floor'] == 1]
    assert len(ground) == count
    for opening in ground:
        low, high = openings_plan.band(opening['family'])
        assert low-1e-6 <= opening['width_m'] <= high+1e-6


def test_impossible_explicit_request_reports_a_conflict_not_a_tiny_window():
    intent = plain()
    intent['context']['parcel'] = [[0, 0], [6, 0], [6, 18], [0, 18]]
    intent['building']['facades'] = [dict(body='main', front='street', floors=[1, 2],
                                          windows=dict(count=3))]
    with pytest.raises(PlanningError) as failure:
        plan_envelope(intent)
    assert failure.value.code == 'window_capacity'


def test_portal_volume_and_piers_are_reserved_between_openings():
    intent = plain()
    intent['building']['site'] = {'door': dict(position='left', portal='pilasters')}
    plan = plan_envelope(intent)
    hosts = _hosts(plan)
    door = next(o for o in plan.openings if o['kind'] == 'entrance')
    reserve = openings_plan.portal_reserve('pilasters')
    line = LineString(hosts[door['surface']]['line'])
    start, end = _span(line, door['geometry'])
    assert door['reserve_m'] == pytest.approx(openings_plan.margin_for(
        kind='door', portal='pilasters'))
    assert start-reserve >= -1e-6                       # pilaster stays on the wall
    assert line.length-end-reserve >= -1e-6
    for window in (o for o in plan.openings if o['kind'] == 'window' and o['floor'] == 1):
        window_line = LineString(hosts[window['surface']]['line'])
        wstart, _ = _span(window_line, window['geometry'])
        assert wstart >= end+reserve+openings_plan.PIER_M-1e-6


def test_storefront_is_one_continuous_glazing_wider_than_any_house_window():
    intent = plain()
    intent['building']['program'] = {'use': 'residential', 'floors': [
        {'body': 'main', 'floor': 1, 'sectors': [{'front': 'street', 'use': 'commercial'}]}]}
    plan = plan_envelope(intent)
    ground = [o for o in plan.openings if o['kind'] == 'window' and o['floor'] == 1]
    assert len(ground) == 1 and ground[0]['family'] == 'storefront'
    assert ground[0]['width_m'] >= 3.5
    assert ground[0]['width_m'] > max(o['width_m'] for o in plan.openings
                                      if o['kind'] == 'window' and o['floor'] == 2)


@pytest.mark.parametrize('form,proportion', [('rectangle', 'horizontal'),
                                             ('arch', 'vertical'),
                                             ('circle', 'square'),
                                             ('ellipse', 'horizontal')])
def test_every_family_punches_the_catalogue_contour(tmp_path, form, proportion):
    intent = plain()
    intent['building']['facades'] = [dict(body='main', front='street', floors=[1, 2],
                                          windows=dict(count=2, proportion=proportion,
                                                       shape=form))]
    plan = plan_envelope(intent)
    hosts = _hosts(plan)
    curved = form != 'rectangle'
    for opening in plan.openings:
        if opening['kind'] != 'window':continue
        line = LineString(hosts[opening['surface']]['line'])
        catalogue = catalogue_openings.opening_for_record(opening, hosts[opening['surface']])
        aperture = opening_shape(catalogue)
        start, end = _span(line, opening['geometry'])
        assert aperture.bounds[0] == pytest.approx(start, abs=1e-6)
        assert aperture.bounds[2] == pytest.approx(end, abs=1e-6)
        if curved:
            assert aperture.area < opening['width_m']*(
                opening['top_m']-opening['bottom_m'])-1e-6
    report = export_envelope(plan, tmp_path/f'family_{form}_{proportion}', preview=False)
    assert report['audit']['watertight']
    # The catalog frames project to the street: they must survive the export.
    assert 'window_profile' in report['catalogue_openings']['semantics']
    assert 'window_glass' in report['catalogue_openings']['semantics']
    if curved:
        assert report['contoured_walls']['hosts'] >= 1
        assert all(shape(wall['domain']).is_valid for wall in plan.contoured_walls)


def test_axes_lintels_and_catalogue_contours_repeat_between_compatible_floors():
    intent = plain()
    intent['context']['levels_m'] = [0, 3.2, 6., 8.8]
    intent['building']['program'] = {'use': 'residential', 'residential': 'multi_family'}
    plan = plan_envelope(intent)
    hosts = _hosts(plan)
    floors = {}
    for opening in plan.openings:
        if opening['kind'] == 'window':
            floors.setdefault(opening['floor'], []).append(opening)

    def signature(opening):
        catalogue = catalogue_openings.opening_for_record(opening, hosts[opening['surface']])
        return (round(catalogue.u_m, 6), round(catalogue.width_m, 6),
                round(catalogue.height_m, 6), round(opening['sill_m'], 6),
                round(opening['top_m']-opening['bottom_m'], 6))

    assert len(floors[2]) == len(floors[3]) == 3
    assert [signature(o) for o in floors[2]] == [signature(o) for o in floors[3]]
    type_, = [t for t in plan.facade['floor_types'] if t['floors'] == [2, 3]]
    assert len(type_['axes_m']) == 3


def test_catalogue_frames_project_to_the_street_while_glazing_sets_back():
    plan = plan_envelope(plain())
    mesh = catalogue_openings.materialize_openings(plan)
    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)
    materials = {m['name']: i for i, m in enumerate(mesh.materials)}
    slot = np.asarray(mesh.face_materials)

    def y_of(name):
        return vertices[faces[slot == materials[name]]][:, 1]

    assert y_of('glass').min() > 0.        # glazing sits inside the lot
    assert y_of('wood').min() < -.02       # frames overhang the sidewalk
    assert vertices[:, 1].min() < -.02


def test_public_route_has_no_duplicate_joinery_emitter():
    plan = plan_envelope(plain())
    legacy = {'jamb_left', 'jamb_right', 'head', 'sill', 'sill_cap',
              'leaf0_left', 'leaf0_infill', 'leaf1_right'}
    assert not legacy & {part['kind'] for part in plan.parts}
    semantics = {part['name'] for part in catalogue_openings.materialize_openings(plan).parts}
    # Capabilities ``_joinery`` used to emit must all come from the catalogue.
    assert {'window_reveal', 'window_profile', 'window_glass', 'window_sill',
            'window_mullion', 'door_reveal', 'door_moulding', 'door_leaf_frame',
            'door_handle', 'door_threshold'} <= semantics
    # Construction-specific leaves come from the catalog design, not a second
    # emitter: a glazed door (balcony access) resolves to glass infill.
    glazed = {part['name'] for part in
              catalogue_openings.materialize_openings(plan_envelope(request())).parts}
    assert 'door_glass' in glazed


def test_corner_fronts_keep_their_own_edge_margins():
    intent = plain()
    intent['context']['fronts'] = {'street': 0, 'side': 1}
    intent['building']['organization'] = 'corner'
    plan = plan_envelope(intent)
    hosts = _hosts(plan)
    for front in ('street', 'side'):
        windows = [o for o in plan.openings if o['kind'] == 'window' and o['front'] == front]
        assert windows, front
        for opening in windows:
            line = LineString(hosts[opening['surface']]['line'])
            distances = sorted(line.project(Point(p)) for p in shape(opening['geometry']).coords)
            assert distances[0] >= .85-1e-6
            assert line.length-distances[1] >= .85-1e-6


