"""Inferable street-frame composition -> polygonal mass/site/support IR.

No benchmark IDs, cameras or image processing belong in this module.
"""
from dataclasses import dataclass
import re
import numpy as np
import shapely
from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from domain.architecture import MassSpec
from modeling.mesh_builder import polygons


def mass_polygon(mass):
    return Polygon(mass.footprint, mass.footprint_holes)


def ring(poly):
    points = list(orient(poly, 1).exterior.coords)[:-1]
    start = min(range(len(points)), key=lambda i: points[i])
    return tuple(points[start:] + points[:start])


def holes(poly):
    return tuple(tuple(r.coords)[:-1] for r in orient(poly, 1).interiors)


def region_frame(context, region):
    p = np.asarray(context.parcel)
    edge = region.front_edge
    if edge is None:
        edge = max(context.fronts, key=lambda i: np.linalg.norm(p[(i+1)%len(p)]-p[i]))
    if not 0 <= edge < len(p):
        raise ValueError("Region front_edge outside canonical parcel")
    a, b = p[edge], p[(edge+1)%len(p)]
    t = (b-a)/np.linalg.norm(b-a)
    inward = np.array([-t[1], t[0]])
    u, d = (p-a)@t, (p-a)@inward
    if region.width_reference not in ('parcel','edge'):
        raise ValueError('Invalid width_reference')
    extent=(0.,float(np.linalg.norm(b-a))) if region.width_reference=='edge' else (float(u.min()),float(u.max()))
    return a, t, inward, (*extent,float(d.max()))


def region_polygon(context, region, tolerance=0.):
    a, t, inward, (umin, umax, depth) = region_frame(context, region)
    if not 0 <= region.u[0] < region.u[1] <= 1:
        raise ValueError("Region u must be an increasing interval in [0,1]")
    if region.depth_m is not None and region.depth != (0., 1.):
        raise ValueError("depth_m replaces fractional depth")
    d0, d1 = region.depth_m if region.depth_m is not None else np.asarray(region.depth)*depth
    if not 0 <= d0 < d1 or (region.depth_m is None and region.depth[1] > 1):
        raise ValueError("Invalid region depth")
    u0, u1 = umin + np.asarray(region.u)*(umax-umin)
    shape = Polygon([a+t*u+inward*d for u,d in ((u0,d0),(u1,d0),(u1,d1),(u0,d1))])
    parcel = Polygon(context.parcel)
    if region.fit == "parcel":
        return shapely.set_precision(shape.intersection(parcel),1e-7)
    if region.fit != "rectangle" or not parcel.buffer(tolerance+1e-7).covers(shape):
        raise ValueError("Rectangle region outside parcel tolerance (or invalid fit)")
    return shapely.set_precision(shape,1e-7)


def compose_masses(context, controls):
    if not 0 <= controls.parcel_tolerance_m <= 2:
        raise ValueError("parcel_tolerance_m must be 0..2m")
    ids = [c.id for c in controls.components]
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r'[a-z][a-z0-9_]*',i) for i in ids):
        raise ValueError("Components need unique semantic IDs")
    masses = []
    for c in controls.components:
        if c.kind not in ('enclosed','open') or not .05 <= c.slab_m <= .8:
            raise ValueError("Invalid component kind/slab")
        if c.roof and c.roof.props:
            raise ValueError("Use theta.roof.props with canonical mass refs for roof objects")
        if len(c.levels_m)<2 or c.levels_m[0]<0 or any(b-a<.5 for a,b in zip(c.levels_m,c.levels_m[1:])):
            raise ValueError("Component levels must increase by >=0.5m")
        poly = region_polygon(context,c.region,controls.parcel_tolerance_m)
        for cutout in c.cutouts:
            poly = poly.difference(region_polygon(context,cutout,controls.parcel_tolerance_m))
        parts = sorted(polygons(poly),key=lambda p:(p.centroid.x,p.centroid.y))
        if not parts or any(p.area<.5 or p.buffer(-.15).is_empty for p in parts):
            raise ValueError(f"Component {c.id}: empty or sliver geometry")
        for i,p in enumerate(parts):
            masses.append(MassSpec(f'{c.id}:{i}',ring(p),c.levels_m[0],c.levels_m[-1],
                c.levels_m,c.id,None,footprint_holes=holes(p),kind=c.kind,slab_m=c.slab_m))
    for i,a in enumerate(masses):
        for b in masses[i+1:]:
            za=[(z-a.slab_m,z) for z in a.floor_levels[1:]] if a.kind=='open' else [(a.base_z,a.roof_z)]
            zb=[(z-b.slab_m,z) for z in b.floor_levels[1:]] if b.kind=='open' else [(b.base_z,b.roof_z)]
            if any(min(hi,hj)>max(lo,lj)+1e-7 for lo,hi in za for lj,hj in zb) and mass_polygon(a).intersection(mass_polygon(b)).area>1e-6:
                raise ValueError(f"Interpenetrating components: {a.role}, {b.role}")
    return tuple(sorted(masses,key=lambda m:m.id))


@dataclass(frozen=True)
class StructuralPiece:
    id: str
    mass_id: str
    semantic: str
    polygon: tuple[tuple[float,float], ...]
    base_z: float
    top_z: float
    holes: tuple[tuple[tuple[float,float], ...], ...] = ()


