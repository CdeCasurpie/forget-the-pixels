import json
from dataclasses import replace
import numpy as np
import pytest
import trimesh
from shapely.geometry import box,Polygon
from shapely.ops import unary_union
from domain.roof_details import RoofDesign,EaveDesign
from domain.theta import from_json,canonical
from modeling.roof_planes import plan_faces,compound_faces,geometry,height
from modeling.roof_assembly import build_roof_assembly,roof_edges
from modeling.roof_detail_resolver import ResolvedRoofAssembly
from modeling.mesh_builder import MeshBuilder
from modeling.theta import resolve_theta,generate_resolved
from test_volumetric_crowns import request


@pytest.mark.parametrize('form',['flat','shed','gable','hip','pavilion','band'])
def test_planes_partition_support_and_meet(form):
    poly=box(2,2,6,5);d=RoofDesign(form=form,band_depth_m=1.)
    ff=plan_faces(poly,d,4)
    assert unary_union([geometry(f) for f in ff]).symmetric_difference(poly).area<1e-7
    assert sum(geometry(f).area for f in ff)==pytest.approx(poly.area)
    for line,kind,p,q in roof_edges(ff):
        if kind in ('ridge','valley'):
            assert all(height(p,*xy)==pytest.approx(height(q,*xy)) for xy in line.coords)


def test_compound_lobe_partition_has_valley():
    parts=[box(0,0,6,3),box(0,0,3,6)];d=RoofDesign(form='compound')
    ff=compound_faces(parts,d,4)
    assert sum(geometry(f).area for f in ff)==pytest.approx(unary_union(parts).area)
    assert any(kind=='valley' for _,kind,_,_ in roof_edges(ff))


@pytest.mark.parametrize('covering',['curved_tile','flat_tile','corrugated','panel','none','slats'])
def test_covering_parts_are_closed_positive_solids(covering):
    d=RoofDesign(form='gable',style='republicano',covering=covering,eave=EaveDesign(fascia=False))
    poly=box(2,2,3.2,3.1);ff=plan_faces(poly,d,4)
    r=ResolvedRoofAssembly('test','test',d,tuple(ff),tuple(poly.exterior.coords)[:-1],4)
    mb=MeshBuilder(box(0,0,10,10));build_roof_assembly(mb,r,box(0,0,10,10));mesh=mb.finish()
    for p in mesh.parts:
        faces=mesh.faces[p['face_start']:p['face_start']+p['face_count']]
        used,index=np.unique(faces,return_inverse=True)
        solid=trimesh.Trimesh(mesh.vertices[used],index.reshape(-1,3),process=False)
        assert solid.is_watertight and solid.is_winding_consistent and solid.volume>0,p['name']


def solve(design=None,**extra):
    r=request();r['theta']['crowns']=[]
    r['theta']['roof_assemblies']=[dict(id='roof',mass_ref='house:0',design=design or dict(form='hip',detail='light'))|extra]
    req=from_json(json.dumps(r));assert canonical(req)==canonical(from_json(canonical(req)))
    return resolve_theta(req.context,req.theta)


def test_explicit_roof_replaces_old_slab_and_is_serializable():
    r=solve();mesh=generate_resolved(r)
    assert 'roof_slab' not in {p['name'] for p in mesh.parts}
    assert 'roof_substrate' in {p['name'] for p in mesh.parts}
    assert canonical(r)


@pytest.mark.parametrize('design,match',[
    (dict(form='hip',parapet_m=.4),'Parapets'),
    (dict(tile_width_m=0.),'dimensions'),
    (dict(eave=dict(spacing_m=0.)),'dimensions'),
    (dict(style='bad'),'style'),
    (dict(slope_deg=float('nan')),'finite')])
def test_invalid_design_rejected(design,match):
    with pytest.raises(ValueError,match=match):solve(design)


def test_fronton_connection_cuts_back_roof_and_preserves_crown():
    r=request();r['theta']['crowns'][0]['design']=dict(family='triangular')
    r['theta']['roof_assemblies']=[dict(id='roof',mass_ref='house:0',crown_ref='crown',junction='behind',design=dict(form='flat',covering='none'))]
    req=from_json(json.dumps(r));resolved=resolve_theta(req.context,req.theta)
    assert len(resolved.crowns)==1
    cover=unary_union([geometry(f) for f in resolved.roof_assemblies[0].faces])
    assert cover.intersection(box(7,2.9,13,3.29)).area<1e-7


@pytest.mark.parametrize('kind',['clean','closed','exposed','profiled','braces','curved','cornice'])
def test_canopy_variants_closed_and_within_envelope(kind):
    d=RoofDesign(form='shed',covering='panel',style='madera',eave=EaveDesign(kind=kind,gutter=True))
    poly=box(2,2,4,3.2);d=replace(d,rotation_deg=90)
    r=ResolvedRoofAssembly('canopy','house',d,tuple(plan_faces(poly,d,3)),tuple(poly.exterior.coords)[:-1],3,True,1.2,(0.,-1.))
    mb=MeshBuilder(box(0,0,10,10));build_roof_assembly(mb,r,box(0,0,10,10));mesh=mb.finish()
    for p in mesh.parts:
        ff=mesh.faces[p['face_start']:p['face_start']+p['face_count']]
        used,index=np.unique(ff,return_inverse=True);solid=trimesh.Trimesh(mesh.vertices[used],index.reshape(-1,3),process=False)
        assert solid.is_watertight and solid.is_winding_consistent and solid.volume>0,p['name']


