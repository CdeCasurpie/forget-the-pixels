import copy
import json
from pathlib import Path

import pytest
from shapely.geometry import shape, box
from shapely.ops import unary_union

from domain.architectural_plan import PlanningError
from planning.articulation import plan_articulation, solid_sections
from planning.massing import local
from planning.massing_export import solids, export_plan


def request(kind, **kwargs):
    return dict(version='intent-v1',seed=17,context=dict(
        parcel=[[0,0],[10,0],[10,18],[0,18]],fronts={'F1':0},levels_m=[0,3.2,6,8.8]),
        building=dict(operations=[dict(id='depth',kind=kind,body='main',front='F1',floors=[2],**kwargs)]))


@pytest.mark.parametrize('kind',['loggia','portico','vestibule','balcony'])
def test_space_has_floor_void_access_and_protection(kind):
    d=request(kind)
    if kind=='balcony':d['building']['site']={'front_space':{'front':'F1','depth':'medium'}}
    p=plan_articulation(d);row=p.storeys[1];s=row['spaces'][0]
    zone=shape(s['geometry']);access=shape(s['access']['geometry'])
    assert s['protection'] and s['access']['status']=='reserved_for_phase3'
    sections=solid_sections(row)
    floor=sections[0][0]
    assert floor.covers(zone)
    # At eye level neither a solid block nor a parapet blocks the space/access.
    middle=next(g for g,z0,z1 in sections if z0<row['bottom_m']+1.6<z1)
    assert middle.intersection(zone).area<1e-7
    assert middle.intersection(access).area<1e-7
    if kind!='balcony':assert sections[-1][0].covers(zone)
    assert all(m.is_watertight and m.volume>0 for _,m in solids(p))


def test_ground_portico_is_free_covered_without_parapet():
    d=request('portico');d['building']['operations'][0]['floors']=[1]
    p=plan_articulation(d)
    s=p.storeys[0]['spaces'][0]
    assert s['protection'] is None
    assert p.checks['covered_free_m2']==pytest.approx(shape(s['geometry']).area)


def test_projecting_rhythm_is_forward_of_base_inside_parcel():
    d=request('depth_rhythm',weights=[1,1,1],planes=['base','recessed','projecting'])
    p=plan_articulation(d);poly=local(shape(p.storeys[1]['geometry']),p.fronts['F1'])
    ys=[poly.intersection(box(a+.01,-1,b-.01,18)).bounds[1] for a,b in [(0,10/3),(10/3,20/3),(20/3,10)]]
    assert ys[2]<ys[0]<ys[1]
    assert p.checks['parcel_containment']


def test_floor_shift_alternates_without_random_inventory_changes():
    d=request('floor_shift');d['building']['operations'][0]['floors']=[2,3]
    p=plan_articulation(d)
    assert shape(p.storeys[1]['geometry']).centroid.x>shape(p.storeys[2]['geometry']).centroid.x


def test_balcony_without_setback_has_explicit_conflict():
    with pytest.raises(PlanningError,match='space_outside_parcel'):plan_articulation(request('balcony'))


def test_spaces_cannot_overlap():
    d=request('loggia');second=copy.deepcopy(d['building']['operations'][0]);second['id']='other'
    d['building']['operations'].append(second)
    with pytest.raises(PlanningError,match='space_overlap'):plan_articulation(d)


def test_determinism_and_request_preservation():
    d=request('loggia');before=copy.deepcopy(d)
    assert plan_articulation(d).to_dict()==plan_articulation(d).to_dict()
    assert d==before


@pytest.mark.parametrize('seed',[7,17,81])
def test_bank_phase2(seed):
    for path in (Path(__file__).parents[1]/'experiments/phase0/cases').glob('*/*.json'):
        d=json.loads(path.read_text())['request'];d['seed']=seed
        p=plan_articulation(d)
        assert not any(o.get('kind') in ('loggia','depth_rhythm','floor_shift') for o in p.pending)
        assert p.checks['area_balance_error_m2']<1e-7
        assert all(m.is_watertight and m.is_winding_consistent and m.volume>0 for _,m in solids(p))


def test_preview_and_glb_export(tmp_path):
    report=export_plan(plan_articulation(request('loggia')),tmp_path/'loggia')
    assert report['all_components_watertight']
    assert (tmp_path/'loggia/preview.png').stat().st_size>0


def test_layered_union_removes_interfaces_and_conserves_volume():
    import numpy as np
    from planning.layered_mesh import layered_mesh
    # Intersecting solids with mismatched XY and Z edges exercise T-junctions.
    a=box(0,0,4,4);b=box(2,1,5,3)
    mesh=layered_mesh([(a,0,3),(b,1,4)])
    expected=a.area*3+b.area*3-a.intersection(b).area*2
    assert mesh.volume==pytest.approx(expected)
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert len(np.unique(np.sort(mesh.faces,axis=1),axis=0))==len(mesh.faces)


def test_space_floor_uses_context_finish_elevation():
    p=plan_articulation(request('loggia'));row=p.storeys[1]
    zone=shape(row['spaces'][0]['geometry'])
    slab=solid_sections(row)[0]
    assert slab[2]==row['bottom_m']
    middle=next(g for g,a,b in solid_sections(row) if a<row['bottom_m']+.1<b)
    assert middle.intersection(zone).area<zone.area*.2


def test_raised_entry_requires_protection():
    d=request('vestibule');d['context']['levels_m']=[.8,4.,6.8,9.6]
    d['context']['ground_z_m']=0;d['building']['operations'][0]['floors']=[1]
    p=plan_articulation(d)
    assert p.storeys[0]['spaces'][0]['protection'] is not None


@pytest.mark.parametrize('kind',['loggia','depth_rhythm','floor_shift'])
def test_articulation_rotation_invariance(kind):
    from shapely.affinity import rotate,translate
    from shapely.geometry import Polygon
    kwargs=dict(weights=[1,2,1],planes=['base','recessed','projecting']) if kind=='depth_rhythm' else {}
    d=request(kind,**kwargs);a=plan_articulation(d)
    parcel=translate(rotate(Polygon(d['context']['parcel']),31,origin=(0,0)),100,-50)
    d['context']['parcel']=[list(p) for p in list(parcel.exterior.coords)[:-1]]
    b=plan_articulation(d)
    for row,other in zip(a.storeys,b.storeys):
        expected=translate(rotate(shape(row['enclosed_geometry']),31,origin=(0,0)),100,-50)
        assert expected.symmetric_difference(shape(other['enclosed_geometry'])).area<1e-5


def test_low_headroom_has_localized_diagnostic():
    d=request('loggia');d['context']['levels_m']=[0,3.2,5.2,8.8]
    with pytest.raises(PlanningError,match='space_headroom'):plan_articulation(d)


def test_comparison_bank_has_closed_slab_return_joints():
    import runpy
    cases=runpy.run_path(str(Path(__file__).parents[1]/'experiments/phase2/compare.py'))['cases']
    for name,d in cases():
        p=plan_articulation(d)
        assert all(m.is_watertight and m.is_winding_consistent and m.volume>0 for _,m in solids(p)),name
