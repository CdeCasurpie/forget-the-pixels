import copy
import json
from pathlib import Path

import numpy as np
import pytest
from shapely.affinity import rotate, translate
from shapely.geometry import Polygon, shape
from shapely.ops import unary_union

from domain.architectural_plan import PlanningError
from domain.building_intent import ORGANIZATIONS
from planning.massing import plan_massing, front_frames, local, world
from planning.massing_export import solids, export_plan


def request():
    return {'version':'intent-v1','seed':17,'context':{
        'parcel':[[0,0],[12,0],[12,18],[0,18]],'fronts':{'F1':0},
        'levels_m':[0,3.2,6.,8.8]},'building':{}}


def operation(kind, **kwargs):
    return dict(id='op',kind=kind,body='main',front='F1',**kwargs)


def footprint(plan,floor=1):
    return unary_union([shape(s['geometry']) for s in plan.storeys if s['floor']==floor])


def test_input_preserved_and_deterministic():
    d=request();before=copy.deepcopy(d)
    a=plan_massing(d);b=plan_massing(d)
    assert d==before and a.to_dict()==b.to_dict()
    assert a.request==d


@pytest.mark.parametrize('org',ORGANIZATIONS)
@pytest.mark.parametrize('dimensions',[(5,20),(18,12),(10,18)])
def test_organizations_on_three_parcel_aspects(org,dimensions):
    d=request();w,h=dimensions;d['context']['parcel']=[[0,0],[w,0],[w,h],[0,h]]
    d['building']['organization']=org
    plan=plan_massing(d)
    assert plan.checks['area_balance_error_m2']<1e-7
    assert plan.checks['parcel_containment']
    assert len(plan.storeys)==3
    assert all(mesh.is_watertight and mesh.volume>0 for _,mesh in solids(plan))


@pytest.mark.parametrize('kind',['setback','bite','courtyard','chamfer'])
def test_cuts_have_real_effect_and_record_removed_area(kind):
    d=request();d['building']['operations']=[operation(kind,position='left',depth='medium',floors=[3])]
    p=plan_massing(d)
    assert footprint(p,3).area<footprint(p,2).area
    rec=p.operations[0]['floors'][0]
    assert shape(rec['removed']).area==pytest.approx(rec['before_m2']-rec['after_m2'])
    assert footprint(p,2).covers(footprint(p,3))


def test_courtyard_is_hole_and_not_filled_in_mesh():
    d=request();d['building']['operations']=[operation('courtyard')]
    p=plan_massing(d)
    assert len(footprint(p).interiors)==1
    expected=sum(shape(s['geometry']).area*(s['top_m']-s['bottom_m']) for s in p.storeys)
    assert sum(m.volume for _,m in solids(p))==pytest.approx(expected)
    assert shape(p.site['uncovered']).covers(Polygon(footprint(p).interiors[0]))


def test_open_ground_separates_free_covered_and_occupied():
    d=request();d['building']['operations']=[operation('open_ground')]
    p=plan_massing(d)
    assert p.storeys[0]['kind']=='open' and p.storeys[1]['kind']=='enclosed'
    assert p.supports and all(s['kind']=='column' for s in p.supports)
    assert p.checks['covered_free_m2']>100
    occupied=shape(p.site['occupied']);free=shape(p.site['free'])
    assert occupied.intersection(free).area<1e-8
    assert occupied.union(free).area==pytest.approx(216)


def test_front_frame_winding_invariance():
    a=request();b=copy.deepcopy(a)
    b['context']['parcel']=[[0,0],[0,18],[12,18],[12,0]]
    b['context']['fronts']={'F1':3}
    a['building']['operations']=[operation('bite',position='left')]
    b['building']=copy.deepcopy(a['building'])
    pa=plan_massing(a);pb=plan_massing(b)
    assert pa.fronts==pb.fronts
    assert footprint(pa).symmetric_difference(footprint(pb)).area<1e-7
    f=pa.fronts['F1'];assert f['right']==[1.,0.] and f['inward']==[-0.,1.]


