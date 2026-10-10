"""Continuous facade silhouette, apertures and mouldings in one (u,z) chart.

The profile extends the actual wall, rather than stacking a decorative crown
over a horizontal lintel. No mass, storey or world-space footprint is added.
"""
import math
from shapely.geometry import Polygon, LineString, box
from shapely.ops import unary_union
from domain.models import ResolvedTopProfile
from modeling.mesh_builder import polygons


def validate_top_profile(profile):
    if profile is None:return
    pts=profile.points
    if not 2<=len(pts)<=64 or not all(math.isfinite(v) for p in pts for v in p):
        raise ValueError('Top profile needs 2..64 finite (u,rise) points')
    if pts[0][0]!=0 or pts[-1][0]!=1 or not all(0<=u<=1 and 0<=z<=4 for u,z in pts):
        raise ValueError('Top profile spans u=0..1, rise=0..4 m')
    if any(b[0]<a[0] or a==b for a,b in zip(pts,pts[1:])):
        raise ValueError('Top profile must progress left to right without repeated points')
    shape=Polygon([(0.,-1.),*pts,(1.,-1.)])
    if not shape.is_valid or not LineString(pts).is_simple:
        raise ValueError('Self-intersecting top profile')
    if not (.12<=profile.depth_m<=.8 and 0<=profile.trim_width_m<=.5 and
            .02<=profile.trim_depth_m<=.4):
        raise ValueError('Invalid top profile depth/trim dimensions')


def resolve_top_profile(profile,width,height,start=0.,low=0.):
    if profile is None:return None
    validate_top_profile(profile)
    return ResolvedTopProfile(tuple((start+u*width,low+height+z) for u,z in profile.points),
        low+height,profile.depth_m,profile.trim_width_m,profile.trim_depth_m,profile.trim_material_slot)


def wall_domain(length,height,profile=None):
    base=box(0.,0.,length,height)
    if profile is None:return base
    # Include a small overlap below the base so zero-rise segments are valid.
    pts=profile.points_m
    upper=Polygon([(pts[0][0],profile.base_z_m-.01),*pts,(pts[-1][0],profile.base_z_m-.01)])
    return base.union(upper)


def visible_profile_domains(domains,profile):
    """Extend only intervals reaching the original top; occluders do not reflow."""
    upper=max(z for _,z in profile.points_m)
    return tuple(domains)+tuple((u0,z1,u1,upper) for u0,z0,u1,z1 in domains
        if abs(z1-profile.base_z_m)<1e-7 and upper>z1)


def emit_top_trim(mb,a,t,n,profile):
    if not profile.trim_width_m:return
    pts=profile.points_m
    # Trim follows the top edge, including slopes and sampled arcs. Both
    # layers have real depth and a common continuous silhouette.
    below=Polygon([(pts[0][0],profile.base_z_m-5),*pts,(pts[-1][0],profile.base_z_m-5)])
    path=LineString(pts)
    for width,depth,name in ((profile.trim_width_m,profile.trim_depth_m,'top_profile_moulding'),
                             (profile.trim_width_m*.28,profile.trim_depth_m+.045,'top_profile_lip')):
        band=path.buffer(width,cap_style=2,join_style=2).intersection(below)
        mb.panel(a,t,n,polygons(band),-.015,depth,
                 lambda *args:profile.trim_material_slot,name,clip='envelope')


def roof_aperture_clearance(facade,roof_z):
    """Remove roof slab in the reveals of openings crossing its elevation."""
    import numpy as np
    a=np.asarray(facade.vertex_a);t=(np.asarray(facade.vertex_b)-a)/facade.width_m
    n=np.asarray(facade.normal_xy)
    cuts=[]
    for op in facade.openings:
        if op.v_m<roof_z<op.v_m+op.height_m:
            lo,hi=op.u_m-.03,op.u_m+op.width_m+.03
            depth=max(op.recess_m+.22,facade.top_profile.depth_m)
            cuts.append(Polygon([a+t*u+n*w for u,w in ((lo,.01),(hi,.01),(hi,-depth),(lo,-depth))]))
    return unary_union(cuts)
