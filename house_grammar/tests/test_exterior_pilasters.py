"""R4: facade pilasters belong to the ordered languages and frame real bays."""
import json

import pytest
from shapely.geometry import LineString

from planning.envelope import plan_envelope
from planning.envelope_export import export_envelope
from planning.pilaster_catalogue import materialize_pilasters
from planning.pilaster_plan import plan_pilasters


def request(style='republicano', width=11., floors=2):
    return dict(version='intent-v1', seed=17,
                context=dict(parcel=[[0, 0], [width, 0], [width, 18], [0, 18]],
                             fronts={'street': 0},
                             levels_m=[round(3.2*i, 2) for i in range(floors+1)]),
                building=dict(profile='barranco_residential', style=style))


def surface_of(data, surface_id):
    return next(s for row in data['massing']['storeys'] for s in row.get('surfaces', [])
                if s['id'] == surface_id)


def test_ordered_languages_frame_their_bays():
    for style in ('republicano', 'clasico', 'barroco'):
        pilasters = plan_pilasters(plan_envelope(request(style=style)))
        assert pilasters, f'{style} should carry a facade order'
        assert {p['style'] for p in pilasters} == {style}


@pytest.mark.parametrize('style', ['moderno', 'madera'])
def test_plain_languages_stay_unadorned(style):
    assert plan_pilasters(plan_envelope(request(style=style))) == []
    assert len(materialize_pilasters(plan_envelope(request(style=style))).faces) == 0


def test_pilasters_sit_between_the_openings_of_their_surface():
    data = plan_envelope(request()).to_dict()
    pilasters = plan_pilasters(data)
    assert pilasters
    for pilaster in pilasters:
        surface = surface_of(data, pilaster['surface_id'])
        line = LineString(surface['line'])
        left = pilaster['u_m']-pilaster['width_m']/2
        right = pilaster['u_m']+pilaster['width_m']/2
        assert 0. <= left and right <= line.length
        for opening in data['openings']:
            if opening['surface'] != surface['id']:
                continue
            ends = sorted(line.project(__import__('shapely').geometry.Point(p))
                          for p in opening['geometry']['coordinates'])
            assert ends[1] <= left+1e-6 or ends[0] >= right-1e-6


def test_every_pilaster_fits_its_pier_with_a_margin():
    data = plan_envelope(request()).to_dict()
    for pilaster in plan_pilasters(data):
        assert pilaster['height_m'] > .9
        assert pilaster['width_m'] > 0. and pilaster['depth_m'] > 0.


def test_pilasters_are_materialized_from_the_member_catalog():
    mesh = materialize_pilasters(plan_envelope(request(style='clasico')))
    assert len(mesh.faces) > 0
    assert {'member_shaft', 'member_base', 'member_capital'} <= {p['name'] for p in mesh.parts}


def test_pilaster_plan_is_deterministic():
    first = plan_pilasters(plan_envelope(request(style='barroco')))
    second = plan_pilasters(plan_envelope(request(style='barroco')))
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_pilaster_span_keeps_the_edge_margin_to_its_openings():
    from shapely.geometry import Point
    data = plan_envelope(request()).to_dict()
    for pilaster in plan_pilasters(data):
        surface = surface_of(data, pilaster['surface_id'])
        line = LineString(surface['line'])
        left = pilaster['u_m']-pilaster['width_m']/2
        right = pilaster['u_m']+pilaster['width_m']/2
        for opening in data['openings']:
            if opening['surface'] != surface['id']:
                continue
            ends = sorted(line.project(Point(p)) for p in opening['geometry']['coordinates'])
            if ends[1] <= left:
                assert left-ends[1] >= .28-1e-6
            elif ends[0] >= right:
                assert ends[0]-right >= .28-1e-6


def test_export_reports_the_pilasters(tmp_path):
    report = export_envelope(plan_envelope(request(style='republicano')), tmp_path/'order')
    assert (tmp_path/'order'/'envelope.glb').exists()
    assert report['pilasters']['count'] > 0
    assert report['pilasters']['faces'] > 0
    assert 'member_shaft' in report['pilasters']['semantics']
