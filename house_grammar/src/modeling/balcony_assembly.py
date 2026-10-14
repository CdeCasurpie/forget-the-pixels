"""Balcony platforms, modular enclosures, supports and decorative carpentry."""
import math
from dataclasses import replace
import numpy as np
from shapely.geometry import Polygon, box, Point
from modeling.railing_assembly import build_railing
from modeling.trim_sweep import emit_sweep
from modeling.trim_profiles import cornice_section
from domain.theta import CorniceControls


def build_balcony(mb,resolved,envelope):
    c=resolved.controls
    a,t,n=map(np.asarray,(resolved.origin,resolved.tangent,resolved.normal))
    floor=resolved.floor_z
    mat=c.railing.material
    platform=Polygon(resolved.platform)
    with mb.assembly('balcony/'+c.id):
        if c.slab:
            mb.solid(platform,floor-c.slab_m,floor,c.slab_material,'balcony_platform',clip='envelope')
            if c.fascia:
                profile=cornice_section(CorniceControls(height_m=min(.14,c.slab_m),projection_m=.025),c.style)
                # Perimeter already continuous, with the rear edge against the wall.
                emit_sweep(mb,list(platform.exterior.coords),profile,floor-c.slab_m,
                           mat if mat=='wood' else c.slab_material,'balcony_fascia',envelope)
        for route in resolved.routes:
            build_railing(mb,route,c.railing,c.railing.pattern,mat,envelope,resolved.ornate)
        if c.brackets and c.slab:
            for u in resolved.bracket_positions:
                # Side silhouette extruded across its width. Concave consoles,
                # not boxes scaled to the length of the balcony.
                z=floor-c.slab_m
                depth=c.depth_m*.78; drop=min(.55,c.depth_m*.65)
                if c.style=='moderno':pts=[(0,z),(depth,z),(0,z-drop)]
                else:pts=[(0,z),(depth,z),(depth*.9,z-.09),(depth*.55,z-.15),
                          (depth*.25,z-drop*.75),(0,z-drop)]
                mb.panel(a+t*u,n,t,[Polygon(pts)],-.065,.065,lambda *args:mat,
                         'balcony_bracket',clip='envelope')
        if c.planters:
            count=max(1,math.floor(c.width_m/1.3))
            for u in np.linspace(c.width_m/(2*count),c.width_m-c.width_m/(2*count),count):
                width=min(.8,c.width_m/count-.15)
                footprint=Polygon([a+t*x+n*d for x,d in ((u-width/2,c.depth_m+.03),
                    (u+width/2,c.depth_m+.03),(u+width/2,c.depth_m+.25),(u-width/2,c.depth_m+.25))])
                inner=footprint.buffer(-.025,join_style=2)
                base=floor+c.railing.height_m*.55
                mb.solid(footprint,base,base+.025,mat,'balcony_planter_base',clip='envelope')
                mb.solid(footprint.difference(inner),base+.025,base+.22,mat,'balcony_planter',clip='envelope')
                mb.solid(inner,base+.025,base+.17,'soil','balcony_planter_soil',clip='envelope')
        enclosed=c.kind=='box'
        tall=c.kind in ('box','gallery') or c.cover
        if not tall:return
        ceiling=floor+c.enclosure_height_m
        if c.cover or enclosed:
            mb.solid(platform,ceiling,ceiling+.10,mat if mat=='wood' else c.slab_material,
                     'balcony_cover',clip='envelope')
            profile=cornice_section(CorniceControls(height_m=.12,projection_m=.025),c.style)
            emit_sweep(mb,list(platform.exterior.coords),profile,ceiling-.12,mat,
                       'balcony_cover_cornice',envelope)
        columns=set()
        for route in resolved.routes:
            for p0,p1 in zip(route,route[1:]):
                p0,p1=np.asarray(p0),np.asarray(p1)
                length=np.linalg.norm(p1[:2]-p0[:2]); tangent=(p1[:2]-p0[:2])/length
                normal=np.array([tangent[1],-tangent[0]])
                bays=max(1,math.ceil(length/c.railing.post_spacing_m))
                for i in range(bays+1):
                    xy=p0[:2]+tangent*(length*i/bays)
                    key=tuple(np.round(xy,7))
                    if key in columns:continue
                    columns.add(key)
                    if c.variant=='column_gallery':
                        from domain.vertical_members import MemberDesign
                        from modeling.vertical_member_assembly import build_member
                        design=c.column_member or MemberDesign(style='clasico',variant='tuscan',material=c.slab_material)
                        if design.style=='auto':design=replace(design,style=c.style)
                        build_member(mb,xy,tangent,normal,floor,.16,.16,c.enclosure_height_m,design)
                    else:
                        from domain.vertical_members import MemberDesign
                        from modeling.vertical_member_assembly import build_member
                        design=c.column_member or MemberDesign(style='madera' if mat=='wood' else 'moderno',
                            material=mat,base=False,capital=False)
                        if design.style=='auto':design=replace(design,style=c.style)
                        build_member(mb,xy,tangent,normal,floor,.09,.09,c.enclosure_height_m,design)
                for i in range(bays):
                    lo=length*i/bays+.055; hi=length*(i+1)/bays-.055
                    low=floor+c.railing.height_m+.06; high=ceiling-.18
                    if hi-lo<.08:continue
                    def panel(shape,material,name,depth=.035):
                        mb.panel(p0[:2],tangent,normal,[shape],-depth/2,depth/2,
                                 lambda *args:material,name,clip='envelope')
                    if enclosed:
                        for z in (low,high):panel(box(lo,z-.025,hi,z+.025),mat,'balcony_transom')
                        if resolved.upper=='glass':
                            divisions=max(1,math.ceil((hi-lo)/.55))
                            for j in range(divisions):
                                x0=lo+(hi-lo)*j/divisions; x1=lo+(hi-lo)*(j+1)/divisions
                                panel(box(x0+.02,low+.02,x1-.02,high-.02),c.railing.glass_material,'balcony_enclosure_glass',.012)
                                panel(box(x0-.015,low,x0+.015,high),mat,'balcony_mullion')
                            panel(box(lo,(low+high)/2-.018,hi,(low+high)/2+.018),mat,'balcony_mullion')
                    if resolved.upper in ('lattice','fretwork') or resolved.ornate:
                        bottom=low if enclosed and resolved.upper=='lattice' else max(low,high-.40)
                        # Real perforations through a framed upper frieze.
                        shape=box(lo,bottom,hi,high)
                        pitch=.16; count=max(1,math.floor((hi-lo)/pitch))
                        for j in range(count):
                            x=lo+(hi-lo)*(j+.5)/count
                            if resolved.upper=='lattice':
                                for z in np.arange(bottom+.075,high-.04,.15):
                                    shape=shape.difference(box(x-.048,z-.048,x+.048,z+.048))
                            else:
                                z=(bottom+high)/2
                                shape=shape.difference(Polygon([(x,z-.13),(x+.052,z),(x,z+.13),(x-.052,z)]))
                        panel(shape,mat,'balcony_fretwork')
                    if resolved.ornate and c.fascia:
                        # Hanging scalloped boards below the floor edge.
                        count=max(1,math.ceil((hi-lo)/.24))
                        for j in range(count):
                            x=lo+(hi-lo)*(j+.5)/count; w=min(.10,(hi-lo)/count*.45)
                            shape=Polygon([(x-w,floor-.12),(x+w,floor-.12),
                                           (x+w*.55,floor-.25),(x,floor-.34),(x-w*.55,floor-.25)])
                            panel(shape,mat,'balcony_fretwork_fascia')
