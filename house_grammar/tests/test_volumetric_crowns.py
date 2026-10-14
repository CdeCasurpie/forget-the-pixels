import json
from dataclasses import replace
import numpy as np
import pytest
import trimesh
from shapely.geometry import box
from domain.crowns import CrownDesign
from domain.theta import from_json,canonical
from modeling.crown_catalog import FAMILIES,classify
from modeling.crown_assembly import build_crown,aperture_shape
from modeling.mesh_builder import MeshBuilder
from pipeline.theta import reconstruct


def solids(mesh):
    for part in mesh.parts:
        ff=mesh.faces[part['face_start']:part['face_start']+part['face_count']]
        vv,index=np.unique(ff,return_inverse=True)
        solid=trimesh.Trimesh(mesh.vertices[vv],index.reshape(-1,3),process=False)
        assert solid.is_watertight,part['name']
        assert solid.is_winding_consistent,part['name']
        assert solid.volume>0,part['name']


@pytest.mark.parametrize('family',FAMILIES)
@pytest.mark.parametrize('size',[1.,1.5])
def test_all_crown_families_closed_with_real_depth(family,size):
    mb=MeshBuilder(box(-10,-10,20,20))
    w=4.8*size;h=(2.4 if family=='semicircular' else 1.8)*size
    build_crown(mb,(0,0),(1,0),(0,-1),0,4,w,h,CrownDesign(family=family,style='republicano',thickness_m=.4))
    mesh=mb.finish();solids(mesh)
    assert np.ptp(mesh.vertices[:,1])>.5
    assert mesh.vertices[:,2].max()==pytest.approx(4+h)
    assert {'crown_body','crown_moulding','crown_inner_bead','crown_base_cornice'}<={p['name'] for p in mesh.parts}


@pytest.mark.parametrize('kind',['oculus','roundhead','pointed'])
def test_aperture_is_a_real_hole_with_closed_reveals(kind):
    mb=MeshBuilder(box(-10,-10,20,20))
    hole=aperture_shape(kind,.6,.8,.4,2.4)
    build_crown(mb,(0,0),(1,0),(0,-1),0,0,4.8,2.2,CrownDesign(family='curved_pointed',style='republicano'),hole)
    mesh=mb.finish();solids(mesh)
    from shapely.geometry import Polygon
    for part in mesh.parts:
        if part['name'] not in ('crown_body','crown_rim'):continue
        for face in mesh.faces[part['face_start']:part['face_start']+part['face_count']]:
            tri=Polygon(mesh.vertices[face][:,[0,2]])
            assert tri.intersection(hole.buffer(-1e-6)).area<1e-8


def request():
    return dict(context=dict(parcel=[[0,0],[20,0],[20,20],[0,20]],fronts=[0]),theta=dict(
        schema_version='0.3',architectural_style='republicano',massing=dict(pattern='explicit'),
        masses=[dict(role='house',footprint=[[3,3],[17,3],[17,17],[3,17]],levels_m=[0,4])],
        facade=dict(mode='explicit',openings=[],projections=[],material_regions=[]),
        roof=dict(kind='flat',parapet_m=0,props=[]),site=dict(fence='none',runs=[],garden=False),
        trim=dict(cornice=dict(enabled=False),plinth=dict(enabled=False)),
        crowns=[dict(id='crown',mass_ref='house:0',edge=0,u_m=4,width_m=6,height_m=2,
                     design=dict(silhouette='mixed',stepped=True))]))


def test_classification_and_pipeline_roundtrip():
    r=from_json(json.dumps(request()));result=reconstruct(r)
    c=result.resolved.crowns[0]
    assert c.controls.design.family=='stepped_segmental'
    assert 'curved' in c.classification_reason
    assert c.base_z==4
    assert canonical(r)==canonical(from_json(canonical(r)))


@pytest.mark.parametrize('attributes,family',[
    ({'open_center':True},'broken'),({'concave_shoulders':True},'concave_shoulders'),
    ({'central_block':True},'rectangular_attic'),({'silhouette':'pointed'},'curved_pointed')])
def test_attribute_classification(attributes,family):
    assert classify(CrownDesign(**attributes))[0]==family


@pytest.mark.parametrize('change,match',[
    ({'mass_ref':'absent'},'mass missing'),({'u_m':-1},'span'),
    ({'base_m':1},'contact'),({'aperture':'oculus','aperture_width_m':8},'fit'),
    ({'design':dict(style='barroco')},'conflicts'),
    ({'design':dict(thickness_m=.03)},'thickness'),
    ({'design':dict(family='semicircular')},'height'),
])
def test_invalid_configuration_rejected(change,match):
    r=request();r['theta']['crowns'][0].update(change)
    with pytest.raises(ValueError,match=match):reconstruct(from_json(json.dumps(r)))


def test_entablature_continuous_across_adjacent_masses():
    r=request();t=r['theta'];t['crowns']=[]
    t['masses']=[dict(role='left',footprint=[[3,3],[10,3],[10,17],[3,17]],levels_m=[0,4]),
                 dict(role='right',footprint=[[10,3],[17,3],[17,17],[10,17]],levels_m=[0,4])]
    t['entablatures']=[dict(id='shared',scope='street')]
    result=reconstruct(from_json(json.dumps(r)))
    pieces=[x for x in result.resolved.trims if x.semantic=='entablature_cornice']
    assert len(pieces)==1
    from shapely.geometry import LineString
    assert LineString(pieces[0].path).length==pytest.approx(14.)
    assert set(pieces[0].sources)=={'left:0','right:0'}


def test_explicit_fronton_does_not_invent_apertures():
    result=reconstruct(from_json(json.dumps(request())))
    assert all(not w.facade.openings for w in result.resolved.walls)
    assert 'crown_glass' not in {p['name'] for p in result.mesh.parts}


@pytest.mark.parametrize('style',['republicano','barroco','clasico','madera','moderno'])
@pytest.mark.parametrize('ornament',['keystone','cartouche','volutes','dentils'])
def test_style_profiles_and_procedural_ornaments_are_solids(style,ornament):
    mb=MeshBuilder(box(-10,-10,20,20))
    build_crown(mb,(0,0),(0,1),(1,0),0,0,5,1.8,
                CrownDesign(family='segmental',style=style,ornament=ornament))
    solids(mb.finish())


def test_entablature_takes_over_upper_trim_without_duplicate_cornice():
    r=request();r['theta']['trim']['cornice']={'enabled':True,'profile':'republicano'}
    r['theta']['entablatures']=[dict(id='upper',scope='exposed')]
    result=reconstruct(from_json(json.dumps(r)))
    assert any(p.semantic=='entablature_cornice' for p in result.resolved.trims)
    assert not any(p.semantic=='trim_cornice' for p in result.resolved.trims)
