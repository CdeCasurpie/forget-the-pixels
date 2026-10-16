"""Contour-linked window assembly. Profiles are swept as nested offset bands.

The same aperture defines the wall cutout, reveal, moulding and clipped infill.
Profile samples encode radial offset fraction and outward depth fraction.
"""
import math
import numpy as np
from shapely.geometry import box, LineString
from shapely.ops import unary_union
from modeling.apertures import opening_shape

PROFILES = {
    'moderno': ((0.,.12),(.8,.12),(1.,.08)),
    'clasico': ((0.,.25),(.25,.25),(.26,.65),(.7,.65),(.71,1.),(1.,1.)),
    'republicano': ((0.,.25),(.18,.35),(.32,.7),(.48,.85),(.55,.65),(.75,.65),(.8,1.),(1.,1.)),
    'barroco': tuple((i/24,.48+.32*math.sin(i/24*3*math.pi)+.18*i/24) for i in range(25)),
    'madera': ((0.,.25),(.25,.25),(.26,.6),(.72,.6),(.73,.95),(1.,.95)),
}


def validate_window(op):
    if op.frame_profile not in PROFILES:raise ValueError('Unknown or unresolved window frame profile')
    if op.kind not in ('window','balcony_window') or op.prefab not in ('catalog','legacy','slim_window','storefront','open'):
        raise ValueError('Linked window supports window glass/open infill only')
    if not all(math.isfinite(x) and x>0 for x in
               (op.width_m,op.height_m,op.frame_width_m,op.frame_depth_m,op.recess_m,op.grille_spacing_m)):
        raise ValueError('Invalid window dimensions')
    if op.frame_width_m >= min(op.width_m,op.height_m)/3:
        raise ValueError('Window frame consumes aperture')
    if op.grid_spacing_m is not None and (not math.isfinite(op.grid_spacing_m) or op.grid_spacing_m<.08):
        raise ValueError('Invalid adaptive grid spacing')
    if op.grille_spacing_m<.06:raise ValueError('Grille spacing too small')
    if not 1<=op.mullion_columns<=64 or not 1<=op.mullion_rows<=64:
        raise ValueError('Invalid window grid count')
    if op.grille_pattern not in ('vertical','grid','diamond'):raise ValueError('Invalid grille pattern')
    opening_shape(op)


def interior(op):
    return opening_shape(op).buffer(-op.frame_width_m,join_style=2)


def grid_geometry(op, security=False):
    """Return bars clipped to the clear opening, also used by geometry tests."""
    inside=interior(op)
    x0,y0,x1,y1=inside.bounds
    spacing=op.grille_spacing_m if security else op.grid_spacing_m
    cols=max(1,math.ceil((x1-x0)/spacing)) if spacing else op.mullion_columns
    rows=max(1,math.ceil((y1-y0)/spacing)) if spacing else op.mullion_rows
    if max(cols,rows)>256:raise ValueError('Window grid exceeds geometry budget')
    width=.018 if security else .028
    bars=[]
    if security and op.grille_pattern=='diamond':
        extent=(x1-x0)+(y1-y0)
        for delta in np.arange(-extent,extent+spacing,spacing):
            for sign in (-1,1):
                bars.append(LineString([(x0+delta,y0),(x0+delta+sign*(y1-y0),y1)]).buffer(width/2))
    else:
        for i in range(1,cols):
            x=x0+(x1-x0)*i/cols
            bars.append(box(x-width/2,y0,x+width/2,y1))
        if not security or op.grille_pattern=='grid':
            for i in range(1,rows):
                y=y0+(y1-y0)*i/rows
                bars.append(box(x0,y-width/2,x1,y+width/2))
    return unary_union(bars).intersection(inside)


def build_window(mb,a,t,n,op):
    validate_window(op)
    shape=opening_shape(op)
    clear=interior(op)
    material='wood' if op.frame_profile=='madera' else 'frame'
    def emit(geom,back,front,mat,name):
        if not geom.is_empty:
            parts=list(geom.geoms) if geom.geom_type=='MultiPolygon' else [geom]
            mb.panel(a,t,n,parts,back,front,lambda *args:mat,name)
    emit(shape.difference(clear),-op.recess_m,.012,material,'window_reveal')
    # Sweep the section around the aperture using narrow constant-depth bands.
    # All rings stay inside the aperture; no independent rectangular surround.
    samples=PROFILES[op.frame_profile]
    for (r0,d0),(r1,d1) in zip(samples,samples[1:]):
        for fraction in range(4):
            lo=r0+(r1-r0)*fraction/4
            hi=r0+(r1-r0)*(fraction+1)/4
            depth=(d0+(d1-d0)*(fraction+.5)/4)*op.frame_depth_m
            outer=clear.buffer(hi*op.frame_width_m,join_style=2).intersection(shape)
            inner=clear.buffer(lo*op.frame_width_m,join_style=2)
            emit(outer.difference(inner),0.,max(.005,depth),material,'window_profile')
    if op.prefab!='open':
        emit(clear,-op.recess_m-.02,-op.recess_m,'glass','window_glass')
        emit(grid_geometry(op),-op.recess_m,-op.recess_m+.035,material,'window_mullion')
    if op.grille:
        emit(grid_geometry(op,True),.015,.045,'metal','window_grille')
    if op.sill:
        # Sill follows the lower contour, including circular/elliptic windows.
        lower=shape.intersection(box(op.u_m-1,op.v_m-1,op.u_m+op.width_m+1,
                                    op.v_m+min(.12,op.height_m*.12)))
        emit(lower.difference(clear),-.02,op.frame_depth_m+.12,material,'window_sill')
