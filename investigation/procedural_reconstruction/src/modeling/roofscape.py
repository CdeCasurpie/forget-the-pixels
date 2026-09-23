"""Roofs as their own grammar: surfaces, parapets and scattered rooftop objects.

The previous roof was always one flat slab with a parapet and, at most, three
objects crowded onto a single brute-force-located platform. Seen from above —
which is how a block is read — that is the largest gap against a real Lima roof
plan, where tanks, aerials, ducts, condensers, service rooms, laundry and pots
are spread over the whole surface, and the street-facing band is often tiled.
"""

from __future__ import annotations

import numpy as np
from shapely.affinity import translate
from shapely.geometry import Polygon
from shapely.ops import unary_union

from domain.architecture import RoofPlan, RoofProp, RoofSurface
from modeling.detail import DEFAULT_BUDGET
from modeling.geometry_constraints import (
    apply_edge_setbacks,
    largest_polygon,
    outward_normal,
)
from modeling.mesh_builder import polygons
from modeling.prefabs_roof import BUILDERS, FOOTPRINTS, frame
from modeling.randomness import resolve_seed

TILE_SLOPE_DEG = 20.0
TILE_EAVE_OVERHANG_M = 0.38
# A tiled band is a band, not a roof: past roughly half the depth it stops
# reading as a street-facing eave and starts looking like a barn dropped on top.
TILE_MAX_DEPTH_FRACTION = 0.5
TILE_MAX_DEPTH_M = 3.6
PROP_EDGE_CLEARANCE_M = 0.55
PROP_SPACING_M = 0.28

# How many of each kind may stand on one roof. Tanks and aerials repeat; a
# stair head or a service room does not.
PROP_LIMITS = {
    "stair_bulkhead": 1,
    "caseta": 2,
    "skylight": 3,
    "duct_run": 2,
    "hvac": 4,
    "tank_elevated": 2,
    "water_tank": 3,
    "antenna": 3,
    "laundry": 2,
    "planter": 6,
    "rebar_cluster": 6,
}

# Weighted vocabulary per use, so a workshop roof does not read like a flat.
PROP_WEIGHTS = {
    "residential": {
        "water_tank": 3.0, "tank_elevated": 1.4, "antenna": 2.2, "laundry": 2.6,
        "planter": 2.4, "caseta": 1.6, "stair_bulkhead": 1.2, "rebar_cluster": 1.8,
        "hvac": 0.6, "skylight": 0.5,
    },
    "commercial": {
        "hvac": 3.2, "duct_run": 2.6, "skylight": 1.8, "water_tank": 1.4,
        "stair_bulkhead": 1.2, "antenna": 0.8, "caseta": 1.0, "planter": 0.4,
    },
    "mixed": {
        "water_tank": 2.2, "hvac": 2.0, "duct_run": 1.4, "antenna": 1.6,
        "laundry": 1.6, "planter": 1.4, "caseta": 1.4, "stair_bulkhead": 1.2,
        "skylight": 1.0, "rebar_cluster": 1.0,
    },
}

# An informal top-floor addition carries the household clutter, not plant.
AZOTEA_WEIGHTS = {
    "laundry": 3.0, "water_tank": 2.4, "planter": 2.0, "rebar_cluster": 2.4,
    "antenna": 1.4,
}


def _sweep(polygon, direction, distance, steps=4):
    """Polygon swept along a direction, so an eave grows a continuous apron."""
    if distance <= 0:
        return polygon
    direction = np.asarray(direction, float)
    parts = [polygon]
    for step in range(1, steps + 1):
        offset = direction * (distance * step / steps)
        parts.append(translate(polygon, xoff=float(offset[0]), yoff=float(offset[1])))
    return largest_polygon(unary_union(parts)) or polygon


def _depth_span(polygon, outward):
    """How far the polygon reaches back from its most street-ward point."""
    coords = np.asarray(polygon.exterior.coords)[:, :2]
    projected = coords @ np.asarray(outward, float)
    return float(projected.max() - projected.min())


def _eave_reference(strip, outward):
    """Point on the strip furthest towards the street, used as the eave datum."""
    coords = np.asarray(strip.exterior.coords)[:, :2]
    return coords[int(np.argmax(coords @ np.asarray(outward, float)))]


def _tile_surface(polygon, fronts, parcel, base_z, rng):
    """Tiled band over the street-facing edge, with the flat remainder."""
    if not fronts:
        return None, polygon
    line = min(fronts, key=lambda front: front.distance(polygon))
    if line.distance(polygon) > 0.6:
        return None, polygon
    _, probe_outward, _ = outward_normal(parcel, line.coords[0], line.coords[-1])
    if probe_outward is None:
        return None, polygon
    span = _depth_span(polygon, probe_outward)
    depth = float(
        min(rng.uniform(2.4, 3.6), span * TILE_MAX_DEPTH_FRACTION, TILE_MAX_DEPTH_M)
    )
    if depth < 1.8:
        return None, polygon
    rear = largest_polygon(apply_edge_setbacks(polygon, [line], depth))
    if rear is None:
        return None, polygon
    strip = largest_polygon(polygon.difference(rear))
    if strip is None or strip.area < 4.0 or rear.area < 6.0:
        return None, polygon
    _, outward, _ = outward_normal(parcel, line.coords[0], line.coords[-1])
    if outward is None:
        return None, polygon
    eave = _eave_reference(strip, outward)
    covered = _sweep(strip, outward, TILE_EAVE_OVERHANG_M)
    surface = RoofSurface(
        polygon=tuple((float(x), float(y)) for x, y in covered.exterior.coords),
        kind="tile_shed",
        base_z=base_z,
        slope_deg=TILE_SLOPE_DEG,
        eave_point=(float(eave[0]), float(eave[1])),
        inward_normal=(float(-outward[0]), float(-outward[1])),
    )
    return surface, rear


