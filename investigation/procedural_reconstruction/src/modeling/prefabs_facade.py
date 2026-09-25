"""Facade-attached masses, in facade-local metres. No random choices here.

`u` runs along the facade from vertex_a, `v` is height above the facade base, and
positive depth points out of the building towards the street. Everything here is
a secondary mass hung on a wall: mouldings, balconies, galleries, awnings, bays.
"""

import numpy as np
from shapely.geometry import Polygon

from .detail import DEFAULT_BUDGET
from .prefabs import sign_letters

LEGACY_KINDS = ("panel", "frame", "ledge", "canopy", "curved_canopy")


# Arris break on mouldings that crown something. Small enough to stay a
# highlight, large enough to survive at block-viewing distance.
CHAMFER_M = 0.02


def _add(mb, a, t, n, feature, u1, u2, z1, z2, w1, w2, semantic, material=None,
         chamfer=0.0):
    mb.box(a, t, n, u1, u2, z1, z2, w1, w2,
           material or feature.material_slot, semantic, chamfer=chamfer)


def _footprint(a, t, n, u1, u2, w1, w2):
    origin = np.asarray(a, float)
    return Polygon([
        origin + t * u + n * w
        for u, w in ((u1, w1), (u2, w1), (u2, w2), (u1, w2))
    ])


def _balustrade(mb, a, t, n, u1, u2, z, depth, style="bars", material="metal"):
    """Railing around a projecting slab: bars, turned balusters or solid."""
    spacing = getattr(mb, "budget", DEFAULT_BUDGET).balustrade_spacing_m

    def point(u, height, out):
        xy = np.asarray(a, float) + t * u + n * out
        return (*xy, height)

    top = z + 1.02
    if style == "solid":
        for u_start, u_end, w_start, w_end in (
            (u1, u2, depth - 0.09, depth),
            (u1, u1 + 0.09, 0.0, depth),
            (u2 - 0.09, u2, 0.0, depth),
        ):
            mb.box(a, t, n, u_start, u_end, z, top - 0.08, w_start, w_end,
                   "plaster", "balustrade")
        mb.box(a, t, n, u1 - 0.03, u2 + 0.03, top - 0.08, top, -0.01, depth + 0.03,
               "stone", "balustrade_cap", chamfer=0.015)
        return
    if style == "balusters":
        mb.box(a, t, n, u1, u2, z, z + 0.10, depth - 0.10, depth, "stone",
               "balustrade")
        for u in np.arange(u1 + 0.10, u2 - 0.05, max(0.18, spacing * 1.4)):
            mb.box(a, t, n, u, u + 0.09, z + 0.10, top - 0.09,
                   depth - 0.09, depth - 0.01, "stone", "baluster")
        mb.box(a, t, n, u1, u2, top - 0.09, top, depth - 0.12, depth + 0.02,
               "stone", "balustrade_cap", chamfer=0.015)
        for u in (u1, u2 - 0.09):
            mb.box(a, t, n, u, u + 0.09, z, top, 0.0, depth, "stone", "baluster")
        return
    # Square section rather than round: it is what Lima ironwork is actually
    # made of, and a box costs 12 triangles against a cylinder's 32 — which
    # matters when a five-storey corner carries several hundred bars.
    for height in (z + 0.18, top):
        mb.box(a, t, n, u1 - 0.02, u2 + 0.02, height - 0.024, height + 0.024,
               depth - 0.055, depth - 0.007, material, "balcony_handrail")
        for u in (u1, u2 - 0.048):
            mb.box(a, t, n, u, u + 0.048, height - 0.024, height + 0.024,
                   0.02, depth - 0.007, material, "balcony_return")
    for u in np.arange(u1, u2 - 0.01, spacing):
        mb.box(a, t, n, u, u + 0.024, z + 0.18, top,
               depth - 0.042, depth - 0.018, material, "balcony_bar")
    for u in (u1, u2 - 0.024):
        for out in np.arange(0.06, depth - 0.03, spacing):
            mb.box(a, t, n, u, u + 0.024, z + 0.18, top, out, out + 0.024,
                   material, "balcony_bar")


# ── legacy kinds, kept byte-compatible in their part names ──────────────────


def panel(mb, a, t, n, feature):
    _add(mb, a, t, n, feature, feature.u_m, feature.u_m + feature.width_m,
         feature.v_m, feature.v_m + feature.height_m, -0.015, feature.depth_m,
         "facade_projection_panel")


