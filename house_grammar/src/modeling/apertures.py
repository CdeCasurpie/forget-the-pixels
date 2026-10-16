"""True curved apertures and open/perforated infills using existing panels."""
import numpy as np
from shapely.geometry import Polygon, box
from shapely.ops import unary_union


def opening_shape(op):
    u,v,w,h=op.u_m,op.v_m,op.width_m,op.height_m
    if op.shape=='rectangle':
        if op.arch_rise_m is not None:raise ValueError('arch_rise_m inactive')
        return box(u,v,u+w,v+h)
    if op.shape in ('circle','ellipse'):
        if op.arch_rise_m is not None:raise ValueError('arch_rise_m inactive')
        if op.shape=='circle' and abs(w-h)>1e-7:raise ValueError('Circle requires equal width and height')
        return Polygon([(u+w/2+w/2*np.cos(q),v+h/2+h/2*np.sin(q))
                        for q in np.linspace(0,2*np.pi,97)[:-1]])
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
    raise ValueError('Legacy shaped opening emitter removed; use modeling.opening_catalog.build_opening')
