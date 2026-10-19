"""R3 seam: exterior apertures use the actual door/window catalog builders."""
import numpy as np
import pytest
from shapely.geometry import shape

from planning import catalogue_openings
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
