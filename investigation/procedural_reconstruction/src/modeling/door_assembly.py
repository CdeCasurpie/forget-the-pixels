"""Contour-linked doors and gateways, assembled in facade-local coordinates.

Style selects section/ornaments; dimensions select repeated panels, not stretched
geometry. Leaf polygons and their hardware rotate about the jamb hinges.
"""
import math
from dataclasses import replace
import numpy as np
from shapely.geometry import box, Polygon, Point, LineString
from shapely.affinity import translate
from shapely.ops import unary_union
from modeling.apertures import opening_shape
from modeling.window_assembly import PROFILES

DEFAULTS = {'republicano':'panelled', 'barroco':'panelled', 'clasico':'panelled',
            'madera':'boards', 'moderno':'louvers'}
MATERIALS = ('wood','metal','frame','stone','plaster','concrete','brick','glass','accent')


def layout(op):
    clear=opening_shape(op).buffer(-op.frame_width_m,join_style=2)
    x0,y0,x1,y1=clear.bounds
    split=y1-op.door.transom_height_m
    body=clear.intersection(box(x0,y0,x1,split-.025 if op.door.transom_height_m else y1))
    transom=clear.intersection(box(x0,split+.025,x1,y1)) if op.door.transom_height_m else Polygon()
    count=op.door.leaves or (2 if x1-x0>=1.35 else 1)
    leaves=[body.intersection(box(x0+(x1-x0)*i/count+.009,y0+.009,
                                  x0+(x1-x0)*(i+1)/count-.009,y1)) for i in range(count)]
    return clear,body,transom,leaves,split


def portal_domain(op):
    d=op.door
    if d.portal=='none' and not d.cornice:return Polygon()
    extra=d.portal_gap_m+d.portal_width_m*1.1 if d.portal!='none' else .08
    return box(op.u_m-extra,op.v_m,op.u_m+op.width_m+extra,
               op.v_m+op.height_m+(.20 if d.cornice else 0))


def validate_door(op):
    d=op.door
    if op.kind not in ('door','gate') or d.model not in DEFAULTS:
        raise ValueError('Invalid door kind/model')
    if op.shape not in ('rectangle','arch'):raise ValueError('Door requires rectangle or arch')
    if d.leaves not in (0,1,2):raise ValueError('Door leaves must be auto, one or two')
    if d.construction not in ('auto','panelled','glazed','grille','boards','louvers'):
        raise ValueError('Invalid door construction')
    if d.portal not in ('none','pilasters','columns'):raise ValueError('Invalid door portal')
    if d.transom_infill not in ('glass','open'):raise ValueError('Invalid transom infill')
    if d.grille_pattern not in ('auto','vertical','grid','rings','scrolls'):
        raise ValueError('Invalid door grille')
    dims=(op.width_m,op.height_m,op.frame_width_m,op.frame_depth_m,op.recess_m,
          d.portal_width_m,d.portal_depth_m,d.grille_spacing_m)
    if not all(math.isfinite(v) and v>0 for v in dims):raise ValueError('Invalid door dimensions')
    if op.frame_width_m>=min(op.width_m,op.height_m)/4:raise ValueError('Door frame consumes opening')
    if not math.isfinite(d.portal_gap_m) or d.portal_gap_m<0:raise ValueError('Invalid portal gap')
    if not math.isfinite(d.transom_height_m) or d.transom_height_m<0:raise ValueError('Invalid transom height')
    if not .06<=d.grille_spacing_m<=1.:raise ValueError('Invalid door grille spacing')
    if d.leaf_material not in (*MATERIALS,'auto') or d.frame_material not in (*MATERIALS,'auto'):
        raise ValueError('Invalid door material slot')
    for mat in (d.portal_material,d.metal_material,d.glass_material,d.threshold_material):
        if mat not in MATERIALS:raise ValueError('Invalid door material slot')
    clear,body,transom,leaves,split=layout(op)
    if clear.is_empty or any(p.is_empty or p.bounds[2]-p.bounds[0]<.30 for p in leaves):
        raise ValueError('Door leaf too narrow')
    if body.bounds[3]-body.bounds[1]<1.5:raise ValueError('Door passage too short')
    if d.transom_height_m and (d.transom_height_m<.15 or transom.area<.02):
        raise ValueError('Transom too small')
    if d.opening_angles_deg and len(d.opening_angles_deg)!=len(leaves):
        raise ValueError('Door angle count differs from leaf count')
    if any(not math.isfinite(v) or not 0<=v<=110 for v in d.opening_angles_deg):
        raise ValueError('Invalid door opening angle')


