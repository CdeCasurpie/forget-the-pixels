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


def arch_components(u, v, w, h, rise, frame_f=0.07, impost_z=None):
    """Return (ring_poly, keystone_poly, impost_polys) for a round arch.

    * ring — the full arch profile (jamb-to-jamb + semicircle)
    * keystone — the central voussoir, exaggerated ~25% taller
    * impost_polys — horizontal bands at the springing line on each side
    """
    cx, top = u + w / 2, v + h
    arc_pts = [(cx + (w / 2) * np.cos(t), top - rise + rise * np.sin(t))
               for t in np.linspace(0, np.pi, 25)]
    ring = Polygon([(u, v), (u + w, v), *arc_pts])
    inner = ring.buffer(-frame_f, join_style=2)
    ring = ring.difference(inner)

    # Compact central block contained within the frame at the apex.
    kw = min(w * 0.08, frame_f * 1.2)
    kh = min(rise * 0.30, frame_f)
    keystone = box(cx - kw, top - kh, cx + kw, top)

    iz = impost_z if impost_z is not None else top - rise
    ih = min(rise * 0.12, frame_f)
    imp_l = box(u, iz, u + frame_f, iz + ih)
    imp_r = box(u + w - frame_f, iz, u + w, iz + ih)
    return ring, keystone, [imp_l, imp_r]


def shaped_opening(mb,a,t,n,op):
    shape=opening_shape(op)
    inside=shape.buffer(-min(op.frame_width_m,op.width_m/5),join_style=2)
    def panel(p,back,front,mat,semantic):
        mb.panel(a,t,n,[p],back,front,lambda *args:mat,semantic)
    panel(shape.difference(inside),-op.recess_m,.035,'frame','arched_frame' if op.shape=='arch' else 'window_frame')
    if op.shape == 'arch':
        u, v, w, h = op.u_m, op.v_m, op.width_m, op.height_m
        rise = op.arch_rise_m if op.arch_rise_m is not None else min(w / 2, h / 2)
        ring_poly, keystone, imp_polys = arch_components(u, v, w, h, rise,
                                                       min(op.frame_width_m, w/5))
        panel(keystone, -op.recess_m + 0.008, 0.043,
              'stone', 'keystone')
        for imp in imp_polys:
            panel(imp, -op.recess_m, 0.038,
                  'stone', 'impost_band')
        # Radial voussoir lines for a stone-blocked arch
        cx, top = u + w / 2, v + h
        n_blocks = 7
        for i in range(n_blocks):
            angle = np.pi * (i + 0.5) / n_blocks
            ex = cx + (w / 2) * np.cos(angle)
            ez = top - rise + rise * np.sin(angle)
            mb.beam((*(np.asarray(a) + t * ex + n * (-op.recess_m)), ez),
                    (*(np.asarray(a) + t * ex + n * 0.038), ez),
                    0.012, material='stone', semantic='voussoir_joint')
    if op.prefab=='screen':
        perforations=[]; pitch=.3; bar=.06
        for u in np.arange(op.u_m,op.u_m+op.width_m,pitch):
            for v in np.arange(op.v_m,op.v_m+op.height_m,pitch):
                perforations.append(box(u+bar,v+bar,u+pitch-bar,v+pitch-bar))
        panel(inside.difference(unary_union(perforations)),-op.recess_m,0.,'stone','perforated_screen')
    elif op.prefab=='open' and op.style=='vestibule':
        panel(inside,-op.recess_m-.82,-op.recess_m-.80,'interior','interior_backing')
    elif op.prefab!='open':
        mat='wood' if op.kind in ('door','gate') else 'glass'
        if op.prefab=='metal_gate':mat='metal'
        panel(inside,-op.recess_m-.025,-op.recess_m,mat,op.kind+'_panel')
    if op.grille:
        bars=[]
        for u in np.arange(op.u_m+.1,op.u_m+op.width_m-.05,.14):
            bars.append(box(u,op.v_m,u+.022,op.v_m+op.height_m))
        panel(unary_union(bars).intersection(inside),.05,.08,'metal','security_bar')
