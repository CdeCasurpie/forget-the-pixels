"""Perimeter treatment of a lot: which edges get a fence, a wall or nothing."""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from domain.architecture import BuildingProgram, ParcelContext, SitePlan
from domain.theta import PlinthControls
from domain.fence_catalog import validate_fence_style

MIN_BOUNDARY_LENGTH_M = 0.8
GATE_WIDTH_M = 1.1
GARAGE_WIDTH_M = 2.9


@dataclass
class BoundarySpec:
    line: LineString
    kind: str  # domain.fence_catalog.FENCE_STYLES
    height: float
    gate_u: Optional[float] = None
    gate_width: float = 0.0
    garage_u: Optional[float] = None
    garage_width: float = 0.0
    is_street: bool = False
    height_mode: str = 'high'
    wall_material: str = 'plaster'
    gate_mode: str = 'auto'
    garage_mode: str = 'auto'
    openness: float = .3
    planters: bool = False
    plinth: PlinthControls | None = None
    base_height_m: float | None = None
    # Physical topology, independent of ``kind`` (the local style). 'auto' keeps
    # the style-driven choice; 'solid' is a plain wall, 'open' a thin base with
    # open infill, 'base_and_rail' a tall base with infill on top.
    form: str = 'auto'


def _segments(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "LineString":
        return [geometry]
    return [part for part in getattr(geometry, "geoms", []) if part.length > 0]


def generate_boundaries(
    context: ParcelContext, program: BuildingProgram, site_plan: SitePlan
) -> List[BoundarySpec]:
    """Fences on the stretches of lot edge no building already occupies.

    Street frontage is read from the parcel's declared front edges. It used to be
    inferred by testing whether the segment lay near y = 0, which only held for
    lots that happened to be axis-aligned and centred on the origin.
    """
    fence_kind = program.fence_type
    if fence_kind != "none":
        validate_fence_style(fence_kind)
    if not program.has_fence or fence_kind == "none":
        return []

    parcel = Polygon(context.polygon)
    masses = [Polygon(mass.footprint,mass.footprint_holes) for mass in site_plan.masses
              if mass.base_z<.01 and mass.kind=='enclosed']
    built = unary_union(masses) if masses else Polygon()

    coords = list(parcel.exterior.coords)
    street_edges = set(context.explicit_fronts)
    boundaries: List[BoundarySpec] = []

    for index in range(len(coords) - 1):
        edge = LineString([coords[index], coords[index + 1]])
        free = edge if built.is_empty else edge.difference(built.buffer(1e-4))
        for segment in _segments(free):
            if segment.length < MIN_BOUNDARY_LENGTH_M:
                continue
            if index in street_edges:
                gate_u = max(0.25, segment.length * 0.15) if segment.length>=GATE_WIDTH_M+.5 else None
                garage_u = None
                if gate_u is not None and segment.length > gate_u + GATE_WIDTH_M + GARAGE_WIDTH_M + 0.6:
                    garage_u = gate_u + GATE_WIDTH_M + 0.4
                boundaries.append(
                    BoundarySpec(
                        line=segment,
                        kind=fence_kind,
                        height=2.1,
                        gate_u=gate_u,
                        gate_width=GATE_WIDTH_M if gate_u is not None else 0.,
                        garage_u=garage_u,
                        garage_width=GARAGE_WIDTH_M if garage_u is not None else 0.0,
                        is_street=True,
                    )
                )
            else:
                # A party edge with no building on it still needs a blind wall,
                # otherwise the back yard opens straight into the neighbour.
                boundaries.append(
                    BoundarySpec(line=segment, kind="clasico", height=2.6,
                                 wall_material="brick")
                )
    return boundaries
