"""Continuous architrave/frieze/cornice, plus migration of facade orders."""
from dataclasses import replace
import math
import numpy as np
from shapely import line_merge
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from domain.theta import CorniceControls
from domain.styles import resolve_style
from modeling.assembly import mass_polygon
from modeling.trim_profiles import cornice_section
from modeling.trim_resolver import ResolvedTrim, perimeter_paths, opening_cuts, lines, mass_trim
from modeling.trim_sweep import sweep_domain
from modeling.crown_catalog import STYLES


def courses(height,projection,style,material,frieze_material):
    return ((0.,height*.22,projection*.65,material,'entablature_architrave'),
            (height*.22,height*.70,projection*.42,frieze_material,'entablature_frieze'),
            (height*.70,height,projection,material,'entablature_cornice'))


def resolve_entablatures(theta,masses,walls,envelope,materials,context):
    result=[];ids=set()
    def emit(route,z,height,depth,style,mat,field,sources,prefix):
        for low,high,projection,material,semantic in courses(height,depth,style,mat,field):
            section=((- .002,0.),(projection,0.),(projection,high-low),(-.002,high-low)) if semantic.endswith('frieze') else cornice_section(
                CorniceControls(profile=style,height_m=high-low,projection_m=projection),style)
            cuts=opening_cuts(walls,z+low,z+high,projection)
            for path in lines(route.difference(cuts)):
                if path.length<.03:continue
                domain=sweep_domain(path.coords,section,envelope)
                if not envelope.buffer(1e-6).covers(domain):raise ValueError('Entablature outside permitted envelope')
                result.append(ResolvedTrim(prefix+'/'+str(len(result)),sources,tuple(path.coords),section,z+low,material,semantic))
    for c in theta.entablatures:
        if not c.id or c.id in ids:raise ValueError('Duplicate entablature ID')
        ids.add(c.id)
        if not c.enabled:continue
        style=resolve_style(c.style,theta.architectural_style)
        if style not in STYLES or c.scope not in ('street','exposed') or c.anchor not in ('wall_top','absolute'):raise ValueError('Invalid entablature style/scope/anchor')
        if not all(math.isfinite(v) for v in (c.height_m,c.projection_m,c.top_m)) or not .08<=c.height_m<=2 or not .02<=c.projection_m<=.6:raise ValueError('Invalid entablature dimensions')
        if c.material not in materials or c.frieze_material not in materials:raise ValueError('Unknown entablature material')
        if c.ornament not in ('none','dentils'):raise ValueError('Unknown entablature ornament')
        available={m.id for m in masses}
        if not set(c.mass_refs)<=available:raise ValueError('Entablature mass missing')
        chosen=[m for m in masses if m.kind=='enclosed' and (not c.mass_refs or m.id in c.mass_refs)]
        groups={}
        for m in chosen:
            top=m.roof_z+c.top_m if c.anchor=='wall_top' else c.top_m
            if top-c.height_m<m.base_z or top>m.roof_z+.001:raise ValueError('Entablature must fit supporting wall')
            groups.setdefault(top,[]).append(m)
        for top,group in groups.items():
            poly=unary_union([mass_polygon(m) for m in group]);sources=tuple(m.id for m in group)
            blockers=unary_union([mass_polygon(m) for m in masses if m.id not in sources and m.base_z<top and m.roof_z>=top])
            control=CorniceControls(scope=c.scope)
            for route in perimeter_paths(poly,control,blockers,context):
                emit(route,top-c.height_m,c.height_m,c.projection_m,style,c.material,c.frieze_material,sources,'entablature/'+c.id)
                if c.ornament=='dentils':
                    # Independent complete dentils; no stretching across corners.
                    xy=list(route.coords)
                    for a,b in zip(xy,xy[1:]):
                        edge=LineString([a,b]);count=max(1,int(edge.length/.24))
                        for i in range(count):
                            from shapely.ops import substring
                            mid=edge.length*(i+.5)/count;half=min(.045,edge.length/count*.24)
                            section=((.0,0),(.11,0),(.11,.09),(.0,.09))
                            path=substring(edge,mid-half,mid+half)
                            if path.intersection(opening_cuts(walls,top-.2,top-.11,.11)).length>1e-7:continue
                            if not envelope.buffer(1e-6).covers(sweep_domain(path.coords,section,envelope)):raise ValueError('Dentil outside envelope')
                            result.append(ResolvedTrim('entablature/'+c.id+'/'+str(len(result)),sources,tuple(path.coords),section,top-.2,c.material,'entablature_dentil'))
    # ArchitecturalOrder remains a compositor, but its horizontal parts become
    # merged paths. Explicit mass-level entablatures take precedence.
    managed={m.id for c in theta.entablatures if c.enabled for m in masses if not c.mass_refs or m.id in c.mass_refs}
    groups={}
    for w in walls:
        if w.mass_role in managed:continue
        f=w.facade;a=np.asarray(f.vertex_a)+np.asarray(f.normal_xy)*w.plane_offset_m
        t=(np.asarray(f.vertex_b)-f.vertex_a)/f.width_m
        for p in f.projections:
            if p.source!='architectural_order' or p.kind not in ('panel','cornice'):continue
            trim=mass_trim(theta,w.mass_role)
            if trim is not None and (p.kind=='cornice' or p.kind=='panel' and p.v_m==0):continue
            key=(w.base_z+p.v_m,p.height_m,p.depth_m,p.material_slot,p.kind)
            domains=w.visible_domains or ((0.,0.,f.width_m,w.height_m),)
            intervals=unary_union([LineString([(u0,0),(u1,0)]) for u0,z0,u1,z1 in domains
                                  if z0<=p.v_m+p.height_m/2<=z1])
            for interval in lines(intervals):
                lo,hi=interval.bounds[0],interval.bounds[2]
                route=LineString([a+t*lo,a+t*hi])
                groups.setdefault(key,[]).append((route,w.mass_role))
    for (z,h,depth,mat,kind),items in groups.items():
        merged=line_merge(unary_union([r for r,_ in items]),directed=True)
        for route in lines(merged):
            emit(route,z,h,depth,theta.architectural_style or 'republicano',mat,mat,tuple(sorted({m for _,m in items})),'entablature/order')
    return tuple(result)
