import json
from pathlib import Path
import numpy as np
import pytest
from shapely.geometry import box

from domain.models import Opening
from domain.theta import decode
from modeling.mesh_builder import MeshBuilder
from modeling.opening_catalog import resolve_opening
from modeling.grammar import opening
from modeling.window_assembly import build_window
from modeling.door_assembly import build_door

ROOT=Path(__file__).resolve().parents[1]/'steps/step23_fresh_theta'
SAMPLES=sorted(p for name in ('catalogo_ventanas','catalogo_puertas')
               for p in (ROOT/name).glob('*.json') if p.name!='index.json')


@pytest.mark.parametrize('path',SAMPLES,ids=lambda p:p.stem)
def test_original_catalog_geometry_is_preserved(path):
    op=decode(Opening,json.loads(path.read_text()))
    a,t,n=np.array([0.,0.]),np.array([1.,0.]),np.array([0.,-1.])
    expected=MeshBuilder(box(-5,-5,10,10))
    actual=MeshBuilder(box(-5,-5,10,10))
    (build_window if op.kind=='window' else build_door)(expected,a,t,n,op)
    opening(actual,a,t,n,op,'vertical')
    old,new=expected.finish(),actual.finish()
    np.testing.assert_array_equal(old.vertices,new.vertices)
    np.testing.assert_array_equal(old.faces,new.faces)


@pytest.mark.parametrize('prefab',['louver','screen','roller','wood_panel','metal_gate'])
def test_obsolete_window_prefabs_rejected(prefab):
    with pytest.raises(ValueError,match='catalogo_ventanas'):
        resolve_opening(Opening('window',0,0,1,2,prefab=prefab))


@pytest.mark.parametrize('prefab,construction,leaf',[
    ('roller','louvers','metal'),('wood_panel','boards','wood'),
    ('metal_gate','panelled','metal'),('storefront','glazed','auto'),
    ('open','grille','auto')])
def test_legacy_door_prefabs_normalize_to_catalog(prefab,construction,leaf):
    op=resolve_opening(Opening('door',0,0,1,2.2,prefab=prefab))
    assert op.prefab=='catalog' and op.door is not None and op.door.model=='moderno'
    assert op.door.construction==construction and op.door.leaf_material==leaf


def test_unknown_door_prefab_rejected():
    with pytest.raises(ValueError,match='catalogo_puertas'):
        resolve_opening(Opening('door',0,0,1,2.2,prefab='futuristic'))


def test_defaults_complete_to_catalog():
    assert resolve_opening(Opening('window',0,0,1,2)).frame_profile=='moderno'
    assert resolve_opening(Opening('door',0,0,1,2.2)).door.model=='moderno'


def test_removed_emitters_cannot_be_called_directly():
    from modeling.prefabs import build_opening
    from modeling.apertures import shaped_opening
    for emitter in (build_opening,shaped_opening):
        with pytest.raises(ValueError,match='removed'):
            emitter(None,None,None,None,Opening('window',0,0,1,2))
