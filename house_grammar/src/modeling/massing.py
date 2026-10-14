"""Volumetric massing: one cadastral lot becomes several adjacent or stacked volumes.

A Lima block is never a row of single extruded prisms. Lots carry a street-facing
body, a lower service body over the rear patio, podium/tower splits on commercial
corners, set-back top floors that read as terraces, and informal rooftop additions.
This module turns a parcel plus a measured height into that set of volumes.

Volumes are either disjoint in plan or stacked in Z, never interpenetrating, so
`modeling.exposure` can resolve which walls and roofs are actually visible.
"""

from __future__ import annotations

import numpy as np
from shapely.geometry import Point, Polygon
from shapely.geometry.polygon import orient

from domain.architecture import MassSpec
from modeling.geometry_constraints import (
    apply_edge_setbacks,
    front_lines,
    largest_polygon,
    parcel_polygon,
    snap,
)

PATTERNS = (
    "single_block",
    "front_tall_rear_low",
    "front_low_rear_tall",
    "podium_tower",
    "stepped_back",
    "corner_accent",
)

MIN_MASS_AREA_M2 = 6.0
MIN_MASS_WIDTH_M = 1.8
DEFAULT_FLOOR_HEIGHT_M = 2.8


def usable(polygon, min_area=MIN_MASS_AREA_M2, min_width=MIN_MASS_WIDTH_M):
    """Reject empty, invalid, tiny or sliver-thin volumes before they reach geometry."""
    if polygon is None or polygon.is_empty or not polygon.is_valid:
        return False
    if polygon.area < min_area:
        return False
    # A sliver survives an area test but collapses when eroded by half its width.
    return not polygon.buffer(-min_width / 2.0, join_style=2).is_empty


def lot_depth(parcel, fronts):
    """How far the lot reaches back from its street edges."""
    if not fronts:
        minx, miny, maxx, maxy = parcel.bounds
        return float(max(maxx - minx, maxy - miny))
    return float(
        max(
            min(line.distance(Point(vertex)) for line in fronts)
            for vertex in parcel.exterior.coords
        )
    )


def split_at_depth(parcel, fronts, depth):
    """(front band, rear remainder) cut parallel to the street edges."""
    if depth <= 0 or not fronts:
        return None, None
    rear = largest_polygon(apply_edge_setbacks(parcel, fronts, depth))
    if rear is None:
        return None, None
    front = largest_polygon(parcel.difference(rear))
    return front, rear


def floor_ladder(base_z, roof_z, floor_h):
    """Storey levels on a lot-wide ladder so bands line up between volumes."""
    if roof_z - base_z < 1e-6:
        return (float(base_z), float(roof_z))
    steps = max(1, int(round((roof_z - base_z) / max(floor_h, 0.1))))
    levels = [base_z + index * (roof_z - base_z) / steps for index in range(steps + 1)]
    levels[0], levels[-1] = base_z, roof_z
    return tuple(float(level) for level in levels)


def _volume(role, polygon, base_z, roof_z, floor_h, index):
    polygon = orient(polygon, sign=1.0)
    return MassSpec(
        id=f"{role}_{index}",
        footprint=tuple((float(x), float(y)) for x, y in polygon.exterior.coords),
        base_z=float(base_z),
        roof_z=float(roof_z),
        floor_levels=floor_ladder(base_z, roof_z, floor_h),
        role=role,
        roof_spec=None,
    )


# ── patterns ─────────────────────────────────────────────────────────────────
# Each returns [(role, polygon, base_z, roof_z)] or None when the lot cannot
# carry it, in which case the caller falls back to a single block.


def _single_block(buildable, fronts, roof_z, floor_h, rng):
    return [("main", buildable, 0.0, roof_z)]


def _front_rear(buildable, fronts, roof_z, floor_h, rng, *, tall_front):
    depth = lot_depth(buildable, fronts)
    band = float(np.clip(depth * rng.uniform(0.38, 0.55), 5.0, 12.0))
    front, rear = split_at_depth(buildable, fronts, band)
    if not (usable(front) and usable(rear)):
        return None
    floors = max(1, int(round(roof_z / floor_h)))
    drop = 1 if floors <= 3 else int(rng.integers(1, 3))
    low_z = roof_z - drop * floor_h
    if low_z < floor_h * 0.9:
        return None
    if tall_front:
        return [("front", front, 0.0, roof_z), ("rear", rear, 0.0, low_z)]
    return [("front", front, 0.0, low_z), ("rear", rear, 0.0, roof_z)]


def _podium_tower(buildable, fronts, roof_z, floor_h, rng):
    podium_floors = 1 if roof_z < 5 * floor_h else int(rng.integers(1, 3))
    podium_z = podium_floors * floor_h
    if roof_z - podium_z < 1.5 * floor_h:
        return None
    setback = float(rng.uniform(2.0, 4.0))
    tower = largest_polygon(apply_edge_setbacks(buildable, fronts, setback))
    if not usable(tower, min_area=12.0):
        return None
    return [("podium", buildable, 0.0, podium_z), ("tower", tower, podium_z, roof_z)]


def _stepped_back(buildable, fronts, roof_z, floor_h, rng):
    if roof_z < 2.5 * floor_h:
        return None
    body_z = roof_z - floor_h
    setback = float(rng.uniform(2.2, 3.6))
    top = largest_polygon(apply_edge_setbacks(buildable, fronts, setback))
    if not usable(top, min_area=10.0):
        return None
    return [("main", buildable, 0.0, body_z), ("setback", top, body_z, roof_z)]


