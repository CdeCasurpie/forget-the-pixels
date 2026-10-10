"""Clip facade primitives in their original (u,z) chart, never reflow bays."""
import numpy as np
from shapely.geometry import Polygon, LineString, Point, box
from shapely.ops import unary_union
from modeling.mesh_builder import polygons


def patch_domains(domains, extent, excluded=()):
    """Intersect/subtract rectangles without changing their parent wall chart.

    Horizontal slab decomposition returns disjoint rectangles even when an
    exclusion makes a hole. Composition must happen before using this mask.
    """
    mask=unary_union([box(*d) for d in domains]).intersection(box(*extent))
    if excluded:
        mask=mask.difference(unary_union([box(*d) for d in excluded]))
    if mask.is_empty:
        return ()
    zs=sorted({z for p in polygons(mask) for ring in (p.exterior,*p.interiors) for _,z in ring.coords})
    result=[]
    for lo,hi in zip(zs,zs[1:]):
        for part in polygons(mask.intersection(box(extent[0],lo,extent[2],hi))):
            if part.area>1e-10:
                result.append(part.bounds)
    return tuple(result)


class VisibleFacadeBuilder:
    def __init__(self, builder, a, tangent, domains):
        self._builder=builder
        self.a=np.asarray(a,float)
        self.t=np.asarray(tangent,float)
        self.n=np.array([self.t[1],-self.t[0]])
        self.domains=domains
        self.mask=unary_union([box(*d) for d in domains])

    def __getattr__(self,name):
        return getattr(self._builder,name)

    def panel(self,a,t,n,polys,w1,w2,mat_fn,semantic,**kwargs):
        clipped=[part for p in polys for part in polygons(p.intersection(self.mask))]
        return self._builder.panel(a,t,n,clipped,w1,w2,mat_fn,semantic,**kwargs)

    def crown_panel(self,a,t,n,polys,w1,w2,mat_fn,semantic,*,z_offset=0.,**kwargs):
        """Extend only exposed top domains, and only for crown polygons.

        Ordinary openings, wall shells and other projections continue using
        the original mask. A crown cannot grow above a hidden top segment.
        """
        top=min(p.bounds[1] for p in polys)-z_offset
        upper=max(p.bounds[3] for p in polys)
        cap=unary_union([box(u0,z1+z_offset,u1,upper) for u0,z0,u1,z1 in self.domains
                         if abs(z1-top)<1e-7 and upper>z1+z_offset])
        original=unary_union([box(u0,z0+z_offset,u1,z1+z_offset) for u0,z0,u1,z1 in self.domains])
        mask=original.union(cap)
        clipped=[part for p in polys for part in polygons(p.intersection(mask))]
        return self._builder.panel(a,t,n,clipped,w1,w2,mat_fn,semantic,**kwargs)

    def box(self,a,t,n,u1,u2,z1,z2,w1,w2,material='plaster',semantic='wall',**kwargs):
        if u2<=u1 or z2<=z1 or w2<=w1:
            return
        if not np.allclose(a,self.a) or not np.allclose(t,self.t) or not np.allclose(n,self.n):
            a,t,n=np.asarray(a),np.asarray(t),np.asarray(n)
            shape=Polygon([a+t*u+n*w for u,w in ((u1,w1),(u2,w1),(u2,w2),(u1,w2))])
            return self.solid(shape,z1,z2,material,semantic,clip=kwargs.get('clip','auto'))
        # All facade boxes use the same origin/tangent. Panel extrusion keeps
        # true holes and closed topology even where the mask cuts an opening.
        return self.panel(a,t,n,[box(u1,z1,u2,z2)],w1,w2,lambda *args:material,semantic,
                          clip=kwargs.get('clip','auto'))

    def solid(self,shape,bottom,top,*args,**kwargs):
        if shape.is_empty:return
        coords=np.asarray(shape.envelope.exterior.coords)
        ds=(coords-self.a)@self.n
        for i,(u0,z0,u1,z1) in enumerate(self.domains):
            strip=Polygon([self.a+self.t*u+self.n*d for u,d in ((u0,ds.min()-1),(u1,ds.min()-1),(u1,ds.max()+1),(u0,ds.max()+1))])
            part=shape.intersection(strip)
            if part.is_empty:continue
            if not callable(bottom) and not callable(top):
                lo,hi=max(bottom,z0),min(top,z1)
                if hi<=lo:continue
            else:
                # Clip sloping attachments by their linear height fields first.
                # Such attachments are normally inside a single storey band.
                lo=lambda x,y,b=bottom,z=z0:max(b(x,y) if callable(b) else b,z)
                hi=lambda x,y,t=top,z=z1:min(t(x,y) if callable(t) else t,z)
            kw=dict(kwargs)
            if kw.get('component_id'):kw['component_id']+=f'/visible{i}'
            self._builder.solid(part,lo,hi,*args,**kw)

    def beam(self,a,b,*args,**kwargs):
        a,b=np.asarray(a,float),np.asarray(b,float)
        pa=np.array([np.dot(a[:2]-self.a,self.t),a[2]])
        pb=np.array([np.dot(b[:2]-self.a,self.t),b[2]])
        delta=pb-pa
        if np.dot(delta,delta)<1e-12:
            if self.mask.covers(Point(pa)):return self._builder.beam(a,b,*args,**kwargs)
            return
        line=LineString([pa,pb]); kept=line.intersection(self.mask)
        for seg in ([kept] if kept.geom_type=='LineString' else getattr(kept,'geoms',())):
            if seg.geom_type!='LineString' or seg.is_empty:continue
            q0,q1=np.asarray(seg.coords[0]),np.asarray(seg.coords[-1])
            s0,s1=np.dot(q0-pa,delta)/np.dot(delta,delta),np.dot(q1-pa,delta)/np.dot(delta,delta)
            self._builder.beam(a+(b-a)*s0,a+(b-a)*s1,*args,**kwargs)
