import json
from dataclasses import replace
import numpy as np
import pytest
from shapely.geometry import Polygon
from domain.models import Opening, DoorControls
from domain.theta import from_json
from modeling.door_assembly import layout, validate_door, grille_geometry, build_door, DEFAULTS
from modeling.mesh_builder import MeshBuilder
from pipeline.theta import reconstruct


@pytest.mark.parametrize('style',DEFAULTS)
@pytest.mark.parametrize('shape',['rectangle','arch'])
@pytest.mark.parametrize('width,leaves',[(1.,1),(3.2,2)])
def test_doors_and_large_gateways(style,shape,width,leaves):
    op=Opening('door',1.,.1,width,3.2,shape=shape,frame_width_m=.10,
               door=DoorControls(model=style,leaves=leaves,transom_height_m=.5,
                                 transom_grille=True,portal='columns',cornice=True))
    validate_door(op)
    clear,body,transom,parts,_=layout(op)
    assert len(parts)==leaves
    assert body.intersection(transom).area<1e-9
    for p in parts:
        assert p.difference(clear).area<1e-9
    assert grille_geometry(transom,'scrolls',.16).difference(transom).area<1e-9
    mb=MeshBuilder(Polygon([(-2,-4),(8,-4),(8,4),(-2,4)]))
    build_door(mb,np.zeros(2),np.array([1.,0.]),np.array([0.,-1.]),op)
    mesh=mb.finish()
    assert np.isfinite(mesh.vertices).all()
    assert len(mesh.faces)>0


def test_adaptive_leaves_and_invalid_transom():
    op=Opening('gate',0,0,3.,3.,door=DoorControls(model='moderno'))
    assert len(layout(op)[3])==2
    with pytest.raises(ValueError,match='short'):
        validate_door(replace(op,door=replace(op.door,transom_height_m=2.)))


def test_pipeline_and_portal_validation():
    data=dict(context=dict(parcel=[[0,0],[8,0],[8,8],[0,8]],fronts=[0]),
              theta=dict(schema_version='0.3',architectural_style='republicano',height_m=4.,floors=1,
                facade=dict(mode='explicit',openings=[dict(kind='door',u_m=2.,v_m=.1,width_m=1.5,
                    height_m=2.7,shape='arch',door=dict(portal='pilasters',cornice=True))]),
                roof=dict(kind='flat',parapet_m=0),site=dict(fence='none',runs=[])))
    result=reconstruct(from_json(json.dumps(data)))
    assert len(result.mesh.faces)>0
    data['theta']['facade']['openings'][0]['u_m']=.13
    with pytest.raises(ValueError,match='portal outside'):
        reconstruct(from_json(json.dumps(data)))


def test_open_leaf_changes_geometry_and_preserves_hinge():
    op=Opening('door',1.,.1,1.,2.5,door=DoorControls(model='moderno',construction='glazed',leaves=1))
    meshes=[]
    for angle in (0.,60.):
        mb=MeshBuilder(Polygon([(-3,-5),(5,-5),(5,5),(-3,5)]))
        build_door(mb,np.zeros(2),np.array([1.,0.]),np.array([0.,-1.]),
                   replace(op,door=replace(op.door,opening_angles_deg=(angle,))))
        meshes.append(mb.finish())
    assert meshes[1].vertices[:,1].min()<meshes[0].vertices[:,1].min()-.3
