import json
from dataclasses import asdict, replace
import numpy as np
import pytest
import trimesh
from shapely.geometry import box
from domain.vertical_members import MemberDesign
from domain.theta import from_json, canonical
from modeling.mesh_builder import MeshBuilder
from modeling.vertical_member_catalog import CATALOG
from modeling.vertical_member_assembly import build_member
from modeling.grammar import ZOffsetMeshBuilder
from modeling.visibility import VisibleFacadeBuilder
from pipeline.theta import reconstruct


def assert_solids(mesh):
    assert np.isfinite(mesh.vertices).all()
    for p in mesh.parts:
        faces=mesh.faces[p['face_start']:p['face_start']+p['face_count']]
        used,local=np.unique(faces,return_inverse=True)
        solid=trimesh.Trimesh(mesh.vertices[used],local.reshape(-1,3),process=False)
        assert solid.is_watertight,p['name']
        assert solid.is_winding_consistent,p['name']
        assert solid.volume>0,p['name']


@pytest.mark.parametrize('style,variant',[(s,v) for s,f in CATALOG.items() for v in f])
@pytest.mark.parametrize('height,width',[(2.1,.32),(4.5,.65)])
def test_catalogue_closed_and_proportioned(style,variant,height,width):
    mb=MeshBuilder(box(-3,-3,3,3))
    build_member(mb,(0,0),(1,0),(0,-1),1,width,width,height,MemberDesign(style=style,variant=variant))
    mesh=mb.finish();assert_solids(mesh)
    assert mesh.vertices[:,2].min()==pytest.approx(1)
    assert mesh.vertices[:,2].max()==pytest.approx(1+height)


def request(member=None):
    return dict(context=dict(parcel=[[0,0],[15,0],[15,15],[0,15]],fronts=[0]),theta=dict(
        schema_version='0.3',architectural_style='republicano',massing=dict(pattern='explicit'),
        masses=[dict(role='house',footprint=[[3,3],[12,3],[12,12],[3,12]],levels_m=[0,3.5,7])],
        facade=dict(mode='explicit',openings=[],projections=[],material_regions=[]),
        roof=dict(kind='flat',parapet_m=0,props=[]),site=dict(fence='none',runs=[],garden=False),
        trim=dict(cornice=dict(enabled=False),plinth=dict(enabled=False)),
        vertical_members=[member or dict(id='sample',mass_ref='house:0',edge=0,u_m=2.,bottom_m=0.,height_m=3.5,
                                       width_m=.5,depth_m=.25)]))


def test_pipeline_roundtrip_offset_and_style_inheritance():
    r=request();r['theta']['vertical_members'][0]['bottom_m']=3.5
    parsed=from_json(json.dumps(r));result=reconstruct(parsed)
    member=result.resolved.vertical_members[0]
    assert member.bottom==3.5
    assert member.controls.design.style=='republicano'
    assert canonical(parsed)==canonical(from_json(canonical(parsed)))
    parts=[p for p in result.mesh.parts if p['assembly_id']=='vertical_member/sample']
    faces=np.concatenate([result.mesh.faces[p['face_start']:p['face_start']+p['face_count']] for p in parts])
    assert result.mesh.vertices[np.unique(faces),2].min()==pytest.approx(3.5)


@pytest.mark.parametrize('changes,match',[
    ({'width_m':float('nan')},'finite number'),
    ({'placement':'missing'},'placement'),
    ({'offset_m':10},'envelope'),
    ({'mass_ref':'missing'},'mass'),
    ({'u_m':9.},'span'),
    ({'height_m':9.},'facade band'),
    ({'design':dict(style='moderno')},'conflicts'),
    ({'design':dict(style='republicano',section='circle')},'equal width'),
])
def test_invalid_members_rejected(changes,match):
    r=request();r['theta']['vertical_members'][0].update(changes)
    with pytest.raises(ValueError,match=match):reconstruct(from_json(json.dumps(r)))