def frame(mb, a, t, n, feature):
    u, v = feature.u_m, feature.v_m
    w, h, d = feature.width_m, feature.height_m, feature.depth_m
    border = min(feature.border_width_m, w / 2, h / 2)
    if border <= 0:
        raise ValueError("Facade frame requires a positive border")
    for u1, u2, z1, z2 in (
        (u, u + border, v, v + h),
        (u + w - border, u + w, v, v + h),
        (u + border, u + w - border, v, v + border),
        (u + border, u + w - border, v + h - border, v + h),
    ):
        _add(mb, a, t, n, feature, u1, u2, z1, z2, -0.015, d,
             "facade_projection_frame")


def ledge(mb, a, t, n, feature):
    _add(mb, a, t, n, feature, feature.u_m, feature.u_m + feature.width_m,
         feature.v_m, feature.v_m + feature.height_m, -0.015, feature.depth_m,
         "facade_projection_ledge")


def canopy(mb, a, t, n, feature):
    _add(mb, a, t, n, feature, feature.u_m, feature.u_m + feature.width_m,
         feature.v_m, feature.v_m + feature.height_m, -0.015, feature.depth_m,
         "facade_projection_canopy")


def curved_canopy(mb, a, t, n, feature):
    u, w, d = feature.u_m, feature.width_m, feature.depth_m
    origin = np.asarray(a, float)
    samples = np.linspace(0.0, 1.0, 13)
    outer = [origin + t * (u + w * x) + n * (d * np.sin(np.pi * x)) for x in samples]
    footprint = Polygon([origin + t * u, origin + t * (u + w), *outer[::-1]])
    mb.solid(footprint, feature.v_m, feature.v_m + feature.height_m,
             feature.material_slot, "facade_projection_curved_canopy")


# ── new vocabulary ──────────────────────────────────────────────────────────


def cornice(mb, a, t, n, feature):
    """Stepped crowning moulding; a single flat band reads as a printed line."""
    u1, u2 = feature.u_m, feature.u_m + feature.width_m
    steps = 3
    for index in range(steps):
        low = feature.v_m + feature.height_m * index / steps
        high = feature.v_m + feature.height_m * (index + 1) / steps
        out = feature.depth_m * (0.42 + 0.58 * (index + 1) / steps)
        _add(mb, a, t, n, feature, u1 - 0.02 * index, u2 + 0.02 * index,
             low, high, -0.02, out, "cornice_step")
    # Drip edge: the underside lip that throws water clear of the wall.
    _add(mb, a, t, n, feature, u1 - 0.04, u2 + 0.04,
         feature.v_m + feature.height_m, feature.v_m + feature.height_m + 0.05,
         -0.02, feature.depth_m + 0.03, "cornice_drip", "stone",
         chamfer=CHAMFER_M)


def sill_band(mb, a, t, n, feature):
    """Continuous sill course tying a row of openings together."""
    _add(mb, a, t, n, feature, feature.u_m, feature.u_m + feature.width_m,
         feature.v_m, feature.v_m + feature.height_m, -0.02, feature.depth_m,
         "sill_band")
    _add(mb, a, t, n, feature, feature.u_m, feature.u_m + feature.width_m,
         feature.v_m - 0.03, feature.v_m, feature.depth_m - 0.04,
         feature.depth_m - 0.01, "cornice_drip", "stone", chamfer=0.01)


def pilaster(mb, a, t, n, feature):
    """Vertical order: base, shaft, capital."""
    u1, u2 = feature.u_m, feature.u_m + feature.width_m
    base_h = min(0.34, feature.height_m * 0.10)
    cap_h = min(0.26, feature.height_m * 0.08)
    top = feature.v_m + feature.height_m
    _add(mb, a, t, n, feature, u1 - 0.04, u2 + 0.04, feature.v_m,
         feature.v_m + base_h, -0.02, feature.depth_m + 0.035, "pilaster_base")
    _add(mb, a, t, n, feature, u1, u2, feature.v_m + base_h, top - cap_h,
         -0.02, feature.depth_m, "pilaster")
    _add(mb, a, t, n, feature, u1 - 0.05, u2 + 0.05, top - cap_h, top,
         -0.02, feature.depth_m + 0.045, "pilaster_cap", chamfer=CHAMFER_M)