def resolve_supports(context, controls, masses):
    pieces = []
    for m in masses:
        c = next(c for c in controls.components if c.id==m.role)
        s = c.support
        if s.kind not in ('bearing','columns','cantilever') or s.spacing_m<=0 or not .08<=s.column_width_m<=1.5 or s.inset_m<s.column_width_m/2 or s.max_cantilever_m<0:
            raise ValueError(f"Invalid support: {m.id}")
        p = mass_polygon(m)
        below = unary_union([mass_polygon(b) for b in masses if abs(b.roof_z-m.base_z)<1e-6])
        if m.base_z>0 and s.kind!='columns':
            reach = s.max_cantilever_m if s.kind=='cantilever' else 0.
            if below.is_empty or not below.buffer(reach+1e-6).covers(p):
                raise ValueError(f"Unsupported component {m.id}")
        if s.kind=='cantilever' and (s.max_cantilever_m<=0 or below.intersection(p).area<.25*p.area):
            raise ValueError("Cantilever requires positive reach and >=25% bearing area")
        if m.kind=='open' or (m.base_z>0 and s.kind=='columns'):
            a,t,n,_ = region_frame(context,c.region)
            coords=np.asarray(p.exterior.coords)-a
            us,ds=coords@t,coords@n
            lo_u,hi_u=us.min()+s.inset_m,us.max()-s.inset_m
            lo_d,hi_d=ds.min()+s.inset_m,ds.max()-s.inset_m
            columns=[]
            for u in np.linspace(lo_u,hi_u,max(2,int(np.ceil((hi_u-lo_u)/s.spacing_m))+1)):
                for d in np.linspace(lo_d,hi_d,max(2,int(np.ceil((hi_d-lo_d)/s.spacing_m))+1)):
                    w=s.column_width_m/2
                    poly=Polygon([a+t*(u+du)+n*(d+dd) for du,dd in ((-w,-w),(w,-w),(w,w),(-w,w))])
                    if not p.buffer(1e-7).covers(poly):
                        continue
                    top=m.roof_z-c.slab_m if m.kind=='open' else m.base_z
                    base=m.base_z if m.kind=='open' else 0.
                    base=max([base]+[b.roof_z for b in masses if b.id!=m.id and b.roof_z<=top and mass_polygon(b).buffer(1e-7).covers(poly)])
                    if top>base+1e-6:
                        columns.append(StructuralPiece(f'{m.id}/column{len(columns)}',m.id,'support_column',ring(poly),base,top))
            if len(columns)<2:
                raise ValueError(f"Too few columns in {m.id}; reduce inset/spacing or change region")
            pieces.extend(columns)
        if m.kind=='open':
            for i,z in enumerate(m.floor_levels[1:-1]):
                pieces.append(StructuralPiece(f'{m.id}/slab{i}',m.id,'open_floor_slab',m.footprint,z-c.slab_m,z,m.footprint_holes))
            covered=unary_union([mass_polygon(b) for b in masses if b.id!=m.id and b.kind=='enclosed' and abs(b.base_z-m.roof_z)<1e-6]).intersection(p)
            for i,part in enumerate(polygons(covered)):
                pieces.append(StructuralPiece(f'{m.id}/ceiling{i}',m.id,'open_floor_slab',ring(part),m.roof_z-c.slab_m,m.roof_z,holes(part)))
        elif m.base_z>0:
            underside=p.difference(below)
            for i,part in enumerate(polygons(underside)):
                pieces.append(StructuralPiece(f'{m.id}/soffit{i}',m.id,'soffit',ring(part),m.base_z,m.base_z+c.slab_m,holes(part)))
    return tuple(pieces)


@dataclass(frozen=True)
class ResolvedSiteZone:
    id: str
    kind: str
    polygon: tuple[tuple[float,float], ...]
    holes: tuple[tuple[tuple[float,float], ...], ...] = ()
    slope_deg: float = 0.
    origin: tuple[float,float] = (0.,0.)
    inward: tuple[float,float] = (0.,1.)


def resolve_zones(context, site, masses, structures):
    occupied=unary_union([mass_polygon(m) for m in masses if m.kind=='enclosed' and m.base_z<.01]+
                         [Polygon(s.polygon) for s in structures if s.semantic=='support_column' and s.base_z<.01])
    free=shapely.set_precision(Polygon(context.parcel),1e-7).difference(shapely.set_precision(occupied,1e-7))
    assigned=Polygon(); zones=[]
    if len({z.id for z in site.zones})!=len(site.zones):
        raise ValueError("Duplicate site zone id")
    for z in site.zones:
        if z.kind not in ('garden','patio','terrace','parking','driveway','corridor','paved','unclassified') or not 0<=z.slope_deg<=15:
            raise ValueError("Invalid site zone type/slope")
        if z.slope_deg and z.kind not in ('driveway','parking'):
            raise ValueError("Only parking/driveway zones can be ramps")
        shape=region_polygon(context,z.region).intersection(free)
        if shape.intersection(assigned).area>1e-6:
            raise ValueError("Overlapping site zones")
        assigned=assigned.union(shape)
        a,t,n,(_,_,depth)=region_frame(context,z.region)
        d0=z.region.depth_m[0] if z.region.depth_m else z.region.depth[0]*depth
        for i,p in enumerate(polygons(shape)):
            zones.append(ResolvedSiteZone(f'{z.id}:{i}',z.kind,ring(p),holes(p),z.slope_deg,tuple(a+n*d0),tuple(n)))
    for i,p in enumerate(polygons(free.difference(assigned))):
        zones.append(ResolvedSiteZone(f'free:{i}','unclassified',ring(p),holes(p)))
    return tuple(zones)
