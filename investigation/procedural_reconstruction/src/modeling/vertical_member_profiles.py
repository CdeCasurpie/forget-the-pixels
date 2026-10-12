"""Metric section rings and sampled moulding profiles (no stacked boxes)."""
import numpy as np
from shapely.geometry import box, Point, Polygon
from shapely.geometry.polygon import orient


def section_ring(kind,width,depth,detail,flutes=0):
    if kind in ('circle','ellipse'):
        count=max(32*detail,flutes*12)
        angles=np.linspace(0,2*np.pi,count,endpoint=False)
        radius=1.-(.11*(.5+.5*np.cos(flutes*angles))**3 if flutes else 0.)
        return np.column_stack((width/2*radius*np.cos(angles),depth/2*radius*np.sin(angles)))
    if kind=='octagon':
        q=np.arange(8)*np.pi/4+np.pi/8
        return np.column_stack((width/2*np.cos(q)/np.cos(np.pi/8),depth/2*np.sin(q)/np.cos(np.pi/8)))
    shape=box(-width/2,-depth/2,width/2,depth/2)
    if kind in ('rounded','chamfered'):
        r=min(width,depth)*.13
        shape=shape.buffer(-r,join_style=2).buffer(r,quad_segs=detail*4,join_style=1 if kind=='rounded' else 3)
    if flutes:
        # Grooves are true concavities, not bars glued to a flat face.
        count=max(2,min(flutes,24)); r=min(width/(count*3),depth*.13)
        for x in np.linspace(-width*.40,width*.40,count):
            for sign in (-1,1):shape=shape.difference(Point(x,sign*depth/2).buffer(r,quad_segs=detail*3))
    if not isinstance(shape,Polygon) or not shape.is_valid:raise ValueError('Invalid member section')
    return np.asarray(orient(shape,sign=1.).exterior.coords)[:-1]


def moulding_profile(kind,detail=2):
    # (height fraction, section scale); interpolate smooth curved transitions.
    if kind=='minimal':
        keys=((0,1.08),(.15,1.08),(.85,1.),(1,1.))
    elif kind=='simple':
        keys=((0,1.14),(.25,1.14),(.65,1.07),(1,1.))
    elif kind in ('base','attic'):
        keys=((0,1.18),(.12,1.18),(.17,1.07),(.30,1.16),(.43,1.08),(.55,.98),(.72,.93),(.83,1.04),(1,1.))
    elif kind=='doric':
        keys=((0,1.),(.15,1.02),(.25,1.0),(.67,1.20),(.76,1.25),(1,1.25))
    else:
        keys=((0,1.),(.14,1.05),(.25,1.02),(.42,1.10),(.60,1.22),(.73,1.16),(.82,1.25),(1,1.25))
    result=[]
    for (z0,r0),(z1,r1) in zip(keys,keys[1:]):
        for f in np.linspace(0,1,detail*3,endpoint=False):
            s=f*f*(3-2*f)
            result.append((z0+(z1-z0)*f,r0+(r1-r0)*s))
    return (*result,keys[-1])