def balcony(mb, a, t, n, feature):
    """Projecting slab with a railing; the classic Lima cantilever."""
    u1, u2 = feature.u_m, feature.u_m + feature.width_m
    depth = feature.depth_m
    if not mb.can_attach(_footprint(a, t, n, u1, u2, -0.02, depth).buffer(0.04)):
        return
    _add(mb, a, t, n, feature, u1, u2, feature.v_m - 0.14, feature.v_m,
         -0.02, depth, "balcony_slab", "concrete")
    _add(mb, a, t, n, feature, u1, u2, feature.v_m - 0.19, feature.v_m - 0.14,
         depth - 0.06, depth, "cornice_drip", "stone")
    style = feature.label if feature.label in ("bars", "balusters", "solid") else "bars"
    _balustrade(mb, a, t, n, u1, u2, feature.v_m, depth, style)


def gallery(mb, a, t, n, feature):
    """Continuous covered balcony running the width of the facade."""
    u1, u2 = feature.u_m, feature.u_m + feature.width_m
    depth = feature.depth_m
    if not mb.can_attach(_footprint(a, t, n, u1, u2, -0.02, depth + 0.12).buffer(0.04)):
        return
    _add(mb, a, t, n, feature, u1, u2, feature.v_m - 0.16, feature.v_m,
         -0.02, depth, "gallery_slab", "concrete")
    posts = max(2, int(round(feature.width_m / 2.1)))
    top = feature.v_m + feature.height_m
    for index in range(posts + 1):
        u = u1 + (u2 - u1) * index / posts
        _add(mb, a, t, n, feature, u - 0.06, u + 0.06, feature.v_m, top,
             depth - 0.14, depth - 0.02, "gallery_post", "wood")
        _add(mb, a, t, n, feature, u - 0.11, u + 0.11, top - 0.26, top - 0.10,
             depth - 0.19, depth - 0.02, "gallery_bracket", "wood")
    _add(mb, a, t, n, feature, u1, u2, top - 0.10, top, -0.02, depth + 0.10,
         "gallery_roof", "roof")
    _balustrade(mb, a, t, n, u1, u2, feature.v_m, depth, "balusters")


def awning(mb, a, t, n, feature):
    """Shop awning: a raked sheet on two arms, with a hanging valance."""
    u1, u2 = feature.u_m, feature.u_m + feature.width_m
    depth = feature.depth_m
    rise = max(0.18, feature.height_m)
    if not mb.can_attach(_footprint(a, t, n, u1, u2, 0.0, depth + 0.05).buffer(0.04)):
        return
    origin = np.asarray(a, float)
    top = feature.v_m + rise
    sheet = Polygon([
        origin + t * u1, origin + t * u2,
        origin + t * u2 + n * depth, origin + t * u1 + n * depth,
    ])
    mb.solid(
        sheet,
        lambda x, y: feature.v_m - 0.02
        + (rise) * max(0.0, 1.0 - (np.dot([x, y] - origin, n) / max(depth, 1e-6))),
        lambda x, y: feature.v_m + 0.04
        + (rise) * max(0.0, 1.0 - (np.dot([x, y] - origin, n) / max(depth, 1e-6))),
        feature.material_slot,
        "awning",
    )
    for u in (u1 + 0.10, u2 - 0.16):
        _add(mb, a, t, n, feature, u, u + 0.06, feature.v_m, top,
             0.0, 0.06, "awning_arm", "metal")
        mb.beam(
            (*(origin + t * (u + 0.03) + n * 0.03), top),
            (*(origin + t * (u + 0.03) + n * depth), feature.v_m + 0.02),
            0.018, material="metal", semantic="awning_arm",
        )
    _add(mb, a, t, n, feature, u1, u2, feature.v_m - 0.22, feature.v_m,
         depth - 0.04, depth, "awning_valance")


