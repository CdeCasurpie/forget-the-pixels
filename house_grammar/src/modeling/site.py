"""Everything between the building and the street: fences, gardens, entrances.

A lot is not just its building. The strip in front carries the fence and its
gates, the planting between fence and facade, and the step up to each door. With
none of it the ground floor reads as a wall dropped on a plane.
"""

from __future__ import annotations

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from modeling.boundaries import generate_boundaries
from modeling.fences import build_fence
from modeling.geometry_constraints import largest_polygon, outward_normal
from modeling.mesh_builder import polygons

APPROACH_CLEARANCE_M = 0.30
PLANT_SPACING_M = 1.15
MIN_GARDEN_AREA_M2 = 0.8


def entrance_step(mb, entrance, rng):
    """Two shallow treads in front of a door, and the threshold slab."""
    origin = np.asarray(entrance["origin"], float)
    tangent = np.asarray(entrance["tangent"], float)
    normal = np.asarray(entrance["normal"], float)
    width = float(entrance["width"])
    base_z = float(entrance["base_z"])
    for index, (rise, run) in enumerate(((0.16, 0.34), (0.08, 0.60))):
        mb.box(origin, tangent, normal, -0.12 - index * 0.06,
               width + 0.12 + index * 0.06, base_z - rise, base_z - rise + 0.16,
               0.0, run, "stone", "entrance_step")


def plant_garden(mb, parcel, built, boundaries, entrances, rng):
    """Planting in the gap between fence and facade, keeping doorways clear."""
    garden = parcel
    if not built.is_empty:
        garden = garden.difference(built.buffer(0.10))
    for boundary in boundaries:
        garden = garden.difference(boundary.line.buffer(0.45))
    for entrance in entrances:
        origin = np.asarray(entrance["origin"], float)
        tangent = np.asarray(entrance["tangent"], float)
        normal = np.asarray(entrance["normal"], float)
        centre = origin + tangent * (entrance["width"] / 2.0)
        corridor = LineString([centre, centre + normal * 6.0])
        garden = garden.difference(
            corridor.buffer(entrance["width"] / 2.0 + APPROACH_CLEARANCE_M,
                            cap_style=2)
        )
    garden = largest_polygon(garden)
    if garden is None or garden.area < MIN_GARDEN_AREA_M2:
        return 0

    planted = 0
    for patch in polygons(garden.buffer(-0.35, join_style=2)):
        minx, miny, maxx, maxy = patch.bounds
        for x in np.arange(minx, maxx + PLANT_SPACING_M, PLANT_SPACING_M):
            for y in np.arange(miny, maxy + PLANT_SPACING_M, PLANT_SPACING_M):
                spot = Point(x + float(rng.uniform(0, 0.3)),
                             y + float(rng.uniform(0, 0.3)))
                radius = float(rng.uniform(0.30, 0.42))
                if not patch.covers(spot.buffer(radius + 0.06)):
                    continue
                mb.solid(spot.buffer(radius + 0.05, quad_segs=6), 0.02, 0.24,
                         "stone", "planter")
                mb.solid(spot.buffer(radius, quad_segs=6), 0.24, 0.27, "soil",
                         "planting_soil")
                for tier in range(2):
                    mb.foliage(
                        (spot.x, spot.y, 0.44 + tier * 0.16),
                        (radius * 0.9, radius * 0.9, 0.26),
                        rng,
                    )
                planted += 1
    return planted


def build_site(mb, context, program, site_plan, entrances, rng):
    """Fences, gates, planting and entrance steps for one lot."""
    parcel = Polygon(context.polygon)
    masses = [Polygon(mass.footprint) for mass in site_plan.masses]
    built = unary_union(masses) if masses else Polygon()

    boundaries = generate_boundaries(context, program, site_plan)
    for index, boundary in enumerate(boundaries):
        coords = list(boundary.line.coords)
        tangent, normal, length = outward_normal(parcel, coords[0], coords[-1])
        if tangent is None:
            continue
        origin = np.asarray(coords[0], float)
        with mb.assembly(f"site/fence_{index:02d}"):
            build_fence(mb, origin, tangent, normal, length, boundary)

    for index, entrance in enumerate(entrances):
        with mb.assembly(f"site/entrance_{index:02d}"):
            entrance_step(mb, entrance, rng)

    with mb.assembly("site/garden"):
        return plant_garden(mb, parcel, built, boundaries, entrances, rng)
