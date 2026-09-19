"""Coherent facade accents derived from existing bays; no image inference."""

from dataclasses import replace
import numpy as np
from shapely.geometry import Polygon
from domain.models import FacadeMaterialRegion, FacadeProjection


def compose_facade(facade, parcel, style):
    """Reserve space for accents and emit complete features only when they fit."""
    if not facade.is_front or not facade.openings:
        return facade
    levels = facade.floor_levels_m
    width = facade.width_m
    if len(levels) < 3 or width < 3:
        return facade
    a = np.asarray(facade.vertex_a)
    t = (np.asarray(facade.vertex_b) - a) / width
    n = np.array([t[1], -t[0]])
    regions, features = [], []

    def add(kind, u, v, w, h, depth, material="accent", border=.12):
        if min(w, h, depth) <= 0 or u < 0 or u + w > width:
            return
        envelope = Polygon([a + t*x + n*d for x, d in
                            [(u, 0), (u+w, 0), (u+w, depth), (u, depth)]])
        if parcel.covers(envelope):
            features.append(FacadeProjection(
                kind, u, v, w, h, depth, material, border,
                source="procedural_composition"))

    upper = [o for o in facade.openings if o.v_m >= levels[1]]
    if not upper:
        return facade
    # One coherent focal zone over several storeys, aligned to actual openings.
    columns = sorted(set(round(o.u_m, 6) for o in upper))
    selected = columns[:max(1, (len(columns)+1)//2)]
    group = [o for o in upper if round(o.u_m, 6) in selected]
    left = max(.16, min(o.u_m for o in group) - .22)
    right = min(width-.16, max(o.u_m+o.width_m for o in group) + .22)
    bottom = max(levels[1]+.12, min(o.v_m for o in group)-.25)
    top = min(levels[-1]-.18, max(o.v_m+o.height_m for o in group)+.25)
    regions.append(FacadeMaterialRegion(
        left, bottom, right-left, top-bottom, "accent",
        source="procedural_composition"))
    # Frame remains outside the openings instead of covering their glazing.
    if all(o.kind != "balcony_window" for o in group):
        add("frame", left, bottom, right-left, top-bottom, .15, border=.10)
    for op in facade.openings:
        if op.kind in ("door", "gate"):
            add("canopy", max(.12, op.u_m-.16), op.v_m+op.height_m+.12,
                min(op.width_m+.32, width-.24), .10, .28, "stone")
        elif op.kind == "window":
            # Repeated sunshades unify the upper floors; base remains distinct.
            if op.v_m >= levels[1]:
                kind = "curved_canopy" if style == "narrow" else "ledge"
                add(kind, op.u_m-.08, op.v_m+op.height_m+.10,
                    op.width_m+.16, .08, .18, "stone")
    return replace(facade, material_regions=tuple(regions),
                   projections=tuple(features))
