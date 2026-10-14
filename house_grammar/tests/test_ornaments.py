"""A surround must preserve the opening, including the curved arch head."""
import numpy as np
import pytest
from shapely.ops import unary_union
from domain.models import FacadeProjection, Opening
from modeling.apertures import opening_shape
from modeling.ornaments import moulded_surround


@pytest.mark.parametrize('shape,kind,rise',[('rectangle','moulded_surround',None),
    ('arch','segmental_surround',.35),('arch','segmental_surround',.56),('arch','segmental_surround',.95)])
def test_surround_keeps_aperture_clear(shape,kind,rise):
    class Capture:
        def __init__(self):self.panels=[]
        def panel(self,a,t,n,polys,back,front,material,semantic,**kwargs):
            assert front>back
            assert kwargs['clip']=='envelope'
            self.panels.extend(polys)
    op=Opening('window',1.,1.,2.,3.,shape=shape,
               arch_rise_m=rise)
    border=.20
    feature=FacadeProjection(kind,.8,.8,2.4,3.4,.25,border_width_m=border,arch_rise_m=rise)
    capture=Capture()
    moulded_surround(capture,np.array([0.,0.]),np.array([1.,0.]),np.array([0.,1.]),feature)
    aperture=opening_shape(op)
    relief=unary_union(capture.panels)
    # Keystone may overlap the thin original frame, not the clear opening.
    assert relief.intersection(aperture.buffer(-op.frame_width_m)).area<1e-8
    assert relief.area>.5
    assert all(p.is_valid for p in capture.panels)
