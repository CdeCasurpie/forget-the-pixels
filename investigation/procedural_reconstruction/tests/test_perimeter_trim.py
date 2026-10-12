import json
import numpy as np
import pytest
import trimesh
from shapely.geometry import Polygon, LineString, box
from domain.theta import CorniceControls, PlinthControls, from_json
from modeling.mesh_builder import MeshBuilder
from modeling.trim_profiles import CORNICES, cornice_section
from modeling.trim_sweep import emit_sweep, sweep_domain
from modeling.trim_resolver import plinth_pieces
from pipeline.theta import reconstruct


def request():
    return dict(context=dict(parcel=[[0,0],[10,0],[10,10],[0,10]],fronts=[0,1]),
                theta=dict(schema_version='0.3',height_m=6.,floors=2,architectural_style='republicano',
                           trim=dict(cornice={},plinth=dict(enabled=False)),
                           facade=dict(mode='explicit',openings=[],projections=[],material_regions=[]),
                           side_material='plaster',roof=dict(kind='flat',parapet_m=0.,props=[]),
                           site=dict(fence='none',runs=[],garden=False)))


@pytest.mark.parametrize('style',CORNICES)
@pytest.mark.parametrize('path',[
    [(1,1),(4,1),(4,4),(1,4),(1,1)],
    [(1,1),(4,1),(4,2),(2,2),(2,4),(1,4),(1,1)],
    [(1,1),(4,1),(4,4)],
])
def test_profile_sweep_is_closed_oriented_and_continuous(style,path):
    envelope=box(-2,-2,8,8)
    mb=MeshBuilder(envelope)
    section=cornice_section(CorniceControls(),style)
    emit_sweep(mb,path,section,3.,'cornice','trim_cornice',envelope)
    mesh=mb.finish()
    solid=trimesh.Trimesh(mesh.vertices,mesh.faces,process=False)
    assert solid.is_watertight
    assert solid.is_winding_consistent
    assert solid.volume>0
    assert np.isfinite(mesh.vertices).all()
    assert mesh.vertices[:,2].max()==pytest.approx(3.24)


def test_sweep_does_not_silently_clip():
    with pytest.raises(ValueError,match='envelope'):
        emit_sweep(MeshBuilder(box(0,0,4,4)),[(0,0),(4,0)],
                   cornice_section(CorniceControls(),'clasico'),3.,'cornice','trim_cornice',box(0,0,4,4))


def test_pipeline_crown_top_and_off_switch():
    r=request()
    result=reconstruct(from_json(json.dumps(r)))
    assert result.resolved.trims
    assert all(p.base_z+max(z for d,z in p.section)==pytest.approx(6.) for p in result.resolved.trims)
    r['theta']['trim']['cornice']['enabled']=False
    result=reconstruct(from_json(json.dumps(r)))
    assert not result.resolved.trims
    assert not {'top_cornice','plinth','floor_band','floor_slab'} & {p['name'] for p in result.mesh.parts}


def test_stacked_identical_masses_only_crown_upper():
    r=request()
    r['theta'].update(height_m=None,floors=None,massing=dict(pattern='explicit'))
    r['theta']['masses']=[dict(role='lower',footprint=[[1,1],[8,1],[8,8],[1,8]],levels_m=[0,3]),
                          dict(role='upper',footprint=[[1,1],[8,1],[8,8],[1,8]],levels_m=[3,6])]
    result=reconstruct(from_json(json.dumps(r)))
    assert len(result.resolved.trims)==1
    assert result.resolved.trims[0].base_z==pytest.approx(5.76)


def test_setback_crowns_exposed_lower_edge():
    r=request()
    r['theta'].update(height_m=None,floors=None,massing=dict(pattern='explicit'))
    r['theta']['masses']=[dict(role='lower',footprint=[[1,1],[8,1],[8,8],[1,8]],levels_m=[0,3]),
                          dict(role='upper',footprint=[[1,3],[8,3],[8,8],[1,8]],levels_m=[3,6])]
    result=reconstruct(from_json(json.dumps(r)))
    lower=[p for p in result.resolved.trims if p.base_z<3]
    assert lower
    assert all(LineString(p.path).intersection(LineString([(1,8),(8,8)])).length<1e-6 for p in lower)


def test_plinth_door_cut_and_window_sill():
    r=request()
    r['theta']['trim']['plinth']=dict(design='blocks',height_m=1.2)
    r['theta']['facade']['openings']=[dict(kind='door',u_m=2.,v_m=0.,width_m=1.,height_m=2.5),
                                     dict(kind='window',u_m=5.,v_m=.8,width_m=1.,height_m=1.2)]
    result=reconstruct(from_json(json.dumps(r)))
    pieces=[p for p in result.resolved.trims if p.semantic=='trim_plinth']
    door=box(2.,-.2,3.,.001)
    assert all(sweep_domain(p.path,p.section).intersection(door).area<1e-8 for p in pieces)
    assert any(p.base_z<.8 and LineString(p.path).intersection(LineString([(5,0),(6,0)])).length>.1 for p in pieces)


def test_flush_plinth_has_finish_without_relief():
    r=request()
    r['theta']['trim']['plinth']=dict(design='smooth',relief_m=0,height_m=.7)
    result=reconstruct(from_json(json.dumps(r)))
    assert all(p.semantic!='trim_plinth' for p in result.resolved.trims)
    assert 'material_coating' in {p['name'] for p in result.mesh.parts}


