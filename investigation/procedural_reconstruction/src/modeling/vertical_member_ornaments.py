"""Swept volutes, curved leaf reliefs and shaped timber saddles."""
import numpy as np
from shapely.geometry import Polygon
from modeling.vertical_member_sweep import emit_loft


def emit_ornaments(mb,center,t,n,z,width,depth,height,kind,material,detail,attached):
    center,t,n=map(np.asarray,(center,t,n))
    directions=((t,n),) if attached else ((t,n),(-t,-n),(n,-t),(-n,t))
    for tangent,normal in directions:
        w=width if abs(np.dot(tangent,t))>.5 else depth
        d=depth if abs(np.dot(tangent,t))>.5 else width
        origin=center+normal*d*.47
        def point(x,y,out=0):return (* (origin+tangent*x+normal*out),z+y)
        if kind in ('volutes','composite'):
            for sign in (-1,1):
                angles=np.linspace(0,2.6*np.pi,24*detail)
                curve=[point(sign*(w*.32+w*.19*(1-i/(len(angles)*1.08))*np.cos(q)),
                             height*.62+height*.29*(1-i/(len(angles)*1.08))*np.sin(q),w*.04)
                       for i,q in enumerate(angles)]
                for a,b in zip(curve,curve[1:]):mb.beam(a,b,min(w*.023,height*.04),material,'member_volute',clip='envelope')
        if kind in ('leaves','composite'):
            count=max(3,min(7,int(w/.10)))
            for x in np.linspace(-w*.38,w*.38,count):
                # Thin solid leaf: pointed plan with a curved projecting spine.
                rings=[]
                for f in np.linspace(0,1,8*detail):
                    half=max(.002,w/count*.42*np.sin(np.pi*f)**.7)
                    protrude=w*.14*np.sin(np.pi*f*.85)
                    rings.append([point(x-half,height*(.10+.70*f),protrude),
                                  point(x+half,height*(.10+.70*f),protrude),
                                  point(x+half,height*(.10+.70*f),protrude+.015),
                                  point(x-half,height*(.10+.70*f),protrude+.015)])
                emit_loft(mb,rings,material,'member_leaf')
        if kind=='saddle':
            rings=[]
            for f,half in ((0,.33),(.59,.58),(.72,.92),(1,.95)):
                rings.append([(* (center+tangent*x+normal*y),z+height*f)
                              for x,y in ((-w*half,-d*.42),(w*half,-d*.42),(w*half,d*.42),(-w*half,d*.42))])
            emit_loft(mb,rings,material,'member_saddle')
            break
