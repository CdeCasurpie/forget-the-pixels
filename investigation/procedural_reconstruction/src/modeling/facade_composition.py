"""Canonical theta-candidate composer in a local facade chart.

Consumes completed FacadeControls. No context, massing, exposure or world
coordinates belong here. Both base walls and FacadeZone use this entry point.
The legacy composer remains separate; shared family relief is reused unchanged.
"""
from dataclasses import replace
from typing import NamedTuple

import numpy as np
from shapely.geometry import box as rect

from domain.models import Opening, FacadeProjection, FacadeMaterialRegion
from domain.theta import FacadeControls
from modeling.detail import DetailBudget
from modeling.facade_program import FAMILY_RULES, _relief


class FacadeComposition(NamedTuple):
    axes_m: tuple[float, ...]
    openings: tuple[Opening, ...]
    projections: tuple[FacadeProjection, ...]
    material_regions: tuple[FacadeMaterialRegion, ...]


def _check(condition, message):
    if not condition:
        raise ValueError(message)


def compose_facade(c: FacadeControls, family, length, levels, height, ground, top,
                   floor_indices=None) -> FacadeComposition:
    """Compose local metric entities; floor_indices preserves component floors.

    Controls must already be completed/validated by the resolver. Visibility
    must be applied after composition, never by shortening this input chart.
    """
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
    projections, regions = _relief(length, levels, axes, pitch, ops, rules, height,
                                  ground, top, np.random.default_rng(0), [], DetailBudget(2))
    projections = tuple(replace(x, depth_m=c.gallery_depth_m) if x.kind == "gallery" else
                        replace(x, depth_m=c.awning_depth_m) if x.kind == "awning" else x for x in projections)
    ops = tuple(replace(x, kind="window") if x.kind == "balcony_window" else x for x in ops)
    return FacadeComposition(axes, ops, projections if c.projections is None else c.projections,
                             tuple(regions) if c.material_regions is None else c.material_regions)
