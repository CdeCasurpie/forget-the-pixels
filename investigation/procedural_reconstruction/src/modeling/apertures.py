"""True curved apertures and open/perforated infills using existing panels."""
import numpy as np
from shapely.geometry import Polygon, box
from shapely.ops import unary_union


def opening_shape(op):
    u,v,w,h=op.u_m,op.v_m,op.width_m,op.height_m
    if op.shape=='rectangle':
        if op.arch_rise_m is not None:raise ValueError('arch_rise_m inactive')
        return box(u,v,u+w,v+h)
    if op.shape!='arch':raise ValueError('Unknown opening shape')
    rise=op.arch_rise_m if op.arch_rise_m is not None else min(w/2,h/2)
    if not 0<rise<h:raise ValueError('Invalid arch rise')
    arc=[(u+w/2+w/2*np.cos(t),v+h-rise+rise*np.sin(t)) for t in np.linspace(0,np.pi,25)]
    return Polygon([(u,v),(u+w,v),*arc])


def shaped_opening(mb,a,t,n,op):
    shape=opening_shape(op)
    inside=shape.buffer(-min(op.frame_width_m,op.width_m/5),join_style=2)
    def panel(p,back,front,mat,semantic):
        mb.panel(a,t,n,[p],back,front,lambda *args:mat,semantic)
    panel(shape.difference(inside),-op.recess_m,.035,'frame','arched_frame' if op.shape=='arch' else 'window_frame')
    if op.prefab=='screen':
        perforations=[]; pitch=.3; bar=.06
        for u in np.arange(op.u_m,op.u_m+op.width_m,pitch):
            for v in np.arange(op.v_m,op.v_m+op.height_m,pitch):
                perforations.append(box(u+bar,v+bar,u+pitch-bar,v+pitch-bar))
        panel(inside.difference(unary_union(perforations)),-op.recess_m,0.,'stone','perforated_screen')
    elif op.prefab!='open':
        mat='wood' if op.kind in ('door','gate') else 'glass'
        if op.prefab=='metal_gate':mat='metal'
        panel(inside,-op.recess_m-.025,-op.recess_m,mat,op.kind+'_panel')
    if op.grille:
        bars=[]
        for u in np.arange(op.u_m+.1,op.u_m+op.width_m-.05,.14):
            bars.append(box(u,op.v_m,u+.022,op.v_m+op.height_m))
        panel(unary_union(bars).intersection(inside),.05,.08,'metal','security_bar')
