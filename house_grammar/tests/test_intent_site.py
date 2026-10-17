"""Phase 5: fence forms, gates, accessible ground and material audits."""
import json
from functools import lru_cache
from pathlib import Path

import pytest
from shapely.geometry import shape

from domain.architectural_plan import PlanningError
from planning.site_access import ACCESS_WIDTH, plan_site
from planning.site_export import export_site, solids


ROOT=Path(__file__).parents[1]
BANK=ROOT/'experiments'/'phase0'/'cases'
CASES=ROOT/'experiments'/'phase5'/'cases'
BANK_PATHS=sorted(BANK.glob('*/*.json'))
FIXTURE_PATHS=sorted(CASES.glob('*.json'))


def request_for(path, seed=17):
    request=json.loads(path.read_text())['request'];request['seed']=seed
    return request


@lru_cache(maxsize=None)
def site(path, seed=17):
    return plan_site(request_for(path,seed))


def bank(name, seed=17):
    return site(next(path for path in BANK_PATHS if path.stem==name),seed)


def fixture(name, seed=17):
    return site(CASES/f'{name}.json',seed)


def part(plan, identity):
    return next(p for p in plan.parts if p['id']==identity)


@pytest.mark.parametrize('path',BANK_PATHS,ids=lambda p:p.stem)
def test_frozen_bank_builds_connected_ground_access(path):
    plan=site(path)
    assert plan.version=='site-plan-v1'
    assert plan.checks['parcel_containment'] and plan.checks['accesses_connected']
    assert 'site.fence' not in {p['path'] for p in plan.pending}
    assert 'site.access_route' not in {p['path'] for p in plan.pending}
    assert len(plan.routes)==len(plan.accesses)>=1
    assert len({a['kind'] for a in plan.accesses})==len(plan.accesses)
    for a in plan.accesses:
        assert a['clear_width_m']>=(.75 if a['kind']=='pedestrian' else 2.1)
        assert a['to_id'] in {o['id'] for o in plan.envelope['openings']} or a['to_id']=='site/open_arcade'
        opening=next((o for o in plan.envelope['openings'] if o['id']==a['to_id']),None)
        route=next(r for r in plan.routes if r['id']==a['route_id'])
        if opening:
            from shapely.geometry import Point
            assert Point(shape(route['axis']).coords[-1]).distance(shape(opening['axis']))<1e-6
    assert all(p['top_m']>p['bottom_m'] and shape(p['geometry']).is_valid for p in plan.parts)


def test_other_seeds_build_the_entire_bank():
    for path in BANK_PATHS:
        for seed in (7,81):
            plan=site(path,seed)
            assert plan.checks['accesses_connected'],(path,seed)


@pytest.mark.parametrize('path',FIXTURE_PATHS,ids=lambda p:p.stem)
def test_fixture_scopes_are_physical_and_respected(path):
    plan=site(path);expected=json.loads(path.read_text())['expectations']
    kinds={p['kind'] for p in plan.parts}
    if expected.get('no_fence'):assert plan.fence is None
    if 'fence' in expected:assert plan.fence['form']==expected['fence']
    if 'height_m' in expected:assert plan.fence['height_m']==pytest.approx(expected['height_m'])
    if 'cap' in expected:assert plan.fence['cap']==expected['cap']
    if 'gates' in expected:assert sorted(g['kind'] for g in plan.gates)==sorted(expected['gates'])
    if 'routes' in expected:assert sorted(r['kind'] for r in plan.routes)==sorted(expected['routes'])
    if 'transitions' in expected:assert sorted(r['transition'] for r in plan.routes)==sorted(expected['transitions'])
    if 'parts' in expected:assert set(expected['parts'])<=kinds
    if expected.get('canopy'):assert 'gate_canopy' in kinds
    if expected.get('details'):assert len(plan.fence['details'])==3
    if expected.get('completion'):
        assert any(d.get('source')=='completion' and d['path']=='site.fence' for d in plan.decisions)


def test_all_fixture_seeds_export_closed_disjoint_solids():
    for path in FIXTURE_PATHS:
        for seed in (7,17,81):
            _,audit=solids(site(path,seed))
            assert audit['watertight'] and not audit['non_watertight'],(path,seed,audit)
            assert audit['group_overlap_m3']<=1e-9,(path,seed,audit['group_overlap_pairs'])


@pytest.mark.parametrize('name',['p5_high_fence_hidden','p5_low_open_rail',
                                'p5_base_and_rail','p5_partial_fence','p5_covered_portal'])
