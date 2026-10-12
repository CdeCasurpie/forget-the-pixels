"""Closed profiled sweeps with shared corner vertices and bounded mitres.

No cadastral clipping: the complete section must fit its authorised envelope.
Reject self-intersecting offsets rather than silently repairing the profile.
"""
import numpy as np
from shapely.geometry import Polygon, LineString, Point
from modeling.mesh_builder import triangulate_rings, _oriented


def stations(path,envelope=None):
    pts=np.asarray(path,float)
    closed=np.linalg.norm(pts[0]-pts[-1])<1e-8
    if closed:pts=pts[:-1]
    out=[]
    for i,p in enumerate(pts):
        before=p-pts[i-1] if i or closed else pts[1]-p
        after=pts[(i+1)%len(pts)]-p if i<len(pts)-1 or closed else before
        before=before/np.linalg.norm(before); after=after/np.linalg.norm(after)
        n0=np.array([before[1],-before[0]]); n1=np.array([after[1],-after[0]])
        denom=1+np.dot(n0,n1)
        if denom<1e-6:raise ValueError('Trim path doubles back')
        m=(n0+n1)/denom
        if np.linalg.norm(m)>4:
            # Bevel instead of an arbitrarily long mitre.
            out.extend(((p,n0),(p,n1)))
        else:out.append((p,m))
    if closed:out.append(out[0])
    elif envelope is not None:
        # A termination on a party boundary is capped in that boundary's plane,
        # not perpendicular to a slightly oblique facade (which crosses the lot).
        rings=[ring for poly in getattr(envelope,'geoms',(envelope,))
               if poly.geom_type=='Polygon' for ring in [poly.exterior,*poly.interiors]]
        for k in (0,-1):
            p,n=out[k]
            for ring in rings:
                xy=list(ring.coords)
                for a,b in zip(xy,xy[1:]):
                    if LineString([a,b]).distance(Point(p))>.003:continue
                    tangent=np.asarray(b)-a; tangent=tangent/np.linalg.norm(tangent)
                    dot=np.dot(tangent,n)
                    if abs(dot)>.25:
                        out[k]=(p,tangent/dot)
                        break
    return out,closed


def sweep_domain(path,section,envelope=None):
    ss,closed=stations(path,envelope)
    lo=min(d for d,z in section); hi=max(d for d,z in section)
    inner=[tuple(p+n*lo) for p,n in ss]; outer=[tuple(p+n*hi) for p,n in ss]
    if closed:
        a,b=Polygon(outer),Polygon(inner)
        if not a.is_valid or not b.is_valid:raise ValueError('Trim offset self-intersects; reduce projection')
        domain=a.symmetric_difference(b)
    else:domain=Polygon(outer+inner[::-1])
    if not domain.is_valid or domain.is_empty:raise ValueError('Invalid trim sweep footprint')
    return domain


def emit_sweep(mb,path,section,z,material,semantic,envelope):
    domain=sweep_domain(path,section,envelope)
    if not envelope.buffer(1e-7).covers(domain):
        raise ValueError(f'{semantic} projection outside permitted envelope')
    ss,closed=stations(path,envelope)
    vertices,triangles=triangulate_rings(section)
    triangles=_oriented(triangles,vertices,ccw=True)
    # Triangulation can reorder/clean section points, use its ring for all faces.
    section=[tuple(p) for p in vertices]
    with mb.component(semantic):
        idx=[[mb.vert((* (p+n*d),z+h)) for d,h in section] for p,n in ss]
        mat=mb.mat_index(material)
        distance=0.
        for k in range(len(ss)-1):
            step=float(np.linalg.norm(ss[k+1][0]-ss[k][0]))
            for j in range(len(section)):
                q=(j+1)%len(section)
                mb.quad(idx[k][j],idx[k+1][j],idx[k+1][q],idx[k][q],
                        ((distance,section[j][1]),(distance+step,section[j][1]),
                         (distance+step,section[q][1]),(distance,section[q][1])),mat)
            distance+=step
        if not closed:
            for a,b,c in triangles:
                # Section is CCW in outward-depth/up; start cap faces backwards.
                mb.tri(idx[0][a],idx[0][b],idx[0][c],(section[a],section[b],section[c]),mat)
                mb.tri(idx[-1][c],idx[-1][b],idx[-1][a],(section[c],section[b],section[a]),mat)
