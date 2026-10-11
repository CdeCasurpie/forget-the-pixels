"""Facade-local classical templates. Dimensions and materials come from the caller."""
import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.affinity import scale
from dataclasses import replace
from .prefabs import sign_letters


def _panel(mb, a, t, n, shape, back, front, material, semantic):
    mb.panel(a, t, n, [shape], back, front, lambda *args: material, semantic, clip='envelope')


def moulded_surround(mb, a, t, n, feature):
    """Three nested, hollow mouldings; never place a panel across the aperture."""
    u, v, w, h = feature.u_m, feature.v_m, feature.width_m, feature.height_m
    border = min(feature.border_width_m, w / 5, h / 5)
    inner = box(u + border, v + border, u + w - border, v + h - border)
    if feature.kind == 'segmental_surround':
        left, bottom, right, top = inner.bounds
        rise = feature.arch_rise_m if feature.arch_rise_m is not None else min((right-left)*.28, (top-bottom)*.25, .9)
        if not np.isfinite(rise) or not 0 < rise < top-bottom:
            raise ValueError('Invalid surround arch rise')
        arc = [(u+w/2+(right-left)/2*np.cos(angle), top-rise+rise*np.sin(angle))
               for angle in np.linspace(0, np.pi, 25)]
        inner = Polygon([(left,bottom),(right,bottom),*arc])
    for i in range(3):
        low, high = border*i/3, border*(i+1)/3
        ring = inner.buffer(high, join_style=2).difference(inner.buffer(low, join_style=2))
        _panel(mb,a,t,n,ring,-.015,feature.depth_m*(.5+.25*i),
               feature.material_slot,'surround_moulding')
    if feature.kind == 'segmental_surround':
        cx, top = u+w/2, v+h-border
        key = Polygon([(cx-border*.4,top-.03),(cx+border*.4,top-.03),
                       (cx+border*.7,top+border),(cx-border*.7,top+border)])
        _panel(mb,a,t,n,key,feature.depth_m*.6,feature.depth_m+.045,
               feature.material_slot,'surround_keystone')


def classical_pilaster(mb, a, t, n, feature):
    """Fluted shaft, moulded base, echinus/abacus and optional composite capital."""
    u, z, w, h, d = (feature.u_m,feature.v_m,feature.width_m,
                      feature.height_m,feature.depth_m)
    mat = feature.material_slot
    composite = feature.kind == 'composite_pilaster'
    base, cap = min(.48,h*.12), min(.55 if composite else .32,h*.14)
    # Recessed longitudinal flutes, cut in the shaft cross-section.
    section = box(u,-.02,u+w,d*.8)
    radius = w/18
    for x in np.linspace(u+w*.18,u+w*.82,5):
        section = section.difference(Point(x,d*.81).buffer(radius,quad_segs=4))
    for poly in [section] if section.geom_type=='Polygon' else section.geoms:
        footprint = Polygon([np.asarray(a)+t*x+n*y for x,y in poly.exterior.coords])
        mb.solid(footprint,z+base,z+h-cap,mat,'pilaster_fluted_shaft',clip='envelope')
    for start, height, widths, semantic in (
        (z,base,(1.0,.88,.96,.82),'pilaster_moulded_base'),
        (z+h-cap,cap,(.85,1.0,1.13,1.0),'pilaster_moulded_capital')):
        for i,scale in enumerate(widths):
            half = w*scale/2
            mb.box(a,t,n,u+w/2-half,u+w/2+half,start+height*i/4,
                   start+height*(i+1)/4,-.02,d*(.8+.2*scale),mat,semantic,clip='envelope')
    if composite:
        for cx in (u+w*.16,u+w*.84):
            r = w*.20
            angles = np.linspace(0,2.6*np.pi,24)
            curve = [(cx+r*(1-i/(len(angles)*1.12))*np.cos(angle),
                      z+h-cap*.5+r*(1-i/(len(angles)*1.12))*np.sin(angle))
                     for i,angle in enumerate(angles)]
            _panel(mb,a,t,n,LineString(curve).buffer(w*.027,quad_segs=2),d,d+.065,mat,'capital_volute')
        for cx in (u+w*.28,u+w*.5,u+w*.72):
            leaf=Polygon([(cx-w*.09,z+h-cap),(cx-w*.10,z+h-cap*.55),
                          (cx,z+h-cap*.25),(cx+w*.10,z+h-cap*.55)])
            _panel(mb,a,t,n,leaf,d*.85,d+.04,mat,'capital_leaf')


def classical_cornice(mb,a,t,n,feature):
    """Projected corona above separated dentils and modestly spaced brackets."""
    u,z,w,h,d=feature.u_m,feature.v_m,feature.width_m,feature.height_m,feature.depth_m
    mat=feature.material_slot
    for lo,hi,depth in ((0,.12,.36),(.12,.23,.5),(.62,.76,.83),(.76,.92,1.),(.92,1.,.92)):
        mb.box(a,t,n,u,u+w,z+h*lo,z+h*hi,-.02,d*depth,mat,'classical_cornice_course',clip='envelope')
    count=max(1,int(w/.22));pitch=w/count
    for i in range(count):
        x=u+(i+.5)*pitch
        mb.box(a,t,n,x-pitch*.22,x+pitch*.22,z+h*.23,z+h*.46,
               -.01,d*.68,mat,'classical_dentil',clip='envelope')
    count=max(1,int(w/.85));pitch=w/count
    for i in range(count):
        x=u+(i+.5)*pitch;half=min(.10,pitch*.18)
        mb.box(a,t,n,x-half,x+half,z+h*.43,z+h*.64,
               -.01,d*.86,mat,'classical_modillion',clip='envelope')


def turned_baluster(mb,a,t,n,u,z,width,height,depth,material='frame'):
    """Extruded turned silhouette, with neck, belly and foot."""
    profile=((0,.48),(.10,.48),(.14,.28),(.27,.20),(.40,.42),(.54,.48),
             (.68,.30),(.80,.15),(.90,.20),(1.,.40))
    points=[(u+width*r,z+height*v) for v,r in profile]
    points += [(u-width*r,z+height*v) for v,r in reversed(profile)]
    _panel(mb,a,t,n,Polygon(points),depth-width*.35,depth+width*.35,
           material,'turned_baluster')


def oval_sign(mb,a,t,n,feature):
    cx,cz=feature.u_m+feature.width_m/2,feature.v_m+feature.height_m/2
    oval=scale(Point(cx,cz).buffer(1,quad_segs=16),feature.width_m/2,
               feature.height_m/2,origin=(cx,cz))
    _panel(mb,a,t,n,oval,-.015,feature.depth_m,'sign','oval_sign')
    _panel(mb,a,t,n,oval.difference(oval.buffer(-.065)),feature.depth_m,
           feature.depth_m+.035,feature.material_slot,'sign_rim')
    sign_letters(mb,a,t,n,replace(feature,u_m=feature.u_m+feature.width_m*.10,
                                 width_m=feature.width_m*.80))
