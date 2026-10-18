"""R3 seam: exterior apertures use the actual door/window catalog builders."""
import numpy as np
import pytest
from shapely.geometry import shape

from planning import catalogue_openings
from planning.envelope import plan_envelope
from planning.envelope_export import export_envelope
from planning.envelope import strip


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
