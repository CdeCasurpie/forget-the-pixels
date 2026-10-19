"""R4: crown (fronton) planning tied to its reserved sector, not a fixed triangle."""
import json

import pytest
from shapely.geometry import LineString, Point, shape

from planning.crown_catalogue import materialize_crowns
from planning.crown_plan import plan_crowns
from planning.envelope import plan_envelope
from planning.envelope_export import export_envelope


def request(style='republicano', operations=None, parcel=((0, 0), (14, 0), (14, 18), (0, 18))):
    return dict(version='intent-v1', seed=17,
                context=dict(parcel=[list(p) for p in parcel], fronts={'F1': 0},
                             levels_m=[0, 3.2, 6.2]),
                building=dict(profile='barranco_residential', style=style,
                              operations=operations if operations is not None else
                              [dict(id='crown0', kind='crown', body='main', front='F1')]))


def host_line(data, crown):
    for row in data['massing']['storeys']:
        for surface in row.get('surfaces', []):
            if surface['id'] == crown['host_surface_id']:
                return LineString(surface['line'])
    raise AssertionError('host surface missing')


def test_requested_crown_stays_tied_to_its_sector_axes():
    data = plan_envelope(request()).to_dict()
    crown = data['crowns'][0]
    line = host_line(data, crown)
    floor = max(o['floor'] for o in data['openings'])
    ends = []
    for op in data['openings']:
        if op['floor'] == floor and op['kind'] == 'window' and op['surface'] == crown['host_surface_id']:
            ends += [line.project(Point(p)) for p in shape(op['geometry']).coords]
    assert crown['width_m'] >= max(ends)-min(ends)
    assert crown['width_m'] < line.length                       # never the whole panel blindly
    assert crown['axis_u_m'] == pytest.approx((min(ends)+max(ends))/2, abs=.6)
    lowest = crown['axis_u_m']-crown['width_m']/2
    assert lowest >= 0. and crown['axis_u_m']+crown['width_m']/2 <= line.length


def test_crown_base_sits_above_every_window_of_its_sector():
    data = plan_envelope(request()).to_dict()
    crown = data['crowns'][0]
    floor = max(o['floor'] for o in data['openings'])
    tops = [o['top_m'] for o in data['openings']
            if o['floor'] == floor and o['surface'] == crown['host_surface_id']]
    assert tops and crown['base_z_m'] >= max(tops)-1e-6


def test_no_crown_without_the_operation():
    data = plan_envelope(request(operations=[])).to_dict()
    assert data['crowns'] == []
    assert len(materialize_crowns(plan_envelope(request(operations=[]))).faces) == 0


@pytest.mark.parametrize('style,family', [
    ('republicano', 'triangular'), ('clasico', 'triangular'),
    ('barroco', 'compound_curve'), ('moderno', 'stepped'), ('madera', 'stepped'),
])
def test_styles_choose_the_crown_family(style, family):
    crown = plan_envelope(request(style=style)).to_dict()['crowns'][0]
    assert crown['design']['family'] == family
    assert crown['design']['style'] == style
    assert crown['height_m'] > 0.


@pytest.mark.parametrize('style,ornament', [
    ('republicano', 'keystone'), ('clasico', 'dentils'),
    ('barroco', 'volutes'), ('moderno', 'none'),
])
def test_style_ornaments_are_local_to_the_crown(style, ornament):
    crown = plan_envelope(request(style=style)).to_dict()['crowns'][0]
    assert crown['design']['ornament'] == ornament


def test_crown_is_materialized_with_the_crown_catalog():
    plan = plan_envelope(request())
    mesh = materialize_crowns(plan)
    names = {part['name'] for part in mesh.parts}
    assert len(mesh.faces) > 0
    assert {'crown_body', 'crown_rim', 'crown_moulding', 'crown_base_cornice'} <= names


def test_crown_plan_is_deterministic():
    first = plan_crowns(plan_envelope(request(style='barroco')))
    second = plan_crowns(plan_envelope(request(style='barroco')))
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_crown_never_overlaps_its_sector_windows():
    data = plan_envelope(request()).to_dict()
    crown = data['crowns'][0]
    line = host_line(data, crown)
    left = crown['axis_u_m']-crown['width_m']/2
    right = crown['axis_u_m']+crown['width_m']/2
    for op in data['openings']:
        if op['surface'] != crown['host_surface_id'] or op['top_m'] <= crown['base_z_m']:
            continue
        ends = sorted(line.project(Point(p)) for p in shape(op['geometry']).coords)
        assert ends[1] <= left or ends[0] >= right


def test_export_reports_the_crowns(tmp_path):
    plan = plan_envelope(request(style='clasico'))
    report = export_envelope(plan, tmp_path/'crowns')
    assert (tmp_path/'crowns'/'envelope.glb').exists()
    assert report['crowns']['count'] == 1
    assert report['crowns']['faces'] > 0
    assert 'crown_body' in report['crowns']['semantics']
