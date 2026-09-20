"""Infer parcel edges exposed to public space from neighbouring lot spacing."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import geopandas as gpd
import numpy as np
from shapely.geometry import Point, Polygon
from shapely.geometry.polygon import orient


@dataclass(frozen=True)
class StreetEdge:
    edge_index: int
    start_xy: tuple[float, float]
    end_xy: tuple[float, float]
    length_m: float
    outward_normal_xy: tuple[float, float]
    clear_sample_ratio: float
    minimum_clearance_m: float
    is_street_facing: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _validate_lots(lots: gpd.GeoDataFrame) -> None:
    if lots.empty or lots.crs is None or lots.crs.to_epsg() != 32718:
        raise ValueError("A nonempty cadastral GeoDataFrame in EPSG:32718 is required")
    if lots.geometry.is_empty.any() or not lots.geometry.is_valid.all():
        raise ValueError("All parcels must be valid nonempty geometries")


def street_facing_edges(
    lots: gpd.GeoDataFrame,
    lot_index,
    *,
    neighbour_clearance_m: float = 1.25,
    min_clear_sample_ratio: float = 2 / 3,
    samples_per_edge: int = 5,
    min_edge_length_m: float = 1.2,
) -> list[StreetEdge]:
    """Classify exterior edges using nearby parcels, rather than edge length.

    At interior samples of each exterior edge we step 5 cm outward, then measure
    the nearest other parcel. At least 2/3 must be clear. It reliably excludes
    shared walls and narrow passages, but is a public-space candidate—not an
    authoritative road-centerline dataset.
    """
    _validate_lots(lots)
    if lot_index not in lots.index:
        raise KeyError(f"Unknown lot index: {lot_index}")
    if not (
        math.isfinite(neighbour_clearance_m)
        and neighbour_clearance_m > 0
        and 0 < min_clear_sample_ratio <= 1
        and isinstance(samples_per_edge, int)
        and samples_per_edge >= 3
        and math.isfinite(min_edge_length_m)
        and min_edge_length_m > 0
    ):
        raise ValueError("Invalid street-edge thresholds")
    polygon = lots.loc[lot_index].geometry
    if polygon.geom_type != "Polygon":
        raise ValueError("Street-edge inference currently requires a Polygon lot")
    polygon = orient(polygon, sign=1.0)
    coords = list(polygon.exterior.coords)
    sindex = lots.sindex
    fractions = np.linspace(0.12, 0.88, samples_per_edge)
    result: list[StreetEdge] = []
    for edge_index, (start, end) in enumerate(zip(coords[:-1], coords[1:])):
        start_xy, end_xy = np.asarray(start[:2], float), np.asarray(end[:2], float)
        tangent = end_xy - start_xy
        length = float(np.linalg.norm(tangent))
        if length <= 1e-9:
            continue
        tangent /= length
        # Exterior of a counter-clockwise ring is on its right.
        outward = np.array([tangent[1], -tangent[0]])
        envelope = Polygon(
            [
                start_xy - outward * 0.05,
                end_xy - outward * 0.05,
                end_xy + outward * (neighbour_clearance_m + 0.1),
                start_xy + outward * (neighbour_clearance_m + 0.1),
            ]
        ).envelope
        positions = sindex.query(envelope, predicate="intersects")
        neighbours = [
            lots.iloc[int(position)].geometry
            for position in positions
            if lots.iloc[int(position)].name != lot_index
        ]
        clearances = []
        for fraction in fractions:
            probe = Point(start_xy + tangent * (fraction * length) + outward * 0.05)
            clearance = (
                min(
                    (probe.distance(other) for other in neighbours),
                    default=float("inf"),
                )
                + 0.05
            )
            clearances.append(clearance)
        ratio = float(np.mean(np.asarray(clearances) >= neighbour_clearance_m))
        result.append(
            StreetEdge(
                edge_index=edge_index,
                start_xy=tuple(start_xy),
                end_xy=tuple(end_xy),
                length_m=length,
                outward_normal_xy=tuple(outward),
                clear_sample_ratio=ratio,
                minimum_clearance_m=float(min(clearances)),
                is_street_facing=bool(
                    length >= min_edge_length_m and ratio >= min_clear_sample_ratio
                ),
            )
        )
    return result


def annotate_street_fronts(lots: gpd.GeoDataFrame, **thresholds) -> gpd.GeoDataFrame:
    """Return a copy with JSON-compatible exposed-edge records for every lot."""
    _validate_lots(lots)
    annotated = lots.copy()
    records = [
        [edge.to_dict() for edge in street_facing_edges(annotated, index, **thresholds)]
        for index in annotated.index
    ]
    annotated["street_edges"] = records
    annotated["street_edge_indices"] = [
        [edge["edge_index"] for edge in edges if edge["is_street_facing"]]
        for edges in records
    ]
    return annotated
