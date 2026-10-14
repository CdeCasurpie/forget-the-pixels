"""Local material/relief boundaries without structural wall cuts."""
import numpy as np
import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from domain.models import FacadeMaterialRegion, FacadeSpecification, Opening
from modeling.grammar import facade, _brick_frame_polys
from modeling.mesh_builder import MeshBuilder
from modeling.validation import analyze_topology
from modeling.geometry_constraints import SURFACE_EPSILON_M


def build(*,front=False,regions=(),ops=()):
    spec=FacadeSpecification('edge_0',(0.,0.),(20.,0.),20.,(0.,-1.),(0.,3.,6.,10.),
        openings=ops,is_front=front,wall_material='plaster' if front else 'brick',material_regions=regions)
    mb=MeshBuilder(box(-2,-2,22,12))
    facade(mb,spec,10.)
    return mb.finish()


def caps(mesh,semantics,y):
    result=[]
    for p in mesh.parts:
        if p['name'] not in semantics: continue
        for tri in mesh.vertices[mesh.faces[p['face_start']:p['face_start']+p['face_count']]]:
            if np.allclose(tri[:,1],y,atol=1e-9,rtol=0): result.append(Polygon(tri[:,[0,2]]))
    return unary_union(result)


def test_side_frame_coverage_material_and_depth():
    mesh=build()
    assert not analyze_topology(mesh)['violations']
    base=caps(mesh,{'wall'},.015)
    frame=caps(mesh,{'structural_column','structural_beam'},0.)
    expected=_brick_frame_polys(20,10,(0,3,6,10))
    assert base.symmetric_difference(box(0,0,20,10)).area<1e-8
    assert frame.symmetric_difference(expected).area<1e-8
    assert base.difference(frame).area==pytest.approx(box(0,0,20,10).difference(expected).area)
    assert sum(p['face_count'] for p in mesh.parts if p['name']=='wall')==12
    for p in mesh.parts:
        if p['name'] in {'wall','structural_column','structural_beam'}:
            names={mesh.materials[int(i)]['name'] for i in mesh.face_materials[p['face_start']:p['face_start']+p['face_count']]}
            assert names==({'brick'} if p['name']=='wall' else {'concrete'})


def test_small_material_patch_costs_only_local_faces():
    baseline=build(front=True)
    mesh=build(front=True,regions=(FacadeMaterialRegion(2,4,2,1,'accent'),))
    assert len(mesh.faces)-len(baseline.faces)==12
    for m in (baseline,mesh): assert not analyze_topology(m)['violations']
    def walls(m):
        return [(p['face_count'],m.vertices[m.faces[p['face_start']:p['face_start']+p['face_count']]].tolist()) for p in m.parts if p['name']=='wall']
    assert walls(mesh)==walls(baseline)
    patch=caps(mesh,{'material_coating'},-SURFACE_EPSILON_M)
    assert patch.symmetric_difference(box(2,4,4,5)).area<1e-8


def test_coatings_preserve_holes_and_last_region_wins():
    ops=(Opening('window',3,4,1,1),)
    regions=(FacadeMaterialRegion(2,3,4,3,'accent'),FacadeMaterialRegion(4,3,3,3,'stone'))
    mesh=build(front=True,regions=regions,ops=ops)
    assert not analyze_topology(mesh)['violations']
    patches=caps(mesh,{'material_coating'},-SURFACE_EPSILON_M)
    assert patches.intersection(box(3,4,4,5)).area<1e-9
    expected=box(2,3,7,6).difference(box(3,4,4,5))
    assert patches.symmetric_difference(expected).area<1e-8


@pytest.mark.parametrize('axis,cut',[(0,2.),(2,1.8)])
def test_explicit_legacy_material_cut_remains_supported(axis,cut):
    mb=MeshBuilder(box(-2,-2,14,8))
    mb.panel([0,0],[1,0],[0,-1],[box(0,0,10,5)],-.2,0.,
        lambda kind,u,v,w:'concrete' if (u if axis==0 else v)<cut else 'brick',
        'wall',cuts_u=(cut,) if axis==0 else (),cuts_z=(cut,) if axis==2 else ())
    mesh=mb.finish()
    assert not analyze_topology(mesh)['violations']
    assert len(mesh.faces)<40
    for tri in mesh.vertices[mesh.faces]:
        if np.ptp(tri[:,1])<1e-9: assert not tri[:,axis].min()<cut<tri[:,axis].max()