def test_gate_openings_remove_fence_without_blocking_the_pedestrian(name):
    plan=fixture(name);frame=plan.envelope['interior']['massing']['fronts']['F1']
    from planning.envelope import strip
    from planning.site_access import _line, FENCE_THICKNESS
    edge=_line(frame,0,frame['length_m'])
    for gate in plan.gates:
        left,right=gate['interval_m']
        cut=strip(edge,left,right,0.,FENCE_THICKNESS,frame['inward'])
        for p in plan.parts:
            if p['kind'] not in ('fence_wall','fence_base','fence_post','fence_rail','fence_bar','gate_post'):
                continue
            assert shape(p['geometry']).intersection(cut).area<1e-8,p['id']
        access=next(a for a in plan.accesses if a['kind']==gate['kind'])
        assert access['from_id']==gate['id']
        route=next(r for r in plan.routes if r['id']==access['route_id'])
        gate_members=[p for p in plan.parts if p['id'].startswith('site/fence/'+gate['id']+'/')
                      and p['kind'] in ('gate_rail','gate_bar','gate_leaf','gate_frame')]
        assert min(shape(route['geometry']).distance(shape(p['geometry'])) for p in gate_members)<1e-6
        target=next(o for o in plan.envelope['openings'] if o['id']==access['to_id'])
        assert shape(target['axis']).centroid.distance(shape(gate['geometry']).centroid)<5.


def test_portal_canopy_is_supported_by_both_gate_jambs():
    plan=fixture('p5_covered_portal')
    gate=next(g for g in plan.gates if g['kind']=='vehicle')
    canopy=part(plan,'site/fence/'+gate['id']+'/canopy')
    assert canopy['material']=='corrugated'
    assert canopy['bottom_m']==pytest.approx(plan.fence['height_m'])
    for side in ('left','right'):
        support=part(plan,'site/fence/'+gate['id']+f'/{side}_post')
        assert shape(canopy['geometry']).intersection(shape(support['geometry'])).area>.001
        assert support['top_m']==pytest.approx(canopy['bottom_m'])


def test_devices_are_anchored_without_invading_gate_openings():
    plan=fixture('p5_high_fence_hidden')
    gate=next(g for g in plan.gates if g['kind']=='pedestrian')
    from planning.site_access import _line, FENCE_THICKNESS
    from planning.envelope import strip
    frame=plan.envelope['interior']['massing']['fronts'][gate['front']]
    opening=strip(_line(frame,0,frame['length_m']),*gate['interval_m'],0.,FENCE_THICKNESS,frame['inward'])
    for detail in plan.fence['details']:
        assert detail['anchor_id'] in {p['id'] for p in plan.parts}
        assert shape(part(plan,detail['id'])['geometry']).distance(
            shape(part(plan,detail['anchor_id'])['geometry']))<1e-8
        assert shape(part(plan,detail['id'])['geometry']).intersection(opening).area==0.


def test_open_rail_members_touch_their_rails_and_the_base_supports_posts():
    open_plan=fixture('p5_low_open_rail')
    for post in (p for p in open_plan.parts if p['kind']=='fence_post'):
        assert post['bottom_m']==pytest.approx(0.)
    for bar in (p for p in open_plan.parts if p['kind']=='fence_bar'):
        rails=[p for p in open_plan.parts if p['kind']=='fence_rail' and
               shape(p['geometry']).intersection(shape(bar['geometry'])).area>1e-6]
        assert any(abs(rail['top_m']-bar['bottom_m'])<1e-9 for rail in rails),bar['id']
        assert any(abs(rail['bottom_m']-bar['top_m'])<1e-9 for rail in rails),bar['id']
    base_plan=fixture('p5_base_and_rail')
    bases=[p for p in base_plan.parts if p['kind']=='fence_base']
    for post in (p for p in base_plan.parts if p['kind']=='fence_post'):
        touching=[base for base in bases if
                  shape(base['geometry']).intersection(shape(post['geometry'])).area>1e-6]
        assert touching and any(post['bottom_m']==pytest.approx(base['top_m']) for base in touching)


def test_garage_without_independent_fence_gate_keeps_two_building_connections():
    plan=fixture('p5_garage_without_fence_gate')
    assert plan.fence is None and not plan.gates
    assert {a['kind'] for a in plan.accesses}=={'pedestrian','vehicle'}
    assert {o['kind'] for o in plan.envelope['openings']} >= {'entrance','vehicle_entry'}


def test_street_edge_and_open_ground_do_not_invent_external_doors():
    edge=fixture('p5_street_edge')
    assert edge.routes[0]['transition']=='direct' and not edge.parts
    open_ground=bank('11_open_ground')
    assert open_ground.accesses[0]['to_id']=='site/open_arcade'
    assert not open_ground.gates
    assert not [o for o in open_ground.envelope['openings'] if o['kind']=='entrance']


