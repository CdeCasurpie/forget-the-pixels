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
from modeling.detail import DEFAULT_BUDGET
from modeling.geometry_constraints import largest_polygon, outward_normal
from modeling.mesh_builder import polygons

APPROACH_CLEARANCE_M = 0.30
PLANT_SPACING_M = 1.15
MIN_GARDEN_AREA_M2 = 0.8


def draw_fence(mb, a, t, n, length, boundary, rng, base_mat="plaster", style="reja"):
    """One run of perimeter fence, interrupted by its gates."""
    budget = getattr(mb, "budget", DEFAULT_BUDGET)
    bar_pitch = budget.fence_bar_spacing_m
    height = boundary.height if style != "low" else 1.2
    base_h = 0.6

    def spans_gate(u):
        if boundary.gate_u is not None and \
                boundary.gate_u <= u <= boundary.gate_u + boundary.gate_width:
            return True
        return (
            style != "low"
            and boundary.garage_u is not None
            and boundary.garage_u <= u <= boundary.garage_u + boundary.garage_width
        )

    cuts = [0.0, length]
    if boundary.gate_u is not None:
        cuts.extend([boundary.gate_u, boundary.gate_u + boundary.gate_width])
    if style != "low" and boundary.garage_u is not None:
        cuts.extend([boundary.garage_u, boundary.garage_u + boundary.garage_width])
    cuts = sorted({float(np.clip(cut, 0.0, length)) for cut in cuts})

    for u1, u2 in zip(cuts[:-1], cuts[1:]):
        if u2 - u1 < 0.05 or spans_gate((u1 + u2) / 2.0):
            continue
        if style == "reja":
            mb.box(a, t, n, u1, u2, 0.0, base_h, -0.15, 0.0, "brick", "boundary_base")
            if budget.wants_mortar_courses:
                for level in np.arange(0.08, base_h - 0.02, 0.13):
                    mb.box(a, t, n, u1 + 0.02, u2 - 0.02, level, level + 0.012,
                           -0.155, -0.145, "stone", "mortar")
            step = (u2 - u1) / max(1, int((u2 - u1) / bar_pitch))
            for bar_u in np.arange(u1, u2 - 0.01, step):
                mb.box(a, t, n, bar_u, bar_u + 0.02, base_h, height, -0.09, -0.07,
                       "metal", "fence_bar")
            mb.box(a, t, n, u1, u2, height - 0.05, height, -0.10, -0.06, "metal",
                   "fence_rail")
            mb.box(a, t, n, u1, u2, base_h, base_h + 0.05, -0.17, -0.03, "stone",
                   "boundary_cap", chamfer=0.012)
        elif style == "low":
            mb.box(a, t, n, u1, u2, 0.0, base_h, -0.20, 0.0, "plaster",
                   "boundary_base")
            mb.box(a, t, n, u1, u2, base_h - 0.05, base_h, -0.25, 0.05, "stone",
                   "boundary_cap")
            pillars = max(2, int(round((u2 - u1) / 1.5)) + 1)
            pitch = (u2 - u1) / (pillars - 1) if pillars > 1 else 0.0
            for index in range(pillars):
                centre = u1 + index * pitch
                mb.box(a, t, n, max(u1, centre - 0.15), min(u2, centre + 0.15),
                       0.0, height, -0.22, 0.02, "plaster", "boundary_post")
                mb.box(a, t, n, max(u1, centre - 0.17), min(u2, centre + 0.17),
                       height, height + 0.10, -0.25, 0.05, "stone", "boundary_cap",
                       chamfer=0.015)
            for index in range(pillars - 1):
                left = u1 + index * pitch + 0.15
                right = u1 + (index + 1) * pitch - 0.15
                if right <= left:
                    continue
                step = (right - left) / max(1, int((right - left) / bar_pitch))
                for bar_u in np.arange(left, right - 0.01, step):
                    mb.box(a, t, n, bar_u, bar_u + 0.02, base_h, height, -0.11,
                           -0.09, "metal", "fence_bar")
                mb.box(a, t, n, left, right, height - 0.02, height, -0.12, -0.08,
                       "metal", "fence_rail")
        else:
            mb.box(a, t, n, u1, u2, 0.0, height, -0.15, 0.0, base_mat, "wall")
            if style == "solid":
                mb.box(a, t, n, u1, u2, height - 0.10, height, -0.20, 0.05,
                       "stone", "boundary_cap", chamfer=0.015)

    if boundary.gate_u is not None:
        gate_h = height * (0.8 if style != "low" else 1.0)
        mb.box(a, t, n, boundary.gate_u, boundary.gate_u + boundary.gate_width,
               0.0, gate_h, -0.10, -0.05, "metal", "pedestrian_gate")
        for bar_u in np.arange(boundary.gate_u + 0.06,
                               boundary.gate_u + boundary.gate_width - 0.04, 0.12):
            mb.box(a, t, n, bar_u, bar_u + 0.02, 0.10, gate_h - 0.04, -0.11, -0.04,
                   "metal", "gate_flute")
    if style != "low" and boundary.garage_u is not None:
        mb.box(a, t, n, boundary.garage_u,
               boundary.garage_u + boundary.garage_width, 0.0, height * 0.9,
               -0.10, -0.05, "metal", "garage_door")
        for level in np.arange(0.12, height * 0.9 - 0.06, 0.16):
            mb.box(a, t, n, boundary.garage_u + 0.04,
                   boundary.garage_u + boundary.garage_width - 0.04, level,
                   level + 0.05, -0.11, -0.095, "metal", "garage_slat")


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
    styles = {
        "reja": ("plaster", "reja"),
        "fence": ("plaster", "reja"),
        "ladrillos": ("brick", "solid"),
        "concreto": ("plaster", "solid"),
        "concreto_bajo": ("plaster", "low"),
    }
    for index, boundary in enumerate(boundaries):
        coords = list(boundary.line.coords)
        tangent, normal, length = outward_normal(parcel, coords[0], coords[-1])
        if tangent is None:
            continue
        origin = np.asarray(coords[0], float)
        material, style = styles.get(boundary.kind, ("brick", "wall"))
        with mb.assembly(f"site/fence_{index:02d}"):
            draw_fence(mb, origin, tangent, normal, length, boundary, rng, material, style)

    for index, entrance in enumerate(entrances):
        with mb.assembly(f"site/entrance_{index:02d}"):
            entrance_step(mb, entrance, rng)

    with mb.assembly("site/garden"):
        return plant_garden(mb, parcel, built, boundaries, entrances, rng)