def grille_geometry(shape, pattern, spacing):
    if shape.is_empty:return shape
    x0,y0,x1,y1=shape.bounds
    count=max(1,math.ceil((x1-x0)/spacing))
    if count>128:raise ValueError('Door grille exceeds geometry budget')
    bars=[LineString([(x0+(x1-x0)*i/count,y0),(x0+(x1-x0)*i/count,y1)]).buffer(.009)
          for i in range(1,count)]
    if pattern=='grid':
        for y in np.arange(y0+.25,y1,.30):bars.append(box(x0,y-.009,x1,y+.009))
    if pattern in ('rings','scrolls'):
        pitch=.32
        for x in np.arange(x0+.16,x1-.07,pitch):
            if pattern=='rings':
                r=min(.09,(y1-y0)*.20)
                bars.append(Point(x,y1-min(.17,(y1-y0)/2)).buffer(r,quad_segs=12).boundary.buffer(.009))
            else:
                for sign in (-1,1):
                    pts=[(x+sign*(.02+.075*q/(2*math.pi))*math.cos(q),
                          (y0+y1)/2+min(.23,(y1-y0)*.35)*math.sin(q)) for q in np.linspace(0,2*math.pi,32)]
                    bars.append(LineString(pts).buffer(.01))
    return unary_union(bars).intersection(shape)