def test_rotation_and_translation_equivariance():
    d=request();d['building']['operations']=[operation('bite',position='right')]
    a=plan_massing(d)
    polygon=translate(rotate(Polygon(d['context']['parcel']),31,origin=(0,0)),100,-50)
    d['context']['parcel']=[list(p) for p in list(polygon.exterior.coords)[:-1]]
    b=plan_massing(d)
    expected=translate(rotate(footprint(a),31,origin=(0,0)),100,-50)
    assert expected.symmetric_difference(footprint(b)).area<1e-6


def test_secondary_front_cut():
    d=request();d['context']['fronts']['F2']=3
    op=operation('setback',floors=[3]);op['front']='F2';d['building']['operations']=[op]
    p=plan_massing(d)
    assert footprint(p,3).bounds[0]>footprint(p,2).bounds[0]
    assert footprint(p,3).bounds[1]==pytest.approx(footprint(p,2).bounds[1])


def test_explicit_body_order_is_irrelevant_and_no_overlap():
    d=request();d['building']['bodies']=[{'id':'main'}, {'id':'wing','position':'rear','width':'narrow','floors':[1]}]
    a=plan_massing(d);d['building']['bodies'].reverse();b=plan_massing(d)
    assert a.storeys==b.storeys
    ground=[shape(s['geometry']) for s in a.storeys if s['floor']==1]
    assert ground[0].intersection(ground[1]).area<1e-7
    assert ground[0].boundary.intersection(ground[1].boundary).length>1


@pytest.mark.parametrize('kind',['recess','depth_rhythm','floor_shift','loggia','crown','round_corner'])
def test_future_operations_preserved_not_claimed_as_applied(kind):
    d=request();op=operation(kind)
    if kind=='depth_rhythm':op.update(weights=[1,2,1],planes=['base','recessed','base'])
    d['building']['operations']=[op]
    p=plan_massing(d)
    assert p.request['building']['operations']==[op]
    assert p.operations[0]['status']=='pending'
    assert p.pending[0]['id']=='op'


def test_attachment_adds_connected_volume():
    d=request();d['building']['operations']=[operation('attach',position='rear')]
    p=plan_massing(d);r=p.operations[0]['floors'][0]
    assert r['after_m2']>r['before_m2']
    assert footprint(p).geom_type=='Polygon'


@pytest.mark.parametrize('kind',['advance','overhang'])
def test_projections_add_volume_and_support(kind):
    d=request();d['building']['operations']=[operation(kind,floors=[2,3],depth='shallow')]
    p=plan_massing(d)
    assert all(r['after_m2']>r['before_m2'] for r in p.operations[0]['floors'])
    assert any(s['kind'] in ('cantilever','column') for s in p.supports)


def test_unsupported_floating_body_rejected():
    d=request();d['building']['bodies']=[{'id':'main','floors':[2,3]}]
    with pytest.raises(PlanningError,match='unsupported_storey'):plan_massing(d)


def test_no_fence_does_not_remove_setback():
    d=request();d['building']['site']={'fence':False,'front_space':{'front':'F1','depth':'medium'}}
    p=plan_massing(d)
    assert footprint(p).bounds[1]>0


def test_seeds_change_dimensions_not_operation_inventory():
    d=request();d['building']['operations']=[operation('setback',floors=[3])]
    a=plan_massing(d);d['seed']=81;b=plan_massing(d)
    assert [x['id'] for x in a.storeys]==[x['id'] for x in b.storeys]
    assert [x['id'] for x in a.operations]==[x['id'] for x in b.operations]
    assert abs(footprint(a,3).area-footprint(b,3).area)>.01


def test_small_parcel_conflict_is_localized():
    d=request();d['context']['parcel']=[[0,0],[1,0],[1,2],[0,2]]
    with pytest.raises(PlanningError) as error:plan_massing(d)
    assert error.value.code=='unusable_body' and error.value.path