def test_clipped_loft_remains_closed_and_z_offset_applied_once():
    mb=MeshBuilder(box(-.2,-1,.2,1))
    local=ZOffsetMeshBuilder(mb,4.)
    build_member(local,(0,0),(1,0),(0,-1),0,.5,.5,3.,MemberDesign(style='clasico'))
    mesh=mb.finish();assert_solids(mesh)
    assert mesh.vertices[:,0].min()>=-.200001 and mesh.vertices[:,0].max()<=.200001
    assert mesh.vertices[:,2].min()==pytest.approx(4.)
    assert mesh.vertices[:,2].max()==pytest.approx(7.)


def test_visibility_clips_member_without_leaking_into_hidden_band():
    mb=MeshBuilder(box(-2,-2,2,2))
    local=VisibleFacadeBuilder(mb,(-1,0),(1,0),((0.,.5,2.,2.5),))
    build_member(local,(0,0),(1,0),(0,-1),0,.5,.5,3.,MemberDesign(style='clasico'))
    mesh=mb.finish();assert_solids(mesh)
    assert mesh.vertices[:,2].min()==pytest.approx(.5)
    assert mesh.vertices[:,2].max()==pytest.approx(2.5)


def test_panel_is_recessed_and_modern_plain_has_no_added_blocks():
    mb=MeshBuilder(box(-2,-2,2,2))
    build_member(mb,(0,0),(1,0),(0,1),0,.6,.3,3,MemberDesign(style='republicano',variant='recessed_panel',taper=0,entasis=0))
    mesh=mb.finish()
    mid=mesh.vertices[(mesh.vertices[:,2]>1)&(mesh.vertices[:,2]<2)]
    assert np.min(np.abs(mid[:,1]))<.13
    mb=MeshBuilder(box(-2,-2,2,2))
    build_member(mb,(0,0),(1,0),(0,1),0,.6,.3,3)
    assert [p['name'] for p in mb.finish().parts]==['member_shaft']


def test_corner_single_assembly_and_duplicate_rejected():
    r=request();r['theta']['vertical_members'][0].update(u_m=0,placement='corner')
    result=reconstruct(from_json(json.dumps(r)))
    assert len(result.resolved.vertical_members)==1
    duplicate=dict(r['theta']['vertical_members'][0],id='other')
    r['theta']['vertical_members'].append(duplicate)
    with pytest.raises(ValueError,match='Overlapping'):reconstruct(from_json(json.dumps(r)))


def test_opening_conflict_and_disabled_member():
    r=request();r['theta']['facade']['openings']=[dict(kind='window',u_m=1.8,v_m=1.,width_m=.8,height_m=1.)]
    with pytest.raises(ValueError,match='opening'):reconstruct(from_json(json.dumps(r)))
    r['theta']['vertical_members'][0]['enabled']=False
    assert not reconstruct(from_json(json.dumps(r))).resolved.vertical_members


def test_independent_remates_and_materials_preserve_total_height():
    d=MemberDesign(style='republicano',variant='smooth_moulded',base=False,capital=False,
                   pedestal_m=.2,base_material='stone',material='wood')
    mb=MeshBuilder(box(-3,-3,3,3))
    build_member(mb,(0,0),(1,0),(0,-1),0,.5,.3,3,d)
    mesh=mb.finish();assert_solids(mesh)
    assert {p['name'] for p in mesh.parts}=={'member_pedestal','member_shaft'}
    assert mesh.vertices[:,2].max()==pytest.approx(3)
    assert len(np.unique(mesh.face_materials))==2


def test_member_projection_uses_shared_generator_at_upper_floor():
    r=request();r['theta']['vertical_members']=[]
    r['theta']['facade']['projections']=[dict(kind='pilaster',u_m=1.,v_m=3.5,width_m=.4,height_m=3.,depth_m=.2,
                                           member=dict(style='auto',variant='recessed_panel'))]
    result=reconstruct(from_json(json.dumps(r)))
    names={p['name'] for p in result.mesh.parts}
    assert 'member_shaft' in names
    assert not names&{'pilaster','pilaster_cap','pilaster_base','pilaster_fluted_shaft'}