@pytest.mark.parametrize('cap',['none','flat','bevel','pitched','moulded','metal'])
def test_parapet_cap_independent_switch(cap):
    resolved=solve(dict(form='flat',covering='none',parapet_m=.6,cap=cap,cap_drip=cap=='metal',eave=dict(kind='clean',fascia=False)))
    mesh=generate_resolved(resolved);names={p['name'] for p in mesh.parts}
    assert ('roof_parapet_cap' in names)==(cap!='none')
    assert 'roof_fascia' not in names
    assert 'roof_parapet' in names


def test_two_masses_join_without_internal_fascia():
    r=request();t=r['theta'];t['crowns']=[]
    t['masses']=[dict(role='left',footprint=[[3,3],[10,3],[10,10],[3,10]],levels_m=[0,4]),
                 dict(role='right',footprint=[[10,3],[17,3],[17,10],[10,10]],levels_m=[0,4])]
    t['roof_assemblies']=[dict(id=name,mass_ref=name+':0',join_group='house',design=dict(form='flat',covering='none',eave=dict(kind='clean',overhang_m=0))) for name in ('left','right')]
    req=from_json(json.dumps(r));resolved=resolve_theta(req.context,req.theta)
    assert len(resolved.roof_assemblies)==1
    roof=resolved.roof_assemblies[0]
    assert set(roof.source_masses)=={'left:0','right:0'}
    assert sum(line.length for line,kind,_,_ in roof_edges(roof.faces) if kind=='edge')==pytest.approx(42.)
    assert 'roof_slab' not in {p['name'] for p in generate_resolved(resolved).parts}


def test_band_leaves_flat_remainder_without_tiles():
    d=RoofDesign(form='band',covering='flat_tile',band_depth_m=.8,style='republicano',eave=EaveDesign(kind='clean',fascia=False))
    poly=box(2,2,4,4);ff=plan_faces(poly,d,4)
    r=ResolvedRoofAssembly('band','house',d,tuple(ff),tuple(poly.exterior.coords)[:-1],4)
    mb=MeshBuilder(box(0,0,10,10));build_roof_assembly(mb,r,box(0,0,10,10));mesh=mb.finish()
    for p in mesh.parts:
        if p['name']=='roof_flat_tile':
            verts=mesh.vertices[np.unique(mesh.faces[p['face_start']:p['face_start']+p['face_count']])]
            assert verts[:,0].max()<=2.8+1e-6


def test_ridge_position_moves_without_breaking_join():
    d=RoofDesign(form='gable',ridge_fraction=.3)
    ff=plan_faces(box(0,0,10,6),d,4)
    ridge=next(line for line,kind,_,_ in roof_edges(ff) if kind=='ridge')
    assert ridge.bounds[0]==pytest.approx(3.)


def test_optional_style_props_are_deterministic_and_can_be_off():
    a=solve(dict(form='flat',covering='none'),props_mode='auto')
    b=solve(dict(form='flat',covering='none'),props_mode='auto')
    assert a.roof_assemblies[0].props==b.roof_assemblies[0].props
    assert a.roof_assemblies[0].props
    assert not solve(dict(form='flat',covering='none'),props_mode='off').roof_assemblies[0].props


def test_frame_has_no_opaque_substrate():
    r=solve(dict(form='shed',covering='panel',construction='frame',material='glass',detail='light'))
    names={p['name'] for p in generate_resolved(r).parts}
    assert 'roof_substrate' not in names
    assert 'roof_cover' in names


def test_gable_fronton_controls_pitch_and_height():
    r=request();t=r['theta'];t['crowns'][0].update(u_m=0,width_m=14,height_m=2.,design=dict(family='triangular'))
    t['roof_assemblies']=[dict(id='roof',mass_ref='house:0',crown_ref='crown',junction='gable',design=dict(form='gable',detail='light'))]
    req=from_json(json.dumps(r));resolved=resolve_theta(req.context,req.theta)
    roof=resolved.roof_assemblies[0]
    assert max(height(f.plane,*xy) for f in roof.faces for xy in f.polygon)==pytest.approx(6.)


def test_roof_cannot_back_an_oculus():
    r=request();t=r['theta'];t['crowns'][0].update(aperture='oculus',aperture_sill_m=.4,aperture_height_m=.5,design=dict(family='triangular'))
    t['roof_assemblies']=[dict(id='roof',mass_ref='house:0',crown_ref='crown',junction='behind',design=dict(form='gable',slope_deg=30))]
    req=from_json(json.dumps(r))
    with pytest.raises(ValueError,match='aperture'):resolve_theta(req.context,req.theta)


def test_gable_closure_inherits_upper_wall_material():
    r=request();t=r['theta'];t['crowns']=[]
    t['facade']['material_regions']=[dict(u_m=0,v_m=3,width_m=14,height_m=1,material_slot='brick')]
    t['roof_assemblies']=[dict(id='roof',mass_ref='house:0',design=dict(form='gable',detail='light'))]
    req=from_json(json.dumps(r));resolved=resolve_theta(req.context,req.theta)
    assert {f.material for f in resolved.roof_assemblies[0].wall_finishes}=={'brick'}
    mesh=generate_resolved(resolved);names=set()
    for p in mesh.parts:
        if p['name']!='roof_gable_closure':continue
        names.add(mesh.materials[mesh.face_materials[p['face_start']]]['name'])
    assert names=={'brick'}
