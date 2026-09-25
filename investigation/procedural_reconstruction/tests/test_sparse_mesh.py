"""Complexity follows architectural boundaries, never physical wall area."""
import numpy as np
import pytest
from shapely.geometry import box, Polygon
from shapely.ops import unary_union
from modeling.mesh_builder import MeshBuilder
from modeling.validation import analyze_topology


def panel(domain):
    mb=MeshBuilder(box(-100,-100,100,100))
    mb.panel(np.array([0.,0.]),np.array([1.,0.]),np.array([0.,-1.]),[domain],-.2,0.,lambda *args:'plaster','wall')
    return mb.finish()


@pytest.mark.parametrize('width,height',[(1,3),(10,3),(50,10)])
def test_plain_wall_has_twelve_triangles(width,height):
    mesh=panel(box(0,0,width,height))
    assert (len(mesh.vertices),len(mesh.faces))==(8,12)
    assert not analyze_topology(mesh)['violations']


@pytest.mark.parametrize('count',[1,4,10,16])
def test_holes_are_real_and_cost_is_linear(count):
    holes=[box(1+i*2,1,2+i*2,2) for i in range(count)]
    domain=box(0,0,count*2+2,3).difference(unary_union(holes))
    mesh=panel(domain)
    assert len(mesh.faces)<=12+32*count
    assert not analyze_topology(mesh)['violations']
    points=mesh.vertices[mesh.faces]
    front=[Polygon(t[:,[0,2]]) for t in points if np.allclose(t[:,1],0)]
    assert unary_union(front).symmetric_difference(domain).area<1e-8
    assert sum(t.area for t in front)==pytest.approx(domain.area)


@pytest.mark.parametrize('width',[1.2,3.])
def test_ground_opening_is_closed_notch(width):
    domain=box(0,0,10,3).difference(box(2,0,2+width,2.3)).difference(box(6,1,8,2))
    mesh=panel(domain)
    assert not analyze_topology(mesh)['violations']
    assert len(mesh.faces)<100


def test_panel_propagates_internal_exception(monkeypatch):
    mb=MeshBuilder(box(-10,-10,10,10))
    def broken(*args): raise RuntimeError('deliberate geometry failure')
    monkeypatch.setattr(mb,'_panel_poly',broken)
    with pytest.raises(RuntimeError,match='deliberate geometry failure'):
        mb.panel([0,0],[1,0],[0,-1],[box(0,0,2,3)],-.2,0,lambda *args:'plaster','wall')
    assert mb._open is None
    assert not mb.parts