def _corner_accent(buildable, fronts, roof_z, floor_h, rng):
    """A mirador one storey above the parapet where two streets meet."""
    if len(fronts) < 2:
        return None
    reach = float(rng.uniform(4.0, 7.0))
    bands = []
    for line in fronts[:2]:
        rear = largest_polygon(apply_edge_setbacks(buildable, [line], reach))
        if rear is None:
            return None
        band = largest_polygon(buildable.difference(rear))
        if band is None:
            return None
        bands.append(band)
    corner = largest_polygon(bands[0].intersection(bands[1]))
    if not usable(corner, min_area=9.0):
        return None
    return [
        ("main", buildable, 0.0, roof_z),
        ("corner", corner, roof_z, roof_z + floor_h),
    ]


_BUILDERS = {
    "single_block": _single_block,
    "front_tall_rear_low": lambda *a: _front_rear(*a, tall_front=True),
    "front_low_rear_tall": lambda *a: _front_rear(*a, tall_front=False),
    "podium_tower": _podium_tower,
    "stepped_back": _stepped_back,
    "corner_accent": _corner_accent,
}


def choose_pattern(buildable, program, floors, fronts, rng):
    """Weighted, seed-traceable choice among the patterns the lot can carry."""
    depth = lot_depth(buildable, fronts)
    area = buildable.area
    options = [("single_block", 1.0)]
    if depth >= 13.0 and area >= 60.0:
        options.append(("front_tall_rear_low", 2.2))
        options.append(("front_low_rear_tall", 1.0))
    if floors >= 4 and area >= 80.0 and program.use in ("commercial", "mixed"):
        options.append(("podium_tower", 2.0))
    if floors >= 3 and area >= 45.0:
        options.append(("stepped_back", 1.2))
    if getattr(program, "is_corner", False) and floors >= 2 and area >= 55.0:
        options.append(("corner_accent", 1.8))
    weights = np.array([weight for _, weight in options], float)
    return str(rng.choice([name for name, _ in options], p=weights / weights.sum()))


def _rooftop_addition(volumes, fronts, floor_h, rng):
    """Informal top-floor addition at the back of the tallest roof."""
    role, polygon, _, top_z = max(volumes, key=lambda volume: volume[3])
    if role == "corner":
        return None
    platform = largest_polygon(polygon.buffer(-0.7, join_style=2))
    if not usable(platform, min_area=14.0):
        return None
    depth = lot_depth(platform, fronts)
    keep = largest_polygon(
        apply_edge_setbacks(platform, fronts, depth * float(rng.uniform(0.25, 0.5)))
    )
    addition = keep if usable(keep, min_area=9.0) else platform
    return ("azotea", addition, top_z, top_z + floor_h * float(rng.uniform(0.80, 0.95)))


def generate_masses(
    context,
    program,
    roof_z,
    floor_h=DEFAULT_FLOOR_HEIGHT_M,
    *,
    pattern="auto",
    seed=None,
    allow_rooftop_addition=True,
):
    """Volumes for one lot, given its measured roof height.

    `pattern` accepts any name in PATTERNS, or "auto" to pick a weighted one from
    the seed. A pattern the lot geometry cannot carry silently degrades to a
    single block rather than emitting slivers.
    """
    parcel = largest_polygon(parcel_polygon(context))
    if parcel is None or parcel.is_empty:
        raise ValueError("Parcel context has no usable polygon")
    parcel = orient(parcel, sign=1.0)

    roof_z = float(roof_z)
    floor_h = float(floor_h)
    if not np.isfinite(roof_z) or roof_z <= 0 or not np.isfinite(floor_h) or floor_h <= 0:
        raise ValueError("Massing needs a positive finite height and floor height")
    if pattern not in PATTERNS and pattern != "auto":
        raise ValueError(f"Unknown massing pattern: {pattern}")

    rng = np.random.default_rng(program.seed if seed is None else seed)
    fronts = front_lines(context)

    # A declared front setback carves the garden out before any pattern applies.
    buildable = parcel
    setback = float(getattr(program, "front_setback", 0.0) or 0.0)
    if setback > 0 and fronts:
        candidate = largest_polygon(apply_edge_setbacks(parcel, fronts, setback))
        if usable(candidate):
            buildable = candidate

    floors = max(1, int(round(roof_z / floor_h)))
    name = choose_pattern(buildable, program, floors, fronts, rng) if pattern == "auto" else pattern
    volumes = _BUILDERS[name](buildable, fronts, roof_z, floor_h, rng)
    if not volumes or not all(usable(polygon) for _, polygon, _, _ in volumes):
        volumes = _single_block(buildable, fronts, roof_z, floor_h, rng)

    if allow_rooftop_addition and rng.random() < 0.45:
        addition = _rooftop_addition(volumes, fronts, floor_h, rng)
        if addition is not None:
            volumes = [*volumes, addition]

    # Land every volume on the shared cadastral grid and inside the lot, so the
    # exposure pass re-snapping them cannot drift them back outside.
    placed = []
    for index, (role, polygon, base_z, top_z) in enumerate(volumes):
        bounded = largest_polygon(snap(polygon.intersection(parcel)))
        if usable(bounded):
            placed.append(_volume(role, bounded, base_z, top_z, floor_h, index))
    if not placed:
        placed = [_volume("main", parcel, 0.0, roof_z, floor_h, 0)]
    return tuple(placed)