def test_parapet_anchor_and_missing_parapet():
    r=request(); r['theta']['trim']['cornice']['anchor']='parapet_top'
    with pytest.raises(ValueError,match='parapet'):
        reconstruct(from_json(json.dumps(r)))
    r['theta']['roof']['parapet_m']=.4
    result=reconstruct(from_json(json.dumps(r)))
    assert all(p.base_z+max(z for d,z in p.section)==pytest.approx(6.4) for p in result.resolved.trims)


def test_blocks_stationing_crosses_corner():
    c=PlinthControls(design='blocks',block_width_m=.7)
    pieces=plinth_pieces([LineString([(0,0),(1,0),(1,1)])],c,('test',),'test')
    assert any(len(p.path)==3 for p in pieces)


def test_fence_plinth_does_not_fill_access():
    r=request()
    r['theta'].update(height_m=None,floors=None,massing=dict(pattern='explicit'))
    r['theta']['masses']=[dict(role='house',footprint=[[2,2],[8,2],[8,8],[2,8]],levels_m=[0,6])]
    r['theta']['site']['runs']=[dict(edge=0,start_m=0.,end_m=10.,kind='republicano',height_m=1.2,
        height_mode='low',base_height_m=.35,plinth=dict(height_m=.3,design='stepped'),gate_u=2.,gate_width=1.)]
    result=reconstruct(from_json(json.dumps(r)))
    pieces=[p for p in result.resolved.trims if p.sources==('site/fence',)]
    assert pieces
    assert all(LineString(p.path).intersection(LineString([(2,0),(3,0)])).length<1e-7 for p in pieces)
    r['theta']['site']['runs'][0]['plinth']['height_m']=.5
    with pytest.raises(ValueError,match='solid base'):reconstruct(from_json(json.dumps(r)))


def test_courtyard_clockwise_sweep():
    path=[(1,1),(1,4),(4,4),(4,1),(1,1)]
    mb=MeshBuilder(box(0,0,5,5))
    emit_sweep(mb,path,cornice_section(CorniceControls(),'barroco'),2.,'cornice','trim_cornice',box(0,0,5,5))
    mesh=mb.finish(); solid=trimesh.Trimesh(mesh.vertices,mesh.faces,process=False)
    assert solid.is_watertight and solid.is_winding_consistent and solid.volume>0


def test_oblique_party_termination_is_closed_and_inside():
    envelope=Polygon([(0,0),(4,0),(4.4,4),(.4,4)])
    path=[(.1,1.),(4.1,1.)]
    mb=MeshBuilder(envelope)
    section=cornice_section(CorniceControls(),'republicano')
    emit_sweep(mb,path,section,3.,'cornice','trim_cornice',envelope)
    mesh=mb.finish(); solid=trimesh.Trimesh(mesh.vertices,mesh.faces,process=False)
    assert solid.is_watertight and solid.is_winding_consistent
    assert envelope.buffer(1e-7).covers(sweep_domain(path,section,envelope))


def test_component_override_and_serialization():
    r=request(); r['theta'].update(height_m=None,floors=None)
    r['theta']['massing']=dict(pattern='composition',components=[
        dict(id='low',region=dict(front_edge=0,u=[.1,.9],depth=[.1,.9]),levels_m=[0,3],
             trim=dict(cornice=dict(enabled=False),plinth=dict(enabled=False))),
        dict(id='high',region=dict(front_edge=0,u=[.1,.9],depth=[.1,.9]),levels_m=[3,6])])
    parsed=from_json(json.dumps(r))
    result=reconstruct(parsed)
    assert len(result.resolved.trims)==1
    assert result.resolved.trims[0].sources==('high:0',)


def test_repeat_family_cornice_is_suppressed_when_off():
    r=request(); r['theta']['facade']=dict(mode='repeat')
    r['theta']['trim']['cornice']['enabled']=False
    result=reconstruct(from_json(json.dumps(r)))
    names={p['name'] for p in result.mesh.parts}
    assert not {'cornice','cornice_step','top_cornice','trim_cornice'} & names


def test_disabled_fence_finish_preserves_structural_base():
    r=request(); r['theta'].update(height_m=None,floors=None,massing=dict(pattern='explicit'))
    r['theta']['masses']=[dict(role='house',footprint=[[2,2],[8,2],[8,8],[2,8]],levels_m=[0,6])]
    r['theta']['site']['runs']=[dict(edge=0,start_m=0,end_m=10,kind='moderno',height_m=1.2,
        plinth=dict(enabled=False),base_height_m=.35)]
    result=reconstruct(from_json(json.dumps(r)))
    assert not any(p.sources==('site/fence',) for p in result.resolved.trims)
    assert 'boundary_base' in {p['name'] for p in result.mesh.parts}


@pytest.mark.parametrize('field,value', [('height_m',0.),('projection_m',float('nan')),('material','unknown')])
def test_invalid_cornice_controls_rejected(field,value):
    r=request(); r['theta']['trim']['cornice'][field]=value
    with pytest.raises(ValueError):reconstruct(from_json(json.dumps(r)))