def test_raised_ground_floor_has_base_instead_of_floating():
    d=request();d['context']['levels_m']=[.6,3.8,6.6,9.4];d['context']['ground_z_m']=0
    p=plan_massing(d)
    base=next(s for s in p.supports if s['kind']=='plinth')
    assert base['bottom_m']==0 and base['top_m']==.6
    assert min(mesh.bounds[0,2] for _,mesh in solids(p))==0


def test_explicit_primary_position_and_width_affect_plan():
    d=request();d['building']['bodies']=[{'id':'main','position':'right','width':'narrow'}]
    p=plan_massing(d)
    assert footprint(p).bounds[0]>8
    assert footprint(p).bounds[2]==12


def test_partial_setback_preserves_other_side():
    d=request();d['building']['operations']=[operation('setback',floors=[3],position='right',width='narrow')]
    p=plan_massing(d)
    assert footprint(p,3).bounds[1]==footprint(p,2).bounds[1]
    assert footprint(p,3).area<footprint(p,2).area


def test_operation_list_order_does_not_change_geometry():
    d=request();d['building']['operations']=[
        dict(id='bite',kind='bite',body='main',front='F1',position='left'),
        dict(id='setback',kind='setback',body='main',front='F1',floors=[3],after=['bite'])]
    a=plan_massing(d);d['building']['operations'].reverse();b=plan_massing(d)
    assert a.storeys==b.storeys and a.operations==b.operations


def test_impossible_courtyard_has_diagnostic_not_missing_operation():
    d=request();d['context']['parcel']=[[0,0],[2,0],[2,12],[0,12]]
    d['building']['operations']=[operation('courtyard')]
    with pytest.raises(PlanningError,match='courtyard_clearance'):plan_massing(d)


def test_source_fixture_bank_not_changed_by_planning():
    root=Path(__file__).parents[1]/'experiments/phase0/cases'
    for path in root.glob('*/*.json'):
        raw=path.read_bytes();d=json.loads(raw)['request'];plan_massing(d)
        assert path.read_bytes()==raw


def test_surfaces_preserve_courtyard_normals_and_hide_body_joins():
    d=request();d['building']['operations']=[operation('courtyard')]
    p=plan_massing(d)
    inner=[s for s in p.storeys[0]['surfaces'] if s['kind']=='courtyard']
    assert len(inner)==4 and all(s['front'] is None for s in inner)
    poly=footprint(p)
    from shapely.geometry import Point
    for surface in inner:
        a,b=surface['line'];mid=(np.asarray(a)+b)/2
        assert not poly.contains(Point(mid+np.asarray(surface['normal'])*.1))
    d=request();d['building']['bodies']=[{'id':'main'},{'id':'rear','position':'rear','floors':[1]}]
    p=plan_massing(d)
    perimeter=sum(s['length_m'] for row in p.storeys if row['floor']==1 for s in row['surfaces'])
    assert perimeter==pytest.approx(footprint(p).length)


def test_export_glb_and_diagnostics(tmp_path):
    import trimesh
    p=plan_massing(request());report=export_plan(p,tmp_path/'case',preview=False)
    loaded=trimesh.load(tmp_path/'case/massing.glb',force='scene')
    assert len(loaded.geometry)==3
    assert report['all_components_watertight']
    assert json.loads((tmp_path/'case/plan.json').read_text())['version']=='massing-plan-v1'


@pytest.mark.parametrize('seed',[7,17,81])
def test_frozen_bank_geometry_and_pending_inventory(seed):
    root=Path(__file__).parents[1]/'experiments/phase0/cases'
    for path in root.glob('*/*.json'):
        case=json.loads(path.read_text());d=case['request'];d['seed']=seed
        p=plan_massing(d)
        assert p.checks['area_balance_error_m2']<1e-7
        assert {r['id'] for r in p.operations}=={o['id'] for o in d['building'].get('operations',[])}
        assert all(m.is_watertight and m.volume>0 for _,m in solids(p))
