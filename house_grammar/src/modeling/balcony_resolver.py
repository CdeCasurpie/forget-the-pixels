"""Resolve balcony placement, compatibility, routes and existing substrates.

The resolver consumes a :class:`domain.surfaces.SurfaceChart` (bodies plus
facade surfaces) and the balcony controls to place, never a theta candidate.
The legacy theta front end builds a chart from its resolved masses and walls.
"""
from dataclasses import dataclass, replace
import math
import re
import numpy as np
from shapely.geometry import Polygon, LineString, box
from shapely.ops import unary_union
from domain.balconies import BalconyControls
from domain.styles import resolve_style
from modeling.assembly import mass_polygon
from modeling.balcony_catalog import preset, PATTERNS


@dataclass(frozen=True)
class ResolvedBalcony:
    controls: BalconyControls
    origin: tuple[float,float]
    tangent: tuple[float,float]
    normal: tuple[float,float]
    floor_z: float
    platform: tuple[tuple[float,float], ...]
    routes: tuple[tuple[tuple[float,float,float], ...], ...]
    upper: str
    ornate: bool
    bracket_positions: tuple[float,...] = ()


def local_routes(c):
    if c.path:return (c.path,)
    d=c.depth_m if c.kind!='juliet' else .06
    count=max(3,math.ceil(c.width_m/min(1.,c.railing.post_spacing_m)))
    front=[(c.width_m*i/count,d+c.curved_front_m*math.sin(math.pi*i/count),0.)
           for i in range(count+1)] if c.curved_front_m else [(0.,d,0.),(c.width_m,d,0.)]
    if c.corner_return_m:
        front=[(0.,d,0.),(c.width_m+d,d,0.),(c.width_m+d,-c.corner_return_m,0.)]
    segments={'left':[(0.,0.,0.),(0.,d,0.)], 'front':front,
              'right':[(c.width_m,d,0.),(c.width_m,0.,0.)]}
    if c.corner_return_m:segments['right']=[front[-1],(c.width_m,-c.corner_return_m,0.)]
    routes=[]
    for name in ('left','front','right'):
        if name not in c.sides:continue
        line=segments[name]
        if routes and routes[-1][-1]==line[0]:routes[-1].extend(line[1:])
        else:routes.append(list(line))
    return tuple(tuple(p for p in route) for route in routes)


def validate_controls(c,materials):
    if not re.fullmatch(r'[a-z][a-z0-9_]*',c.id):raise ValueError('Invalid balcony id')
    if c.kind not in ('projecting','terrace','juliet','gallery','box','stair'):raise ValueError('Invalid balcony kind')
    dims=(c.width_m,c.slab_m,c.railing.height_m,c.railing.spacing_m,
          c.railing.post_spacing_m,c.railing.post_width_m,c.enclosure_height_m)
    if not all(math.isfinite(v) and v>0 for v in dims):raise ValueError('Invalid balcony dimensions')
    if not all(math.isfinite(v) for v in (c.floor_m,c.u_m,c.depth_m,c.curved_front_m,c.corner_return_m)):
        raise ValueError('Nonfinite balcony placement')
    if c.width_m<.45 or not .04<=c.slab_m<=.5 or not .04<=c.railing.spacing_m<=.6:
        raise ValueError('Balcony dimensions exceed supported range')
    if not .3<=c.railing.height_m<=1.6 or not .4<=c.railing.post_spacing_m<=2.5 or not .03<=c.railing.post_width_m<=.3:
        raise ValueError('Invalid railing proportions')
    if c.width_m>40 or c.depth_m>4 or c.curved_front_m<0 or c.curved_front_m>1.:
        raise ValueError('Balcony geometry budget exceeded')
    if not 0<=c.corner_return_m<=4 or c.corner_return_m and (c.path or c.curved_front_m or c.kind in ('stair','juliet')):
        raise ValueError('Invalid balcony corner return')
    if c.kind in ('terrace','juliet','stair') and c.slab:raise ValueError('Terrace/Juliet/stair must use slab=false')
    if c.kind=='stair' and (c.stair_index is None or c.path or c.cover or c.brackets):
        raise ValueError('Stair railing requires stair_index and derives its own path')
    if c.kind=='juliet' and (c.path or c.brackets or c.cover):raise ValueError('Juliet has no platform/cover')
    if c.kind!='juliet' and c.depth_m<=.1:raise ValueError('Balcony depth too small')
    if len(set(c.sides))!=len(c.sides) or not set(c.sides)<= {'left','front','right'}:
        raise ValueError('Invalid balcony exposed sides')
    if not c.path and not c.sides:raise ValueError('Balcony needs an exposed side')
    if c.path and (c.slab or c.cover or c.kind in ('box','gallery') or c.brackets):
        raise ValueError('Custom railing route uses existing floor/stairs, without new slab/cover')
    if c.kind in ('gallery','box') and (c.curved_front_m or c.enclosure_height_m<c.railing.height_m+.6):
        raise ValueError('Enclosure needs a straight route and sufficient headroom')
    if c.kind=='box' and (not c.railing.enabled or set(c.sides)!={'left','front','right'}):
        raise ValueError('Closed box requires its three enclosure sides')
    for mat in (c.slab_material,c.railing.glass_material):
        if mat not in materials:raise ValueError('Unknown balcony material')
    if c.railing.material!='auto' and c.railing.material not in materials:raise ValueError('Unknown railing material')
    for route in local_routes(c):
        if not 2<=len(route)<=128:raise ValueError('Invalid railing path length')
        if not np.isfinite(route).all():raise ValueError('Invalid railing path coordinates')
        xy=np.asarray(route)[:,:2]
        if any(np.linalg.norm(b-a)<.04 for a,b in zip(xy,xy[1:])):raise ValueError('Railing path has short/vertical segment')
        if not LineString(xy).is_simple:raise ValueError('Railing path self-intersects')
        if LineString(xy).length>80:raise ValueError('Railing path exceeds budget')


