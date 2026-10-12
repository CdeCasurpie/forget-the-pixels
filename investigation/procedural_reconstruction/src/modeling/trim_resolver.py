"""Resolve exposed trim paths from mass topology before emitting meshes."""
from dataclasses import dataclass
import math
import numpy as np
from shapely.geometry import Polygon, LineString
from shapely.geometry.polygon import orient
from shapely.ops import unary_union, substring
from modeling.assembly import mass_polygon
from modeling.trim_profiles import CORNICES, cornice_section, plinth_courses
from modeling.trim_sweep import sweep_domain, emit_sweep


@dataclass(frozen=True)
class ResolvedTrim:
    id: str
    sources: tuple[str,...]
    path: tuple[tuple[float,float],...]
    section: tuple[tuple[float,float],...]
    base_z: float
    material: str
    semantic: str


def mass_trim(theta,mass_id):
    for c in (*theta.massing.components,*theta.roof_bodies):
        if mass_id==c.id or mass_id.startswith(c.id+':'):
            return c.trim if c.trim is not None else theta.trim
    return theta.trim


def validate_plinth(c,materials):
    if c.design not in ('smooth','horizontal_joints','stepped','blocks'):
        raise ValueError('Unknown plinth design')
    if c.scope not in ('exposed','street') or c.material not in materials:
        raise ValueError('Invalid plinth scope/material')
    if not all(math.isfinite(v) and v>0 for v in
               (c.height_m,c.course_height_m,c.block_width_m,c.joint_width_m)):
        raise ValueError('Invalid plinth dimensions')
    if not math.isfinite(c.relief_m) or not 0<=c.relief_m<=.30:
        raise ValueError('Invalid plinth relief')
    if c.joint_width_m>=min(c.course_height_m,c.block_width_m)/3:
        raise ValueError('Plinth joint consumes course')
    if c.design!='smooth' and c.relief_m==0 and c.enabled:
        raise ValueError('Designed plinth requires positive relief; use smooth for flush finish')


def validate_trim(c,style,materials):
    a=c.cornice
    if a.profile not in (*CORNICES,'auto') or a.anchor not in ('wall_top','parapet_top'):
        raise ValueError('Invalid cornice profile/anchor')
    if a.scope not in ('exposed','street') or a.material not in materials:
        raise ValueError('Invalid cornice scope/material')
    if not all(math.isfinite(v) and v>0 for v in (a.height_m,a.projection_m)) or not math.isfinite(a.offset_m):
        raise ValueError('Invalid cornice dimensions')
    if a.enabled:cornice_section(a,style)
    validate_plinth(c.plinth,materials)


def lines(geometry):
    if geometry.is_empty:return []
    if geometry.geom_type in ('LineString','LinearRing'):return [LineString(geometry.coords)]
    return [line for g in getattr(geometry,'geoms',()) for line in lines(g)]


def polygons(geometry):
    if geometry.is_empty:return []
    if geometry.geom_type=='Polygon':return [geometry]
    return [p for g in getattr(geometry,'geoms',()) for p in polygons(g)]


def perimeter_paths(poly,control,blockers,context):
    parcel=Polygon(context.parcel)
    points=list(parcel.exterior.coords)
    party=unary_union([LineString([points[i],points[i+1]])
                       for i in range(len(points)-1) if i not in context.fronts])
    result=[]
    for p in polygons(poly):
        p=orient(p,1)
        for ring in [p.exterior]+(list(p.interiors) if control.courtyards else []):
            path=LineString(ring.coords)
            if not blockers.is_empty:path=path.difference(blockers.buffer(1e-6,join_style=2))
            if control.scope=='street':
                # Include setback facades parallel to a declared street front.
                kept=[]
                for line in lines(path):
                    xy=list(line.coords)
                    for a,b in zip(xy,xy[1:]):
                        t=np.asarray(b)-a; t=t/np.linalg.norm(t)
                        for i in context.fronts:
                            ft=np.asarray(points[i+1])-points[i]; ft=ft/np.linalg.norm(ft)
                            if np.dot(t,ft)>.999:
                                kept.append(LineString([a,b])); break
                from shapely.ops import linemerge
                merged=unary_union(kept)
                path=linemerge(merged) if merged.geom_type=='MultiLineString' else merged
            if not party.is_empty:path=path.difference(party.buffer(1e-6,cap_style=2))
            # Restore a split at the arbitrary ring start, retaining orientation.
            chunks=lines(path)
            if len(chunks)>1 and np.linalg.norm(np.asarray(chunks[-1].coords[-1])-chunks[0].coords[0])<1e-7:
                chunks=[LineString(list(chunks[-1].coords)+list(chunks[0].coords)[1:])]+chunks[1:-1]
            result.extend(chunks)
    return result


def opening_cuts(walls,bottom,top,depth):
    cuts=[]
    for w in walls:
        f=w.facade
        if not f.has_program:continue
        a=np.asarray(f.vertex_a)+np.asarray(f.normal_xy)*w.plane_offset_m
        t=(np.asarray(f.vertex_b)-f.vertex_a)/f.width_m
        n=np.asarray(f.normal_xy)
        for op in f.openings:
            if w.base_z+op.v_m>=top-1e-8 or w.base_z+op.v_m+op.height_m<=bottom+1e-8:continue
            lo=op.u_m; hi=lo+op.width_m
            cuts.append(Polygon([a+t*u+n*d for u,d in
                                 ((lo,-.03),(hi,-.03),(hi,depth*4+.05),(lo,depth*4+.05))]))
    return unary_union(cuts)


