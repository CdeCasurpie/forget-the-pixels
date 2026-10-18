from dataclasses import replace
import pytest
import numpy as np
from shapely.geometry import Polygon
from domain.models import Opening
from domain.theta import from_json
from modeling.window_assembly import PROFILES, build_window, grid_geometry, interior
from modeling.apertures import opening_shape
from modeling.mesh_builder import MeshBuilder
from pipeline.theta import reconstruct
import json


@pytest.mark.parametrize('style',PROFILES)
@pytest.mark.parametrize('shape',['rectangle','arch','circle','ellipse'])
def test_contour_clipping_and_real_mesh(style,shape):
    op=Opening('window',.5,.5,1.6,1.6 if shape=='circle' else 2.2,
               frame_profile=style,shape=shape,grille=True,grille_pattern='diamond',
               frame_width_m=.12,grid_spacing_m=.4,sill=True)
    assert grid_geometry(op).difference(interior(op)).area<1e-9
    assert grid_geometry(op,True).difference(interior(op)).area<1e-9
    builder=MeshBuilder(Polygon([(-1,-2),(4,-2),(4,2),(-1,2)]))
    build_window(builder,np.array([0.,0.]),np.array([1.,0.]),np.array([0.,-1.]),op)
    mesh=builder.finish()
    assert len(mesh.faces)>0
    assert np.isfinite(mesh.vertices).all()


def request(style='clasico',shape='arch'):
    return from_json(json.dumps(dict(context=dict(parcel=[[0,0],[8,0],[8,8],[0,8]],fronts=[0]),
        theta=dict(schema_version='0.3',architectural_style=style,height_m=3.,floors=1,
          facade=dict(mode='explicit',openings=[dict(kind='window',u_m=1.,v_m=.4,
            width_m=1.5,height_m=1.5,shape=shape,frame_profile='auto',grille=True)]),
          roof=dict(kind='flat',parapet_m=0),site=dict(fence='none',runs=[])))))


def test_full_pipeline_resolves_building_style():
    result=reconstruct(request())
    assert len(result.mesh.faces)>0


def test_circle_window_needs_equal_axes():
    with pytest.raises(ValueError,match='equal'):
        opening_shape(Opening('window',0,0,1,2,shape='circle'))


def test_local_frame_profile_is_honored_not_rejected():
    from modeling.opening_catalog import resolve_opening
    op=Opening('window',.5,.5,1.5,1.5,frame_profile='barroco')
    assert resolve_opening(op,'clasico').frame_profile=='barroco'
    r=request()
    op=replace(r.theta.facade.openings[0],frame_profile='barroco')
    r=replace(r,theta=replace(r.theta,facade=replace(r.theta.facade,openings=(op,))))
    assert len(reconstruct(r).mesh.faces)>0


def test_grid_remains_bounded_for_small_aperture():
    op=Opening('window',0,0,.4,.6,shape='ellipse',frame_profile='moderno',
               grille=True,grid_spacing_m=.2)
    assert interior(op).buffer(1e-9).covers(grid_geometry(op))
