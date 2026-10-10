"""Canonical theta-candidate composer in a local facade chart.

Consumes completed FacadeControls. No context, massing, exposure or world
coordinates belong here. Both base walls and FacadeZone use this entry point.
The legacy composer remains separate; shared family relief is reused unchanged.
"""
from dataclasses import dataclass, replace
import math
from typing import NamedTuple

import numpy as np
from shapely.geometry import box as rect

from domain.models import Opening, FacadeProjection, FacadeMaterialRegion
from domain.theta import FacadeControls
from modeling.detail import DetailBudget
from modeling.facade_program import FAMILY_RULES, compose_relief


class FacadeComposition(NamedTuple):
    axes_m: tuple[float, ...]
    openings: tuple[Opening, ...]
    projections: tuple[FacadeProjection, ...]
    material_regions: tuple[FacadeMaterialRegion, ...]


def _check(condition, message):
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True)
class ResolvedBay:
    axis_m: float
    pitch_m: float
    start_m: float
    end_m: float
    group_index: int
    local_index: int
    global_index: int
    ground_role: str
    role: str | None


def validate_bay_groups(c):
    """Validate even inactive/hidden controls, before metric composition."""
    if not c.bay_groups:return
    _check(c.mode=='repeat','bay_groups require repeat mode')
    _check(c.bay_count is None and c.bay_axes_m is None,
           'bay_groups conflict with global bay_count/bay_axes_m')
    previous=0.
    for group in c.bay_groups:
        lo,hi=group.u
        _check(math.isfinite(lo) and math.isfinite(hi) and 0<=lo<hi<=1,'Invalid BayGroup u interval')
        _check(lo>=previous,'BayGroups must be ordered without overlap')
        _check(type(group.count) is int and group.count>=1,'BayGroup count must be a positive integer')
        _check(group.ground_role in ('inherit','entrance','garage','shopfront','blind'),'Invalid BayGroup ground_role')
        _check(group.ground_role not in ('entrance','garage') or group.count==1,
               'BayGroup entrance/garage requires count=1')
        previous=hi


def resolve_bay_layout(c, length):
    """Retain group membership and pitch; canonical indices flatten left->right."""
    validate_bay_groups(c)
    bays=[]
    for gi,group in enumerate(c.bay_groups):
        start,end=(length*u for u in group.u)
        pitch=(end-start-.64)/group.count
        _check(pitch>0,'BayGroup too narrow for its margins')
        for i in range(group.count):
            axis=start+.32+(i+.5)*pitch
            _check(start<axis<end,'BayGroup axis outside group')
            bays.append(ResolvedBay(axis,pitch,start,end,gi,i,len(bays),group.ground_role,group.role))
    return tuple(bays)


def _compose_grouped(c, family, length, levels, height, ground, top, floor_indices):
    bays=resolve_bay_layout(c,length)
    rules=FAMILY_RULES[family]
    edits={(e.floor,e.bay):e for e in c.opening_edits}
    found=set()
    ops=[]
    def append(op,bay):
        _check(op.u_m>=bay.start_m+.12 and op.u_m+op.width_m<=bay.end_m-.12+1e-8,
               'Opening outside its BayGroup')
        _check(op.width_m>0 and op.height_m>0 and op.v_m>=0 and op.v_m+op.height_m<=height-.1,
               'Opening edit/add outside facade')
        shape=rect(op.u_m,op.v_m,op.u_m+op.width_m,op.v_m+op.height_m)
        _check(all(shape.intersection(rect(x.u_m,x.v_m,x.u_m+x.width_m,x.v_m+x.height_m)).area<1e-8 for x in ops),
               'Opening edit/add overlaps another opening')
        ops.append(op)
    for local_floor,(z0,z1) in enumerate(zip(levels,levels[1:])):
        floor=local_floor if floor_indices is None else floor_indices[local_floor]
        for bay in bays:
            key=(floor,bay.global_index)
            found.add(key)
            edit=edits.get(key)
            if edit is not None:
                if edit.action=='replace':append(edit.opening,bay)
                continue
            kind,prefab='window',rules['prefab']
            width,sill,h=bay.pitch_m*c.window_ratio,c.sill_m,c.window_height_m
            if ground and local_floor==0:
                role=bay.ground_role
                if role=='blind':continue
                if role in ('entrance','garage'):
                    kind,prefab=('door','wood_panel') if role=='entrance' else ('gate','roller')
                    # Explicit entry groups use their own available width,
                    # without the legacy first-door cap of 1.2 metres.
                    width,sill,h=bay.pitch_m*.75,.04,min(max(c.window_height_m,2.3),z1-z0-.3)
                elif role=='shopfront' or role=='inherit' and rules['ground']=='shopfront':
                    prefab,sill='storefront',.15
            if floor>0 and c.balconies and bay.global_index%2==0:
                kind,sill='balcony_window',.18
            h=min(h,z1-z0-sill-.2)
            _check(h>=.5 and width>=.4,'Openings cannot fit in BayGroup: reduce count or dimensions')
            append(Opening(kind,bay.axis_m-width/2,z0+sill,width,h,prefab=prefab,
                           grille=rules['grille'],balcony_depth_m=c.balcony_depth_m or .75,curtain=0),bay)
    _check(set(edits)<=found,'Sparse edit targets nonexistent floor/bay')
    for op in c.added_openings:
        owners=[b for b in bays if b.start_m<=op.u_m and op.u_m+op.width_m<=b.end_m]
        _check(bool(owners),'Added opening outside BayGroups (gaps are blind)')
        append(op,owners[0])
    return _finish(c,rules,length,levels,height,ground,top,tuple(b.axis_m for b in bays),ops)