def test_ramp_and_steps_are_floor_relative_and_fit_inside_the_free_ground():
    for name,kind in (('p5_raised_ramp','ramp'),('p5_raised_steps','steps')):
        plan=fixture(name);route=plan.routes[0]
        assert route['transition']==kind
        assert route['rise_m']==pytest.approx(plan.request['context']['levels_m'][0])
        free=shape(plan.envelope['interior']['massing']['site']['free'])
        assert free.buffer(1e-5).covers(shape(route['geometry']))
        assert route['width_m']==ACCESS_WIDTH['pedestrian']
    ramp=fixture('p5_raised_ramp').routes[0]
    assert ramp['rise_m']/ramp['length_m']<=1/12
    steps=[p for p in fixture('p5_raised_steps').parts if p['kind']=='step']
    assert len(steps)>=3
    assert max(p['top_m'] for p in steps)==pytest.approx(.5)
    assert max(p['top_m'] for p in steps)/len(steps)<=.17


def test_raised_street_edge_without_transition_returns_local_conflict():
    request=request_for(CASES/'p5_street_edge.json')
    request['context']['levels_m']=[.5,3.7,6.5]
    with pytest.raises(PlanningError) as err:plan_site(request)
    assert err.value.code=='access_run'


@pytest.mark.parametrize('parcel,fronts',[
    ([[0,0],[10,0],[10,18],[0,18]],{'F1':0,'F2':3}),
    ([[0,0],[0,18],[10,18],[10,0]],{'F1':3,'F2':0}),
])
def test_corner_front_access_is_invariant_to_parcel_winding(parcel,fronts):
    request={'version':'intent-v1','seed':17,
             'context':{'parcel':parcel,'fronts':fronts,'levels_m':[0,3.2,6]},
             'building':{'profile':'barranco_residential','organization':'compact',
                         'site':{'front_space':{'front':'F2','depth':'medium','use':'garden'},
                                 'fence':{'front':'F2','form':'open','height':'low'},
                                 'door':'left'}}}
    plan=plan_site(request)
    assert plan.fence['front']=='F2' and plan.gates[0]['front']=='F2'
    assert next(o for o in plan.envelope['openings'] if o['kind']=='entrance')['front']=='F2'
    assert plan.routes[0]['length_m']>1.
    _,audit=solids(plan)
    assert audit['watertight'] and audit['group_overlap_m3']==0.


def test_fence_without_a_setback_returns_local_conflict():
    request=request_for(CASES/'p5_street_edge.json')
    request['building']['site']={'front_space':False,
                                  'fence':{'front':'F1','form':'solid','height':'high'}}
    with pytest.raises(PlanningError) as err:plan_site(request)
    assert err.value.code in ('fence_blocked','access_outside_free')


def test_local_style_does_not_change_physical_fence_form():
    request=request_for(CASES/'p5_low_open_rail.json')
    normal=plan_site(request)
    request['building']['site']['fence']['style']='republicano'
    republican=plan_site(request)
    assert republican.fence['style']=='republicano'
    assert normal.fence['form']==republican.fence['form']=='open'
    assert [(p['id'],p['geometry'],p['material']) for p in normal.parts]==[
           (p['id'],p['geometry'],p['material']) for p in republican.parts]


def test_pedestrian_gate_style_and_material_are_local_to_the_door():
    request=request_for(CASES/'p5_low_open_rail.json')
    request['building']['site']['fence']['style']='republicano'
    request['building']['site']['door']={'position':'left','style':'clasico','material':'wood'}
    plan=plan_site(request)
    gate=next(g for g in plan.gates if g['kind']=='pedestrian')
    assert plan.fence['form']=='open' and plan.fence['style']=='republicano'
    assert gate['style']=='clasico' and gate['material']=='wood'
    assert part(plan,'site/fence/'+gate['id']+'/leaf')['material']=='wood'


def test_same_site_intent_is_deterministic():
    path=CASES/'p5_high_fence_hidden.json'
    first=plan_site(request_for(path)).to_dict()
    second=plan_site(request_for(path)).to_dict()
    assert json.dumps(first,sort_keys=True)==json.dumps(second,sort_keys=True)


def test_export_contains_site_drawings_and_watertight_glb(tmp_path):
    output=tmp_path/'site'
    report=export_site(fixture('p5_high_fence_hidden'),output)
    assert all((output/name).exists() for name in
               ('plan.json','summary.json','site.glb','preview.png','ground.png','front.png'))
    assert report['audit']['watertight'] and report['audit']['group_overlap_m3']==0.


def test_ramp_mesh_is_a_closed_wedge_not_a_flat_slab():
    plan=fixture('p5_raised_ramp');meshes,audit=solids(plan)
    ramp=next(mesh for name,_,mesh in meshes if name.endswith('/ramp'))
    assert ramp.is_watertight and ramp.volume>0
    assert max(ramp.vertices[:,2])-min(ramp.vertices[:,2])==pytest.approx(.2)
    assert audit['group_overlap_m3']==0.
