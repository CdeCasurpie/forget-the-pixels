"""Structural flat slabs, parapets and rooftop objects.

All designed coverings and slopes are emitted by roof_assembly. The historical
V4 planner supplies flat roofs only; it never invents a random tiled band.
"""

from __future__ import annotations

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from domain.architecture import RoofPlan, RoofProp, RoofSurface
from modeling.detail import DEFAULT_BUDGET
from modeling.geometry_constraints import (
    largest_polygon,
)
from modeling.mesh_builder import polygons
from modeling.prefabs_roof import BUILDERS, FOOTPRINTS, frame
from modeling.randomness import resolve_seed

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
    if mass.roof_spec is not None:
        kind=(mass.roof_spec.get('kind','flat') if isinstance(mass.roof_spec,dict)
              else mass.roof_spec.kind)
        if kind!='flat':
            raise ValueError('V4 roof must be flat; use theta roof_assemblies for catalog roofs')
    rng = np.random.default_rng(resolve_seed(seed, lot_id, mass.id, "roof", "plan"))
    roof_z = float(mass.roof_z)

    surfaces, flat_parts = [], []
    for part in polygons(exposed_area):
        if part.area < 0.5:
            continue
        remainder = part
        if remainder is not None and remainder.area > 0.5:
            surfaces.append(
                RoofSurface(
                    polygon=tuple(
                        (float(x), float(y)) for x, y in remainder.exterior.coords
                    ),
                    kind="flat",
                    base_z=roof_z,
                    holes=tuple(tuple(r.coords)[:-1] for r in remainder.interiors),
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


def build_roof(mb, plan, rng, *, slab_material='concrete'):
    """Emit one mass's flat slabs, parapet and objects."""
    with mb.assembly(f"roof/{plan.mass_id}"):
        _build_roof_body(mb, plan, rng, slab_material=slab_material)


def _build_roof_body(mb, plan, rng, *, slab_material='concrete'):
    flats = []
    for surface in plan.surfaces:
        polygon = Polygon(surface.polygon,surface.holes)
        if polygon.is_empty:
            continue
        if surface.kind == "flat":
            mb.solid(polygon, surface.base_z - surface.thickness_m, surface.base_z,
                     slab_material, "roof_slab")
            flats.append(polygon)
        else:
            raise ValueError('Basic roof surfaces must be flat; use a catalog roof assembly')

    if plan.parapet_height_m > 0 and flats:
        for field in polygons(unary_union(flats)):
            ring = field.difference(field.buffer(-0.14, join_style=2))
            for piece in polygons(ring):
                mb.solid(piece, plan.roof_z, plan.roof_z + plan.parapet_height_m,
                         "plaster", "parapet")
            if plan.parapet_profile == "cap":
                cap = field.difference(field.buffer(-0.19, join_style=2))
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