def _finish(c, rules, length, levels, height, ground, top, axes, ops):
    # All groups have been joined. Global relief runs exactly once; balconies
    # and shutters consume each opening's actual dimensions, not a global pitch.
    projections,regions=compose_relief(length,levels,ops,rules,height,ground,top,
                                       np.random.default_rng(0),[],DetailBudget(2))
    projections=tuple(replace(x,depth_m=c.gallery_depth_m) if x.kind=='gallery' else
                      replace(x,depth_m=c.awning_depth_m) if x.kind=='awning' else x for x in projections)
    ops=tuple(replace(x,kind='window') if x.kind=='balcony_window' else x for x in ops)
    return FacadeComposition(axes,ops,projections if c.projections is None else c.projections,
                             tuple(regions) if c.material_regions is None else c.material_regions)


def compose_facade(c: FacadeControls, family, length, levels, height, ground, top,
                   floor_indices=None) -> FacadeComposition:
    """Compose local metric entities; floor_indices preserves component floors.

    Controls must already be completed/validated by the resolver. Visibility
    must be applied after composition, never by shortening this input chart.
    """
    if c.bay_groups:
        return _compose_grouped(c,family,length,levels,height,ground,top,floor_indices)
    if c.mode == "explicit":
        return FacadeComposition((), c.openings, c.projections or (), c.material_regions or ())
    rules = dict(FAMILY_RULES[family])
    count = c.bay_count or max(1, round((length-.64)/3.1))
    axes = c.bay_axes_m if c.bay_axes_m is not None else tuple(.32+(i+.5)*(length-.64)/count for i in range(count))
    _check(bool(axes) and tuple(sorted(set(axes))) == axes and axes[0] > .4 and axes[-1] < length-.4, "Invalid bay axes")
    pitch = min([length-.64] + [b-a for a,b in zip(axes, axes[1:])] + [2*(axes[0]-.32), 2*(length-.32-axes[-1])])
    ops = []
    found=set()
    edits={(e.floor,e.bay):e for e in c.opening_edits}
    for local_floor, (z0,z1) in enumerate(zip(levels, levels[1:])):
        floor=local_floor if floor_indices is None else floor_indices[local_floor]
        for i, axis in enumerate(axes):
            kind, prefab = "window", rules["prefab"]
            width, sill, h = pitch*c.window_ratio, c.sill_m, c.window_height_m
            if ground and local_floor == 0 and i == 0:
                kind = "gate" if rules["ground"] == "garage" else "door"
                prefab = "roller" if kind == "gate" else "wood_panel"
                width, sill, h = min(pitch*.75, 3.2) if kind == "gate" else min(pitch*.42, 1.2), .04, min(2.3,z1-z0-.3)
            elif ground and local_floor == 0 and rules["ground"] == "shopfront":
                prefab, sill = "storefront", .15
            if floor > 0 and c.balconies and i % 2 == 0:
                kind, sill = "balcony_window", .18
            h = min(h, z1-z0-sill-.2)
            _check(h >= .5 and width >= .4, "Openings cannot fit: reduce bays or window dimensions")
            opening=Opening(kind, axis-width/2, z0+sill, width,h,
                               prefab=prefab, grille=rules["grille"],
                               balcony_depth_m=c.balcony_depth_m or .75, curtain=0)
            key=(floor,i)
            found.add(key)
            edit=edits.get(key)
            if edit is None:
                ops.append(opening)
            elif edit.action=="replace":
                ops.append(edit.opening)
    _check(set(edits)<=found,"Sparse edit targets nonexistent floor/bay")
    ops.extend(c.added_openings)
    rectangles=[]
    for op in ops:
        _check(op.u_m>=.12 and op.v_m>=0 and op.width_m>0 and op.height_m>0 and
               op.u_m+op.width_m<=length-.12 and op.v_m+op.height_m<=height-.1,
               "Opening edit/add outside facade")
        shape=rect(op.u_m,op.v_m,op.u_m+op.width_m,op.v_m+op.height_m)
        _check(all(shape.intersection(other).area<1e-8 for other in rectangles),"Opening edit/add overlaps another opening")
        rectangles.append(shape)
    # Family relief is reused; its two random depths are always overwritten by
    # resolved architectural controls. This RNG never sees xi.
    projections, regions = compose_relief(length, levels, ops, rules, height,
                                  ground, top, np.random.default_rng(0), [], DetailBudget(2))
    projections = tuple(replace(x, depth_m=c.gallery_depth_m) if x.kind == "gallery" else
                        replace(x, depth_m=c.awning_depth_m) if x.kind == "awning" else x for x in projections)
    ops = tuple(replace(x, kind="window") if x.kind == "balcony_window" else x for x in ops)
    return FacadeComposition(axes, ops, projections if c.projections is None else c.projections,
                             tuple(regions) if c.material_regions is None else c.material_regions)