def plinth_pieces(paths,c,sources,prefix,walls=()):
    """Courses share stationing around corners. Cut accesses after stationing."""
    if not c.enabled or c.relief_m==0:return []
    courses=list(plinth_courses(c))
    if c.design in ('horizontal_joints','blocks'):
        courses.insert(0,(0.,c.height_m,c.relief_m*.25,-1))
    result=[]
    for row,(bottom,top,depth,stagger) in enumerate(courses):
        heights=sorted({bottom,top,*[z for w in walls for op in w.facade.openings
                       for z in (w.base_z+op.v_m,w.base_z+op.v_m+op.height_m) if bottom<z<top]})
        for path in paths:
            segments=[path]
            if c.design=='blocks' and stagger>=0:
                if path.length/c.block_width_m>2048:raise ValueError('Plinth exceeds block budget')
                starts=np.arange(-stagger*c.block_width_m/2,path.length,c.block_width_m)
                segments=[substring(path,max(0.,x+c.joint_width_m/2),min(path.length,x+c.block_width_m-c.joint_width_m/2))
                          for x in starts if x+c.block_width_m-c.joint_width_m/2>0 and x+c.joint_width_m/2<path.length]
            for z0,z1 in zip(heights,heights[1:]):
                cuts=opening_cuts(walls,z0,z1,c.relief_m)
                for segment in segments:
                    for line in lines(segment.difference(cuts)):
                        if line.length<1e-6:continue
                        # Raised courses sit on, rather than coincide with, backing.
                        back=c.relief_m*.25 if c.design in ('horizontal_joints','blocks') and stagger>=0 else -.002
                        section=((back,0.),(depth,0.),(depth,z1-z0),(back,z1-z0))
                        result.append(ResolvedTrim(f'{prefix}/{len(result)}',sources,tuple(line.coords),section,z0,c.material,'trim_plinth'))
    return result


def resolve_trims(context,theta,masses,walls,roofs,materials,envelope):
    groups={}; output=[]
    for m in masses:
        c=mass_trim(theta,m.id)
        if c is None:continue
        validate_trim(c,theta.architectural_style,materials)
        if m.kind!='enclosed':continue
        if any(w.facade.top_profile for w in walls if w.mass_role==m.id):
            raise ValueError('Perimeter trim currently requires horizontal tops')
        # Recessed facade zones keep the outer cornice line; the portico
        # soffit and columns carry the overhang. Returns close the sides.
        if c.cornice.enabled:
            a=c.cornice
            roof=next((r for r in roofs if r.mass_id==m.id),None)
            parapet=roof.parapet_height_m if roof else 0.
            if a.anchor=='parapet_top' and parapet<=0 and roof is not None:
                raise ValueError('Cornice parapet anchor requires a parapet')
            z=m.roof_z+(parapet if a.anchor=='parapet_top' else 0)+a.offset_m
            if a.height_m>z-m.base_z:raise ValueError('Cornice exceeds wall height')
            groups.setdefault(('cornice',a,z,m.roof_z),[]).append(m)
        if c.plinth.enabled and abs(m.base_z)<1e-6:
            if c.plinth.height_m>m.roof_z-m.base_z:raise ValueError('Plinth exceeds ground wall height')
            groups.setdefault(('plinth',c.plinth,0.,0.),[]).append(m)
    for (kind,c,z,roof_z),members in groups.items():
        sources=tuple(m.id for m in members)
        poly=unary_union([mass_polygon(m) for m in members])
        blockers=unary_union([mass_polygon(m) for m in masses if m.id not in sources and m.kind=='enclosed' and
                            (m.base_z<=roof_z+1e-6 and m.roof_z>=roof_z-1e-6 if kind=='cornice'
                             else m.base_z<=1e-6)])
        paths=perimeter_paths(poly,c,blockers,context)
        if kind=='cornice':
            section=cornice_section(c,theta.architectural_style)
            cuts=opening_cuts(walls,z-c.height_m,z,c.projection_m)
            for path in paths:
                if path.intersection(cuts).length>1e-7:raise ValueError('Cornice overlaps opening; adjust height or anchor')
                output.append(ResolvedTrim(f'trim/cornice/{len(output)}',sources,tuple(path.coords),section,
                                           z-c.height_m,c.material,'trim_cornice'))
        else:output.extend(plinth_pieces(paths,c,sources,f'trim/plinth/{len(output)}',walls))
    for piece in output:
        if not envelope.buffer(1e-7).covers(sweep_domain(piece.path,piece.section,envelope)):
            raise ValueError(f'{piece.id}: projection outside permitted envelope; path={piece.path}')
    return tuple(output)


def emit_trims(builder,pieces,envelope):
    for p in pieces:
        with builder.assembly(p.id):
            emit_sweep(builder,p.path,p.section,p.base_z,p.material,p.semantic,envelope)
