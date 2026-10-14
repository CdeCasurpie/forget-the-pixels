"""Planar roof arrangements. Convex envelopes and rectangular L/T unions."""
from dataclasses import dataclass
import math
import numpy as np
from shapely.geometry import Polygon, LineString
from shapely.ops import split, unary_union
from modeling.mesh_builder import polygons


@dataclass(frozen=True)
class RoofFace:
    polygon: tuple[tuple[float,float],...]
    holes: tuple[tuple[tuple[float,float],...],...]
    plane: tuple[float,float,float]  # z = ax + by + c


def geometry(face):return Polygon(face.polygon,face.holes)
def height(plane,x,y):return plane[0]*x+plane[1]*y+plane[2]


def keep(poly,plane,positive=True):
    """Clip by an affine half-plane, preserving concave parts and holes."""
    if poly.is_empty:return Polygon()
    a,b,c=plane;norm=math.hypot(a,b)
    if norm<1e-10:return poly if (c>=-1e-8)==positive else Polygon()
    x0,y0,x1,y1=poly.bounds if not poly.is_empty else (0,0,0,0)
    centre=np.array([(x0+x1)/2,(y0+y1)/2]);normal=np.array([a,b])/norm
    centre-=normal*(np.dot(normal,centre)+c/norm)
    tangent=np.array([-normal[1],normal[0]])
    radius=max(math.hypot(x1-x0,y1-y0)*4,100.)
    cutter=LineString([centre-tangent*radius,centre+tangent*radius])
    pieces=split(poly,cutter)
    return unary_union([p for p in pieces.geoms if p.area>1e-9 and
        ((height(plane,*p.representative_point().coords[0])>=-1e-8)==positive)])


def faces(poly,planes,minimum=True):
    result=[]
    for i,plane in enumerate(planes):
        part=poly
        for j,other in enumerate(planes):
            if i==j:continue
            diff=np.asarray(other)-plane if minimum else np.asarray(plane)-other
            part=keep(part,diff)
            if part.is_empty:break
        for p in polygons(part):
            result.append(RoofFace(tuple(p.exterior.coords)[:-1],tuple(tuple(r.coords)[:-1] for r in p.interiors),tuple(map(float,plane))))
    return result


def plan_faces(poly,d,z):
    angle=math.radians(d.rotation_deg);n=np.array([math.cos(angle),math.sin(angle)])
    coords=np.asarray(poly.exterior.coords);values=coords@n;lo,hi=values.min(),values.max()
    k=math.tan(math.radians(d.slope_deg))
    if d.form=='flat':return faces(poly,[(0,0,z)])
    if d.form in ('hip','pavilion'):
        if poly.interiors or poly.symmetric_difference(poly.convex_hull).area>1e-6:
            raise ValueError('Hip/pavilion needs a convex footprint; use compound regions')
        from shapely.geometry.polygon import orient
        points=list(orient(poly,1).exterior.coords);planes=[]
        for a,b in zip(points,points[1:]):
            t=np.asarray(b)-a;t/=np.linalg.norm(t);inside=np.array([-t[1],t[0]])
            planes.append((* (inside*k),z-k*np.dot(inside,a)))
        return faces(poly,planes)
    if d.form=='shed':return faces(poly,[(*(n*k),z-k*lo)])
    if d.form=='band':
        if d.band_depth_m>=hi-lo:raise ValueError('Tile band must leave a flat remainder')
        front=keep(poly,(*(-n),lo+d.band_depth_m));rear=poly.difference(front)
        return faces(front,[(*(n*k),z-k*lo)])+faces(rear,[(0,0,z)])
    ridge=lo+(hi-lo)*d.ridge_fraction
    kr=k*(ridge-lo)/(hi-ridge)
    return faces(poly,[(*(n*k),z-k*lo),(*(-n*kr),z+kr*hi)])


def compound_faces(regions,d,z):
    """Union of gabled lobes: retain the upper roof in overlaps (valleys)."""
    from dataclasses import replace
    groups=[]
    for p in regions:
        xy=np.asarray(p.minimum_rotated_rectangle.exterior.coords)
        edges=xy[1:]-xy[:-1];axis=edges[np.argmin(np.linalg.norm(edges,axis=1))]
        rotation=math.degrees(math.atan2(axis[1],axis[0]))
        groups.append(plan_faces(p,replace(d,form='gable',rotation_deg=rotation),z))
    return merge_roof_faces(groups)


def merge_roof_faces(groups):
    """Upper envelope of intersecting lobe patches, with deterministic ties."""
    result=[]
    for index,group in enumerate(groups):
        for face in group:
            poly=geometry(face)
            for j,others in enumerate(groups):
                if j==index:continue
                for other in others:
                    overlap=poly.intersection(geometry(other))
                    if overlap.area<1e-8:continue
                    diff=np.asarray(other.plane)-face.plane
                    if np.linalg.norm(diff)<1e-9:
                        if j<index:poly=poly.difference(overlap)
                    else:poly=poly.difference(keep(overlap,diff))
            for p in polygons(poly):result+=faces(p,[face.plane])
    return result