def _weights_for(mass, program):
    if mass.role == "azotea":
        return AZOTEA_WEIGHTS
    return PROP_WEIGHTS.get(program.use, PROP_WEIGHTS["residential"])


def _prop_footprint(kind, xy, rotation, scale):
    length, width = FOOTPRINTS[kind]
    tangent, normal = frame(rotation)
    half_u, half_w = length * scale / 2.0, width * scale / 2.0
    centre = np.asarray(xy, float)
    corners = [
        centre + tangent * du + normal * dw
        for du, dw in ((-half_u, -half_w), (half_u, -half_w),
                       (half_u, half_w), (-half_u, half_w))
    ]
    return Polygon(corners)


def scatter_props(area, weights, rng, *, density=0.10, limit=14):
    """Place props on a jittered grid, rejecting overlaps and edge overhangs."""
    usable = area.buffer(-PROP_EDGE_CLEARANCE_M, join_style=2)
    if usable.is_empty:
        return ()
    target = int(np.clip(round(area.area * density), 1, limit))
    kinds = list(weights)
    probabilities = np.array([weights[kind] for kind in kinds], float)
    probabilities /= probabilities.sum()

    minx, miny, maxx, maxy = usable.bounds
    step = 1.05
    grid = [
        (x + float(rng.uniform(0, step)), y + float(rng.uniform(0, step)))
        for x in np.arange(minx, maxx + step, step)
        for y in np.arange(miny, maxy + step, step)
    ]
    if not grid:
        return ()
    order = rng.permutation(len(grid))

    placed, shapes, counts = [], [], {}
    for index in order:
        if len(placed) >= target:
            break
        point = grid[int(index)]
        kind = str(rng.choice(kinds, p=probabilities))
        if counts.get(kind, 0) >= PROP_LIMITS.get(kind, 3):
            continue
        rotation = float(rng.uniform(0, 360))
        scale = float(rng.uniform(0.88, 1.12))
        footprint = _prop_footprint(kind, point, rotation, scale)
        if not usable.covers(footprint):
            continue
        padded = footprint.buffer(PROP_SPACING_M, join_style=2)
        if any(padded.intersects(other) for other in shapes):
            continue
        shapes.append(footprint)
        counts[kind] = counts.get(kind, 0) + 1
        placed.append(
            RoofProp(
                kind=kind,
                position=(float(point[0]), float(point[1])),
                rotation_deg=rotation,
                scale=scale,
                seed=int(rng.integers(0, 2**31 - 1)),
            )
        )
    return tuple(placed)


def plan_roof(mass, program, exposed_area, fronts, parcel, seed, *, lot_id="lot",
              budget=DEFAULT_BUDGET):
    """Decide the surfaces, parapet and objects of one mass's roof."""
    rng = np.random.default_rng(resolve_seed(seed, lot_id, mass.id, "roof", "plan"))
    roof_z = float(mass.roof_z)

    wants_tile = (
        mass.role in ("front", "main", "corner", "podium")
        and program.use in ("residential", "mixed")
        and float(rng.random()) < 0.45
    )

    surfaces, flat_parts = [], []
    for part in polygons(exposed_area):
        if part.area < 0.5:
            continue
        remainder = part
        if wants_tile:
            tile, remainder = _tile_surface(part, fronts, parcel, roof_z, rng)
            if tile is not None:
                surfaces.append(tile)
        if remainder is not None and remainder.area > 0.5:
            kind = "corrugated" if mass.role == "azotea" else "flat"
            surfaces.append(
                RoofSurface(
                    polygon=tuple(
                        (float(x), float(y)) for x, y in remainder.exterior.coords
                    ),
                    kind=kind,
                    base_z=roof_z,
                )
            )
            flat_parts.append(remainder)

    # Drawn before anything the budget can influence: how many objects stand on
    # a roof is a rendering decision, how tall its parapet is is not, and a
    # shared random stream would let the first silently change the second.
    parapet = 0.0 if mass.role == "azotea" else float(rng.uniform(0.35, 0.75))

    props = ()
    if flat_parts:
        field = largest_polygon(unary_union(flat_parts))
        if field is not None and field.area > 4.0:
            density = budget.roof_prop_density
            if program.maintenance == "premium":
                density *= 0.6
            props = scatter_props(
                field,
                _weights_for(mass, program),
                np.random.default_rng(
                    resolve_seed(seed, lot_id, mass.id, "roof", "props")
                ),
                density=density,
                limit=budget.roof_prop_limit,
            )
    return RoofPlan(
        mass_id=mass.id,
        surfaces=tuple(surfaces),
        props=props,
        parapet_height_m=parapet,
        parapet_profile="none" if parapet <= 0 else "cap",
        roof_z=roof_z,
    )