def build_door(mb,a,t,n,op):
    validate_door(op)
    d=op.door
    d=replace(d,leaf_material=('metal' if d.model=='moderno' else 'wood') if d.leaf_material=='auto' else d.leaf_material,
              frame_material=('wood' if d.model=='madera' else 'frame') if d.frame_material=='auto' else d.frame_material)
    a,t,n=map(np.asarray,(a,t,n))
    shape=opening_shape(op)
    clear,body,transom,leaves,split=layout(op)
    pattern=d.grille_pattern if d.grille_pattern!='auto' else (
        'scrolls' if d.model=='barroco' else 'rings' if d.model=='republicano' else 'vertical')
    def emit(p,back,front,mat,name,frame=None):
        if p.is_empty:return
        aa,tt,nn=a,t,n
        if frame:
            hinge,angle=frame
            aa=a+t*hinge-n*op.recess_m
            tt=t*math.cos(angle)+n*math.sin(angle)
            nn=-t*math.sin(angle)+n*math.cos(angle)
            p=translate(p,xoff=-hinge)
        polys=[g for g in getattr(p,'geoms',(p,)) if g.geom_type=='Polygon' and g.area>1e-10]
        if polys:mb.panel(aa,tt,nn,polys,back,front,lambda *args:mat,name)
    emit(shape.difference(clear),-op.recess_m,.015,d.frame_material,'door_reveal')
    for (r0,z0),(r1,z1) in zip(PROFILES[d.model],PROFILES[d.model][1:]):
        for i in range(4):
            lo=r0+(r1-r0)*i/4; hi=r0+(r1-r0)*(i+1)/4
            ring=clear.buffer(hi*op.frame_width_m,join_style=2).intersection(shape).difference(
                clear.buffer(lo*op.frame_width_m,join_style=2))
            emit(ring,0,max(.005,(z0+(z1-z0)*(i+.5)/4)*op.frame_depth_m),d.frame_material,'door_moulding')
    if not transom.is_empty:
        emit(clear.intersection(box(op.u_m,split-.025,op.u_m+op.width_m,split+.025)),
             -op.recess_m,.02,d.frame_material,'transom_rail')
        if d.transom_infill=='glass':emit(transom,-op.recess_m-.02,-op.recess_m,d.glass_material,'transom_glass')
        if d.transom_grille:emit(grille_geometry(transom,pattern,d.grille_spacing_m),.02,.045,d.metal_material,'transom_grille')
    construction=DEFAULTS[d.model] if d.construction=='auto' else d.construction
    for i,leaf in enumerate(leaves):
        x0,y0,x1,y1=leaf.bounds
        angle=math.radians(d.opening_angles_deg[i] if d.opening_angles_deg else 0.)
        frame=(x0 if i==0 else x1,angle if i==0 else -angle)
        inside=leaf.buffer(-min(.075,(x1-x0)*.12),join_style=2)
        emit(leaf.difference(inside),-.045,.025,d.leaf_material,'door_leaf_frame',frame)
        if construction in ('glazed','grille'):
            if construction=='glazed':emit(inside,-.025,-.015,d.glass_material,'door_glass',frame)
            if construction=='grille' or d.leaf_grille:
                emit(grille_geometry(inside,pattern,d.grille_spacing_m),.005,.03,d.metal_material,'door_leaf_grille',frame)
        elif construction in ('boards','louvers'):
            vertical=construction=='boards'
            extent=x1-x0 if vertical else y1-y0
            count=max(2,math.ceil(extent/(.16 if vertical else .18)))
            if count>128:raise ValueError('Door infill exceeds geometry budget')
            for j in range(count):
                lo=(x0 if vertical else y0)+extent*j/count
                hi=lo+extent/count-.008
                panel=box(lo,y0,hi,y1) if vertical else box(x0,lo,x1,hi)
                emit(inside.intersection(panel),-.04,.005,d.leaf_material,'door_board' if vertical else 'door_louver',frame)
        else:
            # Taller/wider leaves get more panels rather than oversized motifs.
            cols=max(1,math.ceil((x1-x0)/.8)); rows=max(2,math.ceil((y1-y0)/.95))
            if cols*rows>128:raise ValueError('Door panel count exceeds budget')
            emit(inside,-.045,-.025,d.leaf_material,'door_panel_back',frame)
            for col in range(cols):
                for row in range(rows):
                    panel=box(x0+(x1-x0)*col/cols+.07,y0+(y1-y0)*row/rows+.07,
                              x0+(x1-x0)*(col+1)/cols-.07,y0+(y1-y0)*(row+1)/rows-.07).intersection(inside)
                    emit(panel,-.025,-.005,d.leaf_material,'door_coffer',frame)
                    emit(panel.difference(panel.buffer(-.025,join_style=2)),-.005,.025,d.leaf_material,'door_panel_moulding',frame)
        handle_x=x1-.10 if i==0 else x0+.10
        hz=y0+min(1.05,(y1-y0)*.5)
        emit(box(handle_x-.016,hz-.06,handle_x+.016,hz+(.42 if d.model=='moderno' else .12)),
             .045,.075,d.metal_material,'door_handle',frame)
        for z in (y0+.25,y1-.25):
            hinge_x=x0 if i==0 else x1
            emit(box(hinge_x-.018,z,hinge_x+.018,z+.08),.02,.06,d.metal_material,'door_hinge',frame)
    if d.threshold:
        emit(box(op.u_m,op.v_m-.035,op.u_m+op.width_m,op.v_m),-op.recess_m,.10,d.threshold_material,'door_threshold')
    if d.portal!='none':
        for x in (op.u_m-d.portal_gap_m-d.portal_width_m/2,
                  op.u_m+op.width_m+d.portal_gap_m+d.portal_width_m/2):
            w=d.portal_width_m; bottom=op.v_m; top=op.v_m+op.height_m
            if d.portal=='columns':
                center=a+t*x+n*d.portal_depth_m/2
                for lo,hi,r in ((bottom,bottom+.13,w*.55),(bottom+.13,top-.18,w*.38),
                                (top-.18,top-.09,w*.48),(top-.09,top,w*.56)):
                    mb.solid(Point(center).buffer(r,quad_segs=12),lo,hi,d.portal_material,'door_column')
            else:
                emit(box(x-w/2,bottom,x+w/2,top),0,d.portal_depth_m*.7,d.portal_material,'door_pilaster')
                for z in (bottom,top-.12):emit(box(x-w*.58,z,x+w*.58,z+.12),0,d.portal_depth_m,d.portal_material,'door_capital')
    if d.cornice:
        bounds=portal_domain(op).bounds
        for i in range(3):
            emit(box(bounds[0],op.v_m+op.height_m+i*.06,bounds[2],op.v_m+op.height_m+(i+1)*.06),
                 0,d.portal_depth_m*(.7+i*.15),d.portal_material,'door_portal_cornice')
