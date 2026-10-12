"""Resolve facade-local anchors before emitting any new vertical-member mesh."""
from dataclasses import dataclass, replace
import re
import numpy as np
from shapely.geometry import Polygon, MultiPoint, box
from shapely.ops import unary_union
from domain.vertical_members import VerticalMemberControls
from modeling.vertical_member_assembly import member_rings


@dataclass(frozen=True)
class ResolvedMember:
    controls: VerticalMemberControls
    center: tuple[float,float]
    tangent: tuple[float,float]
    normal: tuple[float,float]
    bottom: float


def resolve_members(theta,masses,walls,envelope,materials):
    result=[]; ids=set(); occupied=[]
    for c in theta.vertical_members:
        if not re.fullmatch('[a-z][a-z0-9_]*',c.id) or c.id in ids:raise ValueError('Invalid/duplicate member ID')
        ids.add(c.id)
        if not c.enabled:continue
        style=theta.architectural_style if c.design.style=='auto' else c.design.style
        if theta.architectural_style and style!=theta.architectural_style:raise ValueError('Member style conflicts with building')
        c=replace(c,design=replace(c.design,style=style))
        if not np.isfinite((c.u_m,c.bottom_m,c.offset_m,c.embed_ratio)).all():raise ValueError('Nonfinite member anchor')
        if c.placement not in ('attached','embedded','freestanding','corner'):raise ValueError('Unknown member placement')
        if not 0<=c.embed_ratio<=1:raise ValueError('Invalid embed ratio')
        for mat in (c.design.material,c.design.base_material,c.design.capital_material):
            if mat is not None and mat not in materials:raise ValueError('Unknown member material')
        mass=next((m for m in masses if m.id==c.mass_ref),None)
        if mass is None:raise ValueError('Unknown member mass')
        candidates=[w for w in walls if w.mass_role==c.mass_ref and w.edge==c.edge and
                    w.base_z-1e-6<=mass.base_z+c.bottom_m and
                    w.base_z+w.height_m+1e-6>=mass.base_z+c.bottom_m+c.height_m]
        candidates=[w for w in candidates if 0<=c.u_m<=w.facade.width_m]
        if len(candidates)!=1:raise ValueError('Member anchor must identify one exposed facade band')
        wall=candidates[0]; f=wall.facade
        t=(np.asarray(f.vertex_b)-f.vertex_a)/f.width_m; n=np.asarray(f.normal_xy)
        along=c.u_m
        if c.placement=='corner':
            if min(abs(along),abs(along-f.width_m))>1e-6:raise ValueError('Corner member must anchor at edge endpoint')
            edge=c.edge; ring=mass.footprint
            v=np.asarray(ring[edge])-np.asarray(ring[(edge-1)%len(ring)]) if along==0 else np.asarray(ring[(edge+2)%len(ring)])-np.asarray(ring[(edge+1)%len(ring)])
            if abs(np.dot(v/np.linalg.norm(v),t))>1e-5:raise ValueError('Corner member requires an orthogonal corner')
        embed=c.embed_ratio if c.placement in ('embedded','corner') else 0.
        distance=c.offset_m+(c.depth_m*(.5-embed) if c.placement!='freestanding' else 0.)
        center=np.asarray(f.vertex_a)+t*along+n*(wall.plane_offset_m+distance)
        bottom=mass.base_z+c.bottom_m
        parts,orn=member_rings(c.design,c.width_m,c.depth_m,c.height_m)
        local=np.vstack([ring[:,:2] for _,_,rings in parts for ring in rings])
        footprint=MultiPoint(center+local[:,:1]*t+local[:,1:]*n).convex_hull
        if c.design.ornament and orn[2] in ('volutes','leaves','composite','saddle'):
            footprint=footprint.buffer(max(c.width_m,c.depth_m)*(.45 if orn[2]=='saddle' else .20))
        if not envelope.buffer(1e-7).covers(footprint):raise ValueError('Vertical member outside permitted envelope')
        u0,u1=c.u_m+local[:,0].min(),c.u_m+local[:,0].max()
        # Embedded corners intentionally wrap the endpoint; other members must fit.
        if c.placement!='corner' and (u0<0 or u1>f.width_m):raise ValueError('Member exceeds facade span')
        z0=bottom-wall.base_z; domain=box(max(0,u0),z0,min(f.width_m,u1),z0+c.height_m)
        if wall.visible_domains and not unary_union([box(*d) for d in wall.visible_domains]).buffer(1e-6).covers(domain):
            raise ValueError('Member intersects a hidden facade region')
        if c.placement!='freestanding':
            for op in f.openings:
                if domain.intersection(box(op.u_m,op.v_m,op.u_m+op.width_m,op.v_m+op.height_m)).area>1e-7:
                    raise ValueError('Member intersects an opening')
            for p in f.projections:
                if p.kind in ('pilaster','classical_pilaster','composite_pilaster') and domain.intersection(
                    box(p.u_m,p.v_m,p.u_m+p.width_m,p.v_m+p.height_m)).area>1e-7:
                    raise ValueError('Member duplicates a facade projection; migrate that projection')
        for shape,lo,hi in occupied:
            if min(bottom+c.height_m,hi)>max(bottom,lo)+1e-6 and shape.intersection(footprint).area>1e-7:
                raise ValueError('Overlapping vertical members')
        occupied.append((footprint,bottom,bottom+c.height_m))
        result.append(ResolvedMember(c,tuple(center),tuple(t),tuple(n),bottom))
    return tuple(result)