def _same_plane(reference, other, tolerance=1e-6):
    """True when ``other``'s facade lies on ``reference``'s facade plane.

    Storeys of one building are separate bodies now, so a balcony must be able
    to look at the facade above and below it, not only at its own body edge.
    """
    normal = np.asarray(reference.facade.normal_xy, float)
    origin = np.asarray(reference.facade.vertex_a, float)
    return all(abs(float((np.asarray(point, float) - origin) @ normal)) <= tolerance
               for point in (other.facade.vertex_a, other.facade.vertex_b))


def _span(base_a, tangent, p0, p1):
    along = [float((np.asarray(p, float) - base_a) @ tangent) for p in (p0, p1)]
    return min(along), max(along)


def _feature_span(wall, feature, base_a, tangent):
    """Feature extent in the anchor surface frame, not the feature's own."""
    return _span(base_a, tangent,
                 wall.local_point(feature.u_m, wall.base_z)[:2],
                 wall.local_point(feature.u_m + feature.width_m, wall.base_z)[:2])


def _opening_span(wall, opening, base_a, tangent):
    return _span(base_a, tangent,
                 wall.local_point(opening.u_m, wall.base_z)[:2],
                 wall.local_point(opening.u_m + opening.width_m, wall.base_z)[:2])


def resolve_balconies(controls,architectural_style,chart,envelope,materials):
    masses=chart.bodies;walls=chart.surfaces
    result=[]; ids=set(); occupied=[]
    for c in controls:
        if c.id in ids:raise ValueError('Duplicate balcony id')
        ids.add(c.id)
        if not c.enabled:continue
        validate_controls(c,materials)
        style=resolve_style(c.style,architectural_style)
        variant,p=preset(style,c.variant)
        if p.kind=='box' and c.kind!='box':raise ValueError('Box variant requires kind=box')
        if c.kind=='box' and p.kind!='box':raise ValueError('Closed box needs a box variant')
        if p.kind=='gallery' and c.kind not in ('gallery','terrace'):raise ValueError('Gallery variant requires gallery/terrace')
        material=p.material if c.railing.material=='auto' else c.railing.material
        pattern=p.pattern if c.railing.pattern=='auto' else c.railing.pattern
        if pattern not in PATTERNS:raise ValueError('Unknown railing pattern')
        c=replace(c,style=style,variant=variant,railing=replace(c.railing,material=material,pattern=pattern))
        mass=next((m for m in masses if m.id==c.mass_ref),None)
        if mass is None:raise ValueError('Balcony references missing mass')
        surfaces=[w for w in walls if w.mass_role==mass.id and w.edge==c.edge]
        if len(surfaces)!=1:raise ValueError('Balcony needs one unambiguous facade surface')
        surface=surfaces[0]
        base_a=np.asarray(surface.facade.vertex_a,float)
        origin_full,t,n=surface.frame()
        length=surface.width_m
        b=np.asarray(surface.facade.vertex_b,float)
        if c.opening_index is not None:
            if not 0<=c.opening_index<len(surface.facade.openings):raise ValueError('Balcony opening anchor missing')
            op=surface.facade.openings[c.opening_index]; c=replace(c,u_m=op.u_m+(op.width_m-c.width_m)/2)
        z=mass.base_z+c.floor_m
        if not any(abs(z-level)<1e-5 for level in mass.floor_levels):raise ValueError('Balcony must anchor to an existing floor level')
        if c.u_m<0 or c.u_m+c.width_m>length+1e-6:raise ValueError('Balcony outside edge span')
        if surface.visible_domains:
            visible=unary_union([box(*r) for r in surface.visible_domains])
            z_local=z-surface.base_z
            lo=max(0.,min(z_local-.01,surface.height_m));hi=max(0.,min(z_local+.01,surface.height_m))
            attach=box(c.u_m,lo,c.u_m+c.width_m,hi)
            if attach.is_empty or not visible.buffer(1e-6).covers(attach):
                raise ValueError('Balcony anchor intersects hidden facade')
        if c.corner_return_m:
            ring=mass.footprint
            if not 0<=c.edge<len(ring):raise ValueError('Corner balcony requires an exterior mass edge')
            next_edge=np.asarray(ring[(c.edge+2)%len(ring)])-b
            if abs(c.u_m+c.width_m-length)>1e-5 or np.dot(next_edge/np.linalg.norm(next_edge),-n)<.9999:
                raise ValueError('Corner balcony must end at an orthogonal mass corner')
            if c.corner_return_m>np.linalg.norm(next_edge):raise ValueError('Corner return exceeds adjacent edge')
        related=[w for w in walls if _same_plane(surface,w)]
        origin=origin_full+t*c.u_m
        def world(q):return (* (origin+t*q[0]+n*q[1]),z+q[2])
        routes=tuple(tuple(world(q) for q in route) for route in local_routes(c))
        if c.curved_front_m:
            front=[(c.width_m*i/16,c.depth_m+c.curved_front_m*math.sin(math.pi*i/16),0.) for i in range(17)]
        else:front=[(0,c.depth_m,0),(c.width_m,c.depth_m,0)]
        platform=Polygon([world((0,0,0))[:2],*[world(q)[:2] for q in front],world((c.width_m,0,0))[:2]])
        if c.corner_return_m:
            platform=Polygon([world(q)[:2] for q in [(0,0,0),(0,c.depth_m,0),
                (c.width_m+c.depth_m,c.depth_m,0),(c.width_m+c.depth_m,-c.corner_return_m,0),
                (c.width_m,-c.corner_return_m,0),(c.width_m,0,0)]])
        margin=max(.20 if pattern=='bowed' else .15,c.railing.post_width_m*.7)
        if c.planters:margin=max(margin,.30)
        extent=unary_union([LineString([q[:2] for q in route]).buffer(margin,join_style=2) for route in routes])
        if c.slab or c.cover or c.kind=='box':extent=extent.union(platform.buffer(.035,join_style=2))
        if not envelope.buffer(1e-7).covers(extent):raise ValueError('Balcony projection outside permitted envelope')
        if c.kind=='stair':
            candidates=[(surface,s) for s in surface.facade.exterior_stairs]
            if not 0<=c.stair_index<len(candidates):raise ValueError('Stair anchor missing')
            wall,s=candidates[c.stair_index]
            z0=wall.base_z+s.base_z_m; z1=wall.base_z+s.target_z_m
            u0=s.u_m-c.u_m; width=s.flight_width_m; run=s.run_m
            def q(u,d,height):return world((u,d,height-z))
            if s.switchback:
                mid=z0+(z1-z0)*(s.step_count//2)/s.step_count
                u1=u0+width*1.1
                locals_=[[(u0+.06,0,z0),(u0+.06,run-.06,mid),(u1+width-.06,run-.06,mid),(u1+width-.06,0,z1)],
                         [(u0+width-.06,0,z0),(u0+width-.06,run-width,z0+(mid-z0)*(run-width)/run)],
                         [(u1+.06,run-width,mid+(z1-mid)*width/run),(u1+.06,0,z1)]]
            else:locals_=[[(u,0,z0),(u,run,z1)] for u in (u0+.06,u0+width-.06)]
            routes=tuple(tuple(q(*v) for v in path) for path in locals_)
            extent=unary_union([LineString([v[:2] for v in path]).buffer(margin,join_style=2) for path in routes])
            if not envelope.buffer(1e-7).covers(extent):raise ValueError('Stair railing outside permitted envelope')
        if not c.slab and c.kind not in ('juliet','stair'):
            support=[m for m in masses if (not c.support_mass or m.id==c.support_mass) and abs(m.roof_z-z)<1e-5]
            substrate=unary_union([mass_polygon(m) for m in support])
            if not substrate.buffer(1e-5).covers(unary_union([LineString([q[:2] for q in r]) for r in routes])):
                raise ValueError('Terrace railing has no existing roof/floor substrate')
            if any(abs(q[2]-z)>1e-6 for r in routes for q in r):
                raise ValueError('Sloped railing requires kind=stair with stair_index, not a terrace route')
        if c.slab:
            for other in masses:
                if other.id==mass.id:continue
                head=z+(c.enclosure_height_m+.1 if c.kind in ('gallery','box') or c.cover else c.railing.height_m)
                if other.base_z<head and other.roof_z>z+.05 and platform.intersection(mass_polygon(other)).area>.01:
                    raise ValueError('Balcony platform intersects another mass')
        for prev,zprev in occupied:
            if abs(z-zprev)<.05 and platform.intersection(prev).area>.01:raise ValueError('Overlapping balcony assemblies')
        if c.kind!='stair':occupied.append((platform,z))
        # A new slab/bracket must not intersect the head of a lower opening.
        # Storeys are separate bodies, so inspect every facade on the same plane.
        for w in related:
            for feature in w.facade.projections:
                if feature.kind not in ('balcony','gallery'):continue
                f0,f1=_feature_span(w,feature,base_a,t)
                if f0<c.u_m+c.width_m and f1>c.u_m and abs(w.base_z+feature.v_m-z)<.4:
                    raise ValueError('New balcony overlaps a legacy balcony; migrate that projection explicitly')
            for op in w.facade.openings:
                u0,u1=_opening_span(w,op,base_a,t)
                overlap=u0<c.u_m+c.width_m and u1>c.u_m
                if c.slab and overlap and w.base_z+op.v_m<z and w.base_z+op.v_m+op.height_m>z-c.slab_m:
                    raise ValueError('Balcony slab intersects an opening')
        brackets=[]
        if c.brackets and c.slab:
            drop=min(.55,c.depth_m*.65)
            forbidden=[]
            for w in related:
                for op in w.facade.openings:
                    if w.base_z+op.v_m<z-c.slab_m and w.base_z+op.v_m+op.height_m>z-c.slab_m-drop:
                        u0,u1=_opening_span(w,op,base_a,t)
                        forbidden.append((u0-c.u_m-.08,u1-c.u_m+.08))
            for axis in np.linspace(.15,c.width_m-.15,max(2,math.ceil(c.width_m/1.5)+1)):
                choices=[axis+shift for shift in (0.,-.15,.15,-.3,.3,-.45,.45)]
                safe=next((x for x in choices if .07<x<c.width_m-.07 and
                           not any(lo<x<hi for lo,hi in forbidden) and all(abs(x-y)>.14 for y in brackets)),None)
                if safe is None:raise ValueError('No bracket position clear of lower openings; disable brackets or adjust balcony')
                brackets.append(float(safe))
        result.append(ResolvedBalcony(c,tuple(origin),tuple(t),tuple(n),z,
                                      tuple(platform.exterior.coords)[:-1],routes,p.upper,p.ornate,tuple(brackets)))
    return tuple(result)
