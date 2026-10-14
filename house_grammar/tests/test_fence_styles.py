from types import SimpleNamespace
import pytest
import numpy as np
from modeling.fences import STYLES, build_fence


class Recorder:
    def __init__(self):self.parts=[]
    def box(self,*args,**kwargs):self.parts.append(args[-1])
    def beam(self,*args,**kwargs):self.parts.append(kwargs['semantic'])
    def panel(self,*args,**kwargs):self.parts.append(args[-1])


@pytest.mark.parametrize('style',STYLES)
@pytest.mark.parametrize('mode,height',[('low',1.1),('high',2.8)])
def test_access_leaves_use_style_and_open_mode(style,mode,height):
    b=SimpleNamespace(kind=style,height=height,height_mode=mode,wall_material='brick',
                      gate_u=1.,gate_width=1.1,garage_u=3.,garage_width=3.,
                      gate_mode='auto',garage_mode='auto',openness=.3,planters=False)
    r=Recorder()
    build_fence(r,np.array([0.,0.]),np.array([1.,0.]),np.array([0.,-1.]),8.,b)
    assert r.parts.count('gate_handle')==3
    if style in ('republicano','barroco'):
        assert 'gate_panel' not in r.parts
        assert ('fence_spear' in r.parts)==(mode=='high')
    b.gate_mode=b.garage_mode='open'
    r=Recorder()
    build_fence(r,np.array([0.,0.]),np.array([1.,0.]),np.array([0.,-1.]),8.,b)
    assert 'gate_handle' not in r.parts