def bay_window(mb, a, t, n, feature):
    """Shallow projecting bay: three walls, a floor slab and a small roof."""
    u1, u2 = feature.u_m, feature.u_m + feature.width_m
    depth, top = feature.depth_m, feature.v_m + feature.height_m
    if not mb.can_attach(_footprint(a, t, n, u1, u2, -0.02, depth).buffer(0.04)):
        return
    _add(mb, a, t, n, feature, u1, u2, feature.v_m - 0.16, feature.v_m,
         -0.02, depth, "bay_window_slab", "concrete")
    for u_start, u_end, w_start, w_end in (
        (u1, u1 + 0.14, 0.0, depth),
        (u2 - 0.14, u2, 0.0, depth),
        (u1, u2, depth - 0.14, depth),
    ):
        _add(mb, a, t, n, feature, u_start, u_end, feature.v_m, top,
             w_start, w_end, "bay_window_wall", "plaster")
    _add(mb, a, t, n, feature, u1 + 0.14, u2 - 0.14, feature.v_m + 0.42, top - 0.22,
         depth - 0.17, depth - 0.13, "glazing", "glass")
    _add(mb, a, t, n, feature, u1 - 0.05, u2 + 0.05, top, top + 0.10,
         -0.02, depth + 0.06, "bay_window_roof", "stone", chamfer=CHAMFER_M)


def eave(mb, a, t, n, feature):
    """Overhanging roof edge with exposed rafter tails."""
    u1, u2 = feature.u_m, feature.u_m + feature.width_m
    _add(mb, a, t, n, feature, u1, u2, feature.v_m + feature.height_m * 0.55,
         feature.v_m + feature.height_m, -0.02, feature.depth_m, "eave")
    for u in np.arange(u1 + 0.18, u2 - 0.10, 0.52):
        _add(mb, a, t, n, feature, u, u + 0.08, feature.v_m,
             feature.v_m + feature.height_m * 0.55, 0.0, feature.depth_m - 0.05,
             "rafter_tail", "wood")
    _add(mb, a, t, n, feature, u1, u2, feature.v_m + feature.height_m * 0.30,
         feature.v_m + feature.height_m * 0.62, feature.depth_m - 0.05,
         feature.depth_m, "eave_fascia", "wood")


def shutter(mb, a, t, n, feature):
    """Louvered leaves folded back against the wall beside an opening."""
    leaf = min(feature.border_width_m or 0.36, feature.width_m / 2.5)
    for u in (feature.u_m - leaf, feature.u_m + feature.width_m):
        _add(mb, a, t, n, feature, u, u + leaf, feature.v_m,
             feature.v_m + feature.height_m, 0.02, 0.02 + feature.depth_m,
             "shutter_leaf", "wood")
        for level in np.arange(feature.v_m + 0.06,
                               feature.v_m + feature.height_m - 0.04,
                               getattr(mb,'budget',DEFAULT_BUDGET).shutter_pitch_m):
            _add(mb, a, t, n, feature, u + 0.02, u + leaf - 0.02, level,
                 level + 0.045, 0.02 + feature.depth_m,
                 0.03 + feature.depth_m, "shutter_slat", "wood")


def downpipe(mb, a, t, n, feature):
    """Rainwater pipe with its wall clamps."""
    origin = np.asarray(a, float) + t * feature.u_m + n * (feature.depth_m * 0.6)
    mb.beam((*origin, feature.v_m), (*origin, feature.v_m + feature.height_m),
            max(0.03, feature.depth_m * 0.35), material="metal", semantic="downpipe")
    for level in np.arange(feature.v_m + 0.5, feature.v_m + feature.height_m, 1.6):
        _add(mb, a, t, n, feature, feature.u_m - 0.06, feature.u_m + 0.06,
             level, level + 0.05, 0.0, feature.depth_m * 0.6, "downpipe_clamp",
             "metal")


def sign_box(mb, a, t, n, feature):
    """Shop sign: a raised box, optionally carrying relief lettering."""
    _add(mb, a, t, n, feature, feature.u_m, feature.u_m + feature.width_m,
         feature.v_m, feature.v_m + feature.height_m, -0.01, feature.depth_m,
         "sign_box", "sign")
    for u in (feature.u_m + 0.05, feature.u_m + feature.width_m - 0.11):
        _add(mb, a, t, n, feature, u, u + 0.06, feature.v_m - 0.12, feature.v_m,
             0.0, feature.depth_m, "sign_bracket", "metal")
    if feature.label:
        sign_letters(mb, a, t, n, feature)


FACADE_PROJECTIONS = {
    "panel": panel,
    "frame": frame,
    "ledge": ledge,
    "canopy": canopy,
    "curved_canopy": curved_canopy,
    "cornice": cornice,
    "sill_band": sill_band,
    "pilaster": pilaster,
    "balcony": balcony,
    "gallery": gallery,
    "awning": awning,
    "bay_window": bay_window,
    "eave": eave,
    "shutter": shutter,
    "downpipe": downpipe,
    "sign_box": sign_box,
}
