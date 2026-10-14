import json
import numpy as np
import pytest
import trimesh
from shapely.geometry import box, Polygon
from domain.theta import from_json, canonical
from domain.balconies import RailingControls
from modeling.balcony_catalog import CATALOG
from modeling.mesh_builder import MeshBuilder
from modeling.railing_assembly import lathe, build_railing
from pipeline.theta import reconstruct


def request(style='republicano',variant='iron_vertical',width=3.2):
    p=CATALOG[style][variant]
    return dict(context=dict(parcel=[[0,0],[20,0],[20,20],[0,20]],fronts=[0,1]),
        theta=dict(schema_version='0.3',architectural_style=style,
                   massing=dict(pattern='explicit'),
                   masses=[dict(role='house',footprint=[[3,3],[15,3],[15,15],[3,15]],levels_m=[0,3,6])],
                   facade=dict(mode='explicit',openings=[],projections=[],material_regions=[]),
                   roof=dict(kind='flat',parapet_m=0,props=[]),site=dict(fence='none',runs=[],garden=False),
                   balconies=[dict(id='sample',mass_ref='house:0',edge=0,floor_m=3.,u_m=.5,width_m=width,
                                    variant=variant,kind=p.kind,cover=p.kind in ('gallery','box'),brackets=True)]))


@pytest.mark.parametrize('style,variant',[(s,v) for s,f in CATALOG.items() for v in f])
@pytest.mark.parametrize('width',[1.2,3.2,8.])
def test_all_presets_adapt_without_nonfinite_geometry(style,variant,width):
    result=reconstruct(from_json(json.dumps(request(style,variant,width))))
    assert np.isfinite(result.mesh.vertices).all()
    b=result.resolved.balconies[0]
    assert b.controls.style==style
    assert b.controls.width_m==width
    assert len(result.mesh.faces)>0
    assert 'balcony_platform' in {p['name'] for p in result.mesh.parts}


@pytest.mark.parametrize('double,turned',[(False,False),(True,False),(False,True)])
def test_baluster_is_positive_closed_solid(double,turned):
    mb=MeshBuilder(box(-2,-2,2,2))
    lathe(mb,(0,0),0,1,.08,'stone',double=double,turned=turned)
    mesh=mb.finish(); solid=trimesh.Trimesh(mesh.vertices,mesh.faces,process=False)
    assert solid.is_watertight and solid.is_winding_consistent and solid.volume>0


def test_existing_terrace_and_disabled_slab():
    r=request(); t=r['theta']; t['masses']=[
        dict(role='lower',footprint=[[3,2],[15,2],[15,15],[3,15]],levels_m=[0,3]),
        dict(role='upper',footprint=[[3,3],[15,3],[15,15],[3,15]],levels_m=[3,6])]
    t['balconies'][0].update(mass_ref='upper:0',floor_m=0,kind='terrace',slab=False,brackets=False,
                             support_mass='lower:0',sides=['front'])
    result=reconstruct(from_json(json.dumps(r)))
    names={p['name'] for p in result.mesh.parts}
    assert 'balcony_platform' not in names and 'balcony_bar' in names
    t['balconies'][0]['depth_m']=1.8
    with pytest.raises(ValueError,match='substrate'):reconstruct(from_json(json.dumps(r)))


def test_post_shared_at_corner_and_slope_uprights():
    mb=MeshBuilder(box(-3,-3,8,8))
    build_railing(mb,[(0,0,0),(3,0,1),(3,3,1)],RailingControls(post_spacing_m=1.6),
                  'vertical','metal',box(-3,-3,8,8))
    mesh=mb.finish()
    posts=[p for p in mesh.parts if p['name']=='balcony_post']
    assert len(posts)==5  # two segments, three posts each, one shared corner
    for part in posts:
        verts=mesh.vertices[np.unique(mesh.faces[part['face_start']:part['face_start']+part['face_count']])]
        assert np.ptp(verts[:,2])==pytest.approx(1.05)


def test_stair_uses_existing_geometry_and_replaces_legacy_railing():
    r=request(); r['theta']['facade']['stairs']=[dict(u_m=2.,base_z_m=0,target_z_m=3.,run_m=2.2)]
    r['theta']['balconies'][0].update(kind='stair',stair_index=0,floor_m=0,slab=False,brackets=False)
    result=reconstruct(from_json(json.dumps(r)))
    names={p['name'] for p in result.mesh.parts if p['assembly_id'].startswith('house:0/edge0')}
    assert 'exterior_stair_step' in names and 'stair_handrail' not in names
    assert len(result.resolved.balconies[0].routes)==3
    # The inner rail ends before the landing, still on the slope, not floating
    # at landing height over the lower treads.
    inner=result.resolved.balconies[0].routes[1]
    assert inner[-1][2]==pytest.approx(1.5*(2.2-1.15)/2.2)


def test_off_preserves_legacy_and_canonical_empty():
    r=request(); r['theta']['balconies'][0]['enabled']=False
    result=reconstruct(from_json(json.dumps(r)))
    assert not result.resolved.balconies
    del r['theta']['balconies']
    parsed=from_json(json.dumps(r))
    assert '"balconies":[]' not in canonical(parsed)


@pytest.mark.parametrize('change,match',[
    (dict(style='moderno'),'conflicts'),
    (dict(variant='missing'),'Variant'),
    (dict(width_m=.2),'dimensions'),
    (dict(depth_m=4.,curved_front_m=.6),'envelope'),
    (dict(floor_m=2.4),'floor level'),
    (dict(kind='terrace'),'slab=false'),
    (dict(railing=dict(spacing_m=0)),'dimensions')])
def test_bad_controls_rejected(change,match):
    r=request();r['theta']['balconies'][0].update(change)
    with pytest.raises(ValueError,match=match):reconstruct(from_json(json.dumps(r)))


def test_box_wraps_real_corner_without_intersecting_mass():
    r=request('madera','continuous_box')
    r['theta']['balconies'][0].update(u_m=8.8,corner_return_m=2.5)
    result=reconstruct(from_json(json.dumps(r)))
    b=result.resolved.balconies[0]
    assert Polygon(b.platform).intersection(box(3,3,15,15)).area<1e-7
    assert len(b.routes[0])==5
    assert 'balcony_fretwork' in {p['name'] for p in result.mesh.parts}


def test_curved_front_has_modular_post_count():
    r=request('moderno','glass_posts',3.2)
    r['theta']['balconies'][0]['curved_front_m']=.3
    result=reconstruct(from_json(json.dumps(r)))
    posts=[p for p in result.mesh.parts if p['name']=='balcony_post']
    assert 5<=len(posts)<=9
    assert len(result.resolved.balconies[0].platform)>10


def test_width_adds_bars_without_increasing_thickness():
    counts=[]
    for width in (1.2,3.2):
        result=reconstruct(from_json(json.dumps(request(width=width))))
        parts=[p for p in result.mesh.parts if p['name']=='balcony_bar']
        counts.append(len(parts))
        for p in parts:
            vv=result.mesh.vertices[np.unique(result.mesh.faces[p['face_start']:p['face_start']+p['face_count']])]
            assert np.ptp(vv[:,0])<=.018001 and np.ptp(vv[:,1])<=.018001
    assert counts[1]>counts[0]


def test_missing_stair_is_rejected():
    r=request();r['theta']['balconies'][0].update(kind='stair',stair_index=0,slab=False,brackets=False)
    with pytest.raises(ValueError,match='Stair anchor'):reconstruct(from_json(json.dumps(r)))
