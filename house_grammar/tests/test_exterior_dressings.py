"""R5: shallow window dressing behind the exterior windows."""
from planning.dressing_catalogue import materialize_dressings
from planning.dressing_plan import plan_dressings
from planning.envelope import plan_envelope
from planning.envelope_export import export_envelope


def request(style='republicano'):
    return dict(version='intent-v1', seed=17,
                context=dict(parcel=[[0, 0], [11, 0], [11, 18], [0, 18]],
                             fronts={'street': 0}, levels_m=[0, 3.2, 6.2]),
                building=dict(profile='barranco_residential', style=style))


def test_every_window_gets_a_backdrop():
    data = plan_envelope(request()).to_dict()
    windows = {o['id'] for o in data['openings'] if o['kind'] == 'window'}
    dressings = plan_dressings(data)
    assert {d['id'] for d in dressings} == windows
    assert all(d['backdrop'] for d in dressings)


def test_curtain_coverage_is_bounded_and_optional():
    fractions = [d['fraction'] for d in plan_dressings(plan_envelope(request()))]
    assert all(0. <= f <= .52 for f in fractions)
    assert any(f > 0. for f in fractions)


def test_dressing_is_deterministic():
    assert plan_dressings(plan_envelope(request())) == plan_dressings(plan_envelope(request()))


def test_interior_route_has_no_dressing():
    assert plan_dressings({'interior': {}}) == []


def test_dressing_is_materialized_behind_the_wall():
    mesh = materialize_dressings(plan_envelope(request()))
    names = {part['name'] for part in mesh.parts}
    assert len(mesh.faces) > 0
    assert 'window_backdrop' in names
    assert 'window_curtain' in names
    parcel = [[0, 0], [11, 0], [11, 18], [0, 18]]
    assert all(0. <= v[0] <= 11. and 0. <= v[1] <= 18. for v in mesh.vertices)


def test_export_reports_the_dressings(tmp_path):
    report = export_envelope(plan_envelope(request()), tmp_path/'dressing')
    assert (tmp_path/'dressing'/'envelope.glb').exists()
    assert report['dressings']['count'] > 0
    assert report['dressings']['faces'] > 0
    assert 'window_backdrop' in report['dressings']['semantics']