def _slope_fields(surface):
    slope = np.tan(np.radians(surface.slope_deg))
    origin = np.asarray(surface.eave_point, float)
    inward = np.asarray(surface.inward_normal, float)
    thickness = surface.thickness_m

    def top(x, y):
        return surface.base_z + slope * float(
            (x - origin[0]) * inward[0] + (y - origin[1]) * inward[1]
        )

    def bottom(x, y):
        return top(x, y) - thickness

    return bottom, top


def build_roof(mb, plan, rng):
    """Emit one mass's roof: surfaces, ridge closures, parapet and objects."""
    with mb.assembly(f"roof/{plan.mass_id}"):
        _build_roof_body(mb, plan, rng)


def _build_roof_body(mb, plan, rng):
    tiles = []
    flats = []
    for surface in plan.surfaces:
        polygon = Polygon(surface.polygon)
        if polygon.is_empty:
            continue
        if surface.kind == "flat":
            mb.solid(polygon, surface.base_z - surface.thickness_m, surface.base_z,
                     "concrete", "roof_slab")
            flats.append(polygon)
        elif surface.kind == "corrugated":
            mb.solid(polygon, surface.base_z - surface.thickness_m, surface.base_z,
                     "concrete", "roof_slab")
            mb.solid(polygon, surface.base_z, surface.base_z + 0.05, "roof",
                     "corrugated_roof")
            flats.append(polygon)
        else:
            bottom, top = _slope_fields(surface)
            mb.solid(polygon, bottom, top, "roof_tile", "tile_roof")
            tiles.append((polygon, surface))

    # Close the vertical face where a tiled band meets the flat roof behind it,
    # and hang a fascia at its eave so the slab is not seen end-on. Both bands
    # are taken from inside the tile itself: sweeping outwards and differencing
    # would wrap around the sides, where the plane drops below the slab and the
    # closure would have no height to span.
    for polygon, surface in tiles:
        bottom, top = _slope_fields(surface)
        inward = np.asarray(surface.inward_normal, float)
        base = surface.base_z

        # Close the whole perimeter except the eave: the ridge at the back and
        # the two gable triangles at the sides, which otherwise leave the roof
        # open and show its underside from every oblique view.
        eave_band = polygon.difference(
            translate(polygon, xoff=inward[0] * 0.35, yoff=inward[1] * 0.35)
        )
        skirt = polygon.difference(
            polygon.buffer(-0.13, join_style=2)
        ).difference(eave_band.buffer(0.02, join_style=2))
        for piece in polygons(skirt):
            mb.solid(
                piece,
                base,
                lambda x, y, f=bottom, b=base: max(f(x, y), b + 0.02),
                "roof_tile",
                "tile_ridge",
            )

        fascia = polygon.difference(
            translate(polygon, xoff=inward[0] * 0.07, yoff=inward[1] * 0.07)
        )
        for piece in polygons(fascia):
            mb.solid(
                piece,
                lambda x, y, f=bottom: f(x, y) - 0.12,
                lambda x, y, f=bottom: f(x, y) + 0.01,
                "roof_tile",
                "eave_fascia",
            )

    if plan.parapet_height_m > 0 and flats:
        field = largest_polygon(unary_union(flats))
        if field is not None:
            ring = field.difference(field.buffer(-0.14, join_style=2))
            for polygon, _ in tiles:
                ring = ring.difference(polygon.buffer(0.06, join_style=2))
            for piece in polygons(ring):
                mb.solid(piece, plan.roof_z, plan.roof_z + plan.parapet_height_m,
                         "plaster", "parapet")
            if plan.parapet_profile == "cap":
                cap = field.difference(field.buffer(-0.19, join_style=2))
                for polygon, _ in tiles:
                    cap = cap.difference(polygon.buffer(0.06, join_style=2))
                # Two courses rather than one slab: the break in the arris is
                # what keeps the coping from reading as a drawn line.
                head = plan.roof_z + plan.parapet_height_m
                for piece in polygons(cap):
                    mb.solid(piece, head, head + 0.05, "stone", "parapet_cap")
                    weathered = piece.buffer(-0.015, join_style=2)
                    for inner in polygons(weathered):
                        mb.solid(inner, head + 0.05, head + 0.07, "stone",
                                 "parapet_cap")

    for index, prop in enumerate(plan.props):
        builder = BUILDERS.get(prop.kind)
        if builder is None:
            continue
        with mb.assembly(f"roof/{plan.mass_id}/prop_{prop.kind}_{index:02d}"):
            builder(
                mb,
                prop.position,
                plan.roof_z,
                prop.rotation_deg,
                prop.scale,
                np.random.default_rng(prop.seed),
            )
