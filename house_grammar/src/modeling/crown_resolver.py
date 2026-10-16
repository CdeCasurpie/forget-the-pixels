"""Crown anchors and explicit, auditable rule classification."""
from dataclasses import dataclass, replace
import re
import numpy as np
from shapely.geometry import Polygon, box, MultiPoint
from shapely.ops import unary_union
from domain.crowns import CrownControls
from modeling.crown_paths import validate, paths, body_shapes
from modeling.crown_assembly import aperture_shape, moulding_section
from modeling.elevation_sweep import sweep_mesh


@dataclass(frozen=True)
class ResolvedCrown:
    controls: CrownControls
    origin: tuple[float,float]
    tangent: tuple[float,float]
    normal: tuple[float,float]
    base_z: float
    classification_reason: str


def resolve_crowns(theta,masses,walls,envelope,materials,wall_refs=None):
    wall_refs=wall_refs or {}
    result=[];ids=set();occupied=[]
    for c in theta.crowns:
        if not re.fullmatch('[a-z][a-z0-9_]*',c.id) or c.id in ids:raise ValueError('Invalid/duplicate crown ID')
        ids.add(c.id)
        if not c.enabled:continue
        style=theta.architectural_style if c.design.style=='auto' else c.design.style
        d=replace(c.design,style=style)
        if theta.architectural_style and style!=theta.architectural_style:raise ValueError('Crown style conflicts with building')
        family,reason=validate(d,c.width_m,c.height_m)
        d=replace(d,family=family);c=replace(c,design=d)
        for mat in (d.material,d.moulding_material,d.field_material):
            if mat is not None and mat not in materials:raise ValueError('Unknown crown material')
        if not np.isfinite((c.u_m,c.base_m)).all():raise ValueError('Invalid crown placement')
        mass=next((m for m in masses if m.id==c.mass_ref),None)
        if mass is None:raise ValueError('Crown mass missing')
        candidates=[w for w in walls if w.mass_role==c.mass_ref and w.edge==c.edge and
                     (c.id not in wall_refs or w.facade.edge_id==wall_refs[c.id]) and
                     (c.id in wall_refs or c.anchor!='wall_top' or abs(w.base_z+w.height_m-mass.roof_z)<1e-6)]
        if len(candidates)!=1:raise ValueError('Crown needs one unambiguous facade anchor')
        w=candidates[0];f=w.facade
        if c.anchor=='wall_top':
            if f.top_profile:raise ValueError('Crown duplicates existing facade top profile')
            z=(w.base_z+w.height_m if c.id in wall_refs else mass.roof_z)+c.base_m
            if abs(c.base_m)>.02:raise ValueError('Wall-top crown must contact wall top')
        elif c.anchor=='facade':z=mass.base_z+c.base_m
        elif c.anchor=='opening_top':
            if c.opening_index is None or not 0<=c.opening_index<len(f.openings):raise ValueError('Crown opening anchor missing')
            op=f.openings[c.opening_index]
            z=w.base_z+op.v_m+op.height_m+c.base_m
            c=replace(c,u_m=op.u_m+(op.width_m-c.width_m)/2)
        else:raise ValueError('Unknown crown anchor')
        if c.u_m<0 or c.u_m+c.width_m>f.width_m:raise ValueError('Crown exceeds facade span')
        if c.anchor!='wall_top' and (z<w.base_z or z+c.height_m>w.base_z+w.height_m):raise ValueError('Attached crown exceeds wall height')
        a=np.asarray(f.vertex_a)+np.asarray(f.normal_xy)*w.plane_offset_m
        t=(np.asarray(f.vertex_b)-f.vertex_a)/f.width_m;n=np.asarray(f.normal_xy)
        routes=paths(d,c.width_m,c.height_m)
        shape=unary_union(body_shapes(routes))
        if c.aperture!='none':
            if c.anchor!='wall_top':raise ValueError('Crown aperture requires wall-top body, not a solid backing wall')
            if not np.isfinite((c.aperture_width_m,c.aperture_height_m,c.aperture_sill_m)).all() or min(c.aperture_width_m,c.aperture_height_m,c.aperture_sill_m)<=0:
                raise ValueError('Invalid crown aperture dimensions')
            hole=aperture_shape(c.aperture,c.aperture_width_m,c.aperture_height_m,c.aperture_sill_m,c.width_m/2)
            if not shape.buffer(-d.moulding_width_m*1.3).covers(hole):raise ValueError('Crown aperture does not fit field')
            if family=='broken':raise ValueError('Broken crown has no central aperture substrate')
        domain=box(c.u_m,z-w.base_z,c.u_m+c.width_m,z-w.base_z+c.height_m)
        if w.visible_domains:
            visible=unary_union([box(*r) for r in w.visible_domains])
            support=box(c.u_m,w.height_m-.01,c.u_m+c.width_m,w.height_m) if c.anchor=='wall_top' else domain
            if not visible.buffer(1e-6).covers(support):raise ValueError('Crown anchor intersects hidden facade')
        for op in f.openings:
            if domain.intersection(box(op.u_m,op.v_m,op.u_m+op.width_m,op.v_m+op.height_m)).area>1e-7:raise ValueError('Crown overlaps existing opening')
        coords=[a+t*x+n*y for x,y in ((c.u_m,-d.thickness_m),(c.u_m+c.width_m,-d.thickness_m),
                                     (c.u_m,d.projection_m+.06),(c.u_m+c.width_m,d.projection_m+.06))]
        for route in routes:
            vv,_=sweep_mesh(a,t,n,[(c.u_m+x,z+y) for x,y in route],moulding_section(d))
            coords.extend(vv[:,:2])
        footprint=MultiPoint(coords).convex_hull
        if not envelope.buffer(1e-6).covers(footprint):raise ValueError('Crown outside permitted envelope')
        for other in masses:
            if other.id==mass.id:continue
            if other.base_z<z+c.height_m-1e-6 and other.roof_z>z+1e-6:
                from modeling.assembly import mass_polygon
                if footprint.intersection(mass_polygon(other)).area>1e-6:raise ValueError('Crown intersects another mass')
        for other,lo,hi in occupied:
            if min(z+c.height_m,hi)>max(z,lo)+1e-5 and footprint.intersection(other).area>1e-6:raise ValueError('Overlapping crowns')
        occupied.append((footprint,z,z+c.height_m))
        result.append(ResolvedCrown(c,tuple(a),tuple(t),tuple(n),z,reason))
    return tuple(result)
