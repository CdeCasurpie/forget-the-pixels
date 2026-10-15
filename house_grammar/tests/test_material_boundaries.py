"""Finishes partition a wall surface without adding solids or changing depth."""
from dataclasses import replace
import numpy as np
import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from domain.models import FacadeMaterialRegion, FacadeSpecification, Opening, ResolvedTopProfile
from modeling.grammar import facade
from modeling.mesh_builder import MeshBuilder
from modeling.validation import analyze_topology
from modeling.apertures import opening_shape


def build(*, front=True, regions=(), ops=(), material='plaster', parcel=None, profile=None):
    spec=FacadeSpecification('edge_0',(0.,0.),(20.,0.),20.,(0.,-1.),(0.,3.,6.,10.),
        openings=ops,is_front=front,wall_material=material,material_regions=regions,
        top_profile=profile,ornamented=False)
    mb=MeshBuilder(parcel if parcel is not None else box(-2,-2,22,12))
    facade(mb,spec,10.,managed_trim=True)
    return mb.finish()


def wall_triangles(mesh, material=None):
    for p in mesh.parts:
        if p['name'] != 'wall':continue
        for i in range(p['face_start'],p['face_start']+p['face_count']):
            if material is None or mesh.materials[int(mesh.face_materials[i])]['name']==material:
                yield mesh.vertices[mesh.faces[i]]


def front_area(mesh, material=None):
    return unary_union([Polygon(t[:,[0,2]]) for t in wall_triangles(mesh,material)
                        if np.allclose(t[:,1],0.,atol=1e-9,rtol=0)])


def signed_volume(mesh):
    return sum(np.dot(t[0],np.cross(t[1],t[2]))/6 for t in wall_triangles(mesh))


@pytest.mark.parametrize('material',['plaster','brick','concrete'])
def test_material_never_adds_structure_or_moves_wall(material):
    baseline=build(front=False)
    mesh=build(front=False,material=material)
    assert np.array_equal(mesh.vertices,baseline.vertices)
    assert np.array_equal(mesh.faces,baseline.faces)
    assert {p['name'] for p in mesh.parts} == {'wall'}
    assert front_area(mesh,material).area==pytest.approx(200.)
    assert not analyze_topology(mesh)['violations']


@pytest.mark.parametrize('shape',['rectangle','arch','circle'])
def test_paint_preserves_shell_holes_volume_and_exact_material_areas(shape):
    opening=Opening('window',3,4,2,2,shape=shape)
    ops=(opening,)
    regions=(FacadeMaterialRegion(2,3,4,4,'accent'), FacadeMaterialRegion(4,3,3,4,'stone'))
    baseline=build(ops=ops)
    mesh=build(ops=ops,regions=regions)
    assert not analyze_topology(mesh)['violations']
    assert not any(p['name']=='material_coating' for p in mesh.parts)
    assert np.allclose(mesh.vertices.min(axis=0),baseline.vertices.min(axis=0))
    assert np.allclose(mesh.vertices.max(axis=0),baseline.vertices.max(axis=0))
    assert signed_volume(mesh)==pytest.approx(signed_volume(baseline))
    hole=opening_shape(opening)
    expected=box(2,3,4,7).difference(hole)
    assert front_area(mesh,'accent').symmetric_difference(expected).area<1e-8
    assert front_area(mesh,'stone').symmetric_difference(box(4,3,7,7).difference(hole)).area<1e-8
    # No overlapping visible triangles, including the underlying plaster.
    triangles=[Polygon(t[:,[0,2]]) for t in wall_triangles(mesh) if np.allclose(t[:,1],0.)]
    assert sum(p.area for p in triangles)==pytest.approx(unary_union(triangles).area)
    assert front_area(mesh).intersection(hole).area<1e-8


def test_regions_also_apply_to_blind_side_walls():
    mesh=build(front=False,material='brick',regions=(FacadeMaterialRegion(0,0,20,3,'plaster'),))
    assert front_area(mesh,'plaster').area==pytest.approx(60.)
    assert front_area(mesh,'brick').area==pytest.approx(140.)


def test_oblique_parcel_clipping_and_top_profile_keep_closed_shell():
    parcel=Polygon([(0.,0.),(20.,0.),(19.,12.),(-1.,12.)])
    profile=ResolvedTopProfile(((0.,10.),(10.,12.),(20.,10.)),10.,.3,0.,.1,'frame')
    region=FacadeMaterialRegion(2.,4.,12.,3.,'stone')
    ops=(Opening('window',3,4,2,2,shape='arch'),)
    baseline=build(parcel=parcel,profile=profile,ops=ops)
    mesh=build(parcel=parcel,profile=profile,ops=ops,regions=(region,))
    assert not analyze_topology(mesh)['violations']
    assert signed_volume(mesh)==pytest.approx(signed_volume(baseline))
    assert parcel.buffer(1e-8).covers(Polygon(mesh.vertices[:,:2]).convex_hull)


def test_material_uvs_remain_metric_after_partition():
    mesh=build(regions=(FacadeMaterialRegion(2,4,2,1,'stone'),))
    for part in mesh.parts:
        if part['name']!='wall':continue
        for i in range(part['face_start'],part['face_start']+part['face_count']):
            tri=mesh.vertices[mesh.faces[i]]
            if not np.allclose(tri[:,1],0.):continue
            scale=mesh.materials[int(mesh.face_materials[i])]['real_scale_m']
            assert np.allclose(mesh.corner_uv[i]*scale,tri[:,[0,2]])
