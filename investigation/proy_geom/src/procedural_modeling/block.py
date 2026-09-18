"""Batch contracts for rebuilding a small cadastral street area.

It does not invent height. Lots without an accepted height record are retained
in the manifest as skipped, making missing measurements visible to the caller.
"""

from __future__ import annotations

from dataclasses import asdict, replace
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.affinity import translate
from shapely.geometry.polygon import orient

from cadastral_geometry.street_fronts import street_facing_edges
from domain.models import HeightEstimate
from .layout import propose_building


def load_height_fits(paths: list[Path]) -> dict[int, HeightEstimate]:
    """Read Step 9 `height_fit.json` files keyed by their cadastral objectid."""
    fits: dict[int, HeightEstimate] = {}
    for path in paths:
        data = json.loads(Path(path).read_text())
        if "objectid" not in data or "height_m" not in data:
            raise ValueError(f"{path} is not a Step 9 height-fit record")
        regularization = data.get("procedural_regularization", {})
        continuous = float(data["height_m"])
        regularized = regularization.get("regularized_height_m")
        if not np.isfinite(continuous) or continuous <= 0:
            raise ValueError(f"{path} has invalid height")
        if regularized is not None and (
            not np.isfinite(regularized) or regularized <= 0
        ):
            raise ValueError(f"{path} has invalid regularized height")
        objectid = int(data["objectid"])
        if objectid in fits:
            raise ValueError(f"Duplicate height fit for objectid {objectid}")
        fits[objectid] = HeightEstimate(
            continuous_height_m=continuous,
            reprojection_rmse_px=float(data.get("rmse_normalized_px", 0.0)),
            used_pano_ids=tuple(data.get("used_pano_ids", ())),
            regularized_height_m=(
                float(regularized) if regularized is not None else None
            ),
            floor_count=regularization.get("floor_count"),
            floor_height_m=regularization.get("floor_height_m"),
            quality=str(data.get("quality", "unreviewed")),
        )
    return fits


def select_block_lots(
    lots: gpd.GeoDataFrame, objectid: int, radius_m: float, objectid_column="objectid"
) -> gpd.GeoDataFrame:
    """Select a deterministic local working area around one cadastral lot."""
    if lots.crs is None or lots.crs.to_epsg() != 32718:
        raise ValueError("Lots must be projected to EPSG:32718")
    if objectid_column not in lots:
        raise KeyError(f"Missing object id column: {objectid_column}")
    if not np.isfinite(radius_m) or radius_m <= 0:
        raise ValueError("radius_m must be positive and finite")
    target = lots[lots[objectid_column] == objectid]
    if len(target) != 1:
        raise ValueError(f"Expected exactly one lot for {objectid_column}={objectid}")
    centre = target.geometry.iloc[0].centroid
    selected = lots[lots.geometry.intersects(centre.buffer(radius_m))].copy()
    return selected.sort_values(objectid_column)


def build_block_specifications(
    lots: gpd.GeoDataFrame,
    heights: dict[int, HeightEstimate],
    *,
    objectid_column="objectid",
    seed=42,
    setback_m=0.4,
    neighbour_clearance_m=1.25,
) -> tuple[list[tuple[int, object, tuple[float, float]]], list[dict]]:
    """Return local grammar specs and an explicit report for every input lot.

    The generated local meshes carry `local_origin_utm` metadata. A renderer or
    exporter can restore global location without exposing UTM-scale coordinates
    to the modeling kernel.
    """
    if objectid_column not in lots:
        raise KeyError(f"Missing object id column: {objectid_column}")
    specs, report = [], []
    for lot_index, row in lots.sort_values(objectid_column).iterrows():
        objectid = int(row[objectid_column])
        if row.geometry.geom_type != "Polygon":
            report.append(
                {"objectid": objectid, "status": "skipped", "reason": "non_polygon"}
            )
            continue
        fronts = street_facing_edges(
            lots, lot_index, neighbour_clearance_m=neighbour_clearance_m
        )
        front_indices = tuple(
            edge.edge_index for edge in fronts if edge.is_street_facing
        )
        if not front_indices:
            report.append(
                {
                    "objectid": objectid,
                    "status": "skipped",
                    "reason": "no_street_facing_edge",
                }
            )
            continue
        height = heights.get(objectid)
        if height is None:
            report.append(
                {
                    "objectid": objectid,
                    "status": "skipped",
                    "reason": "missing_height",
                    "street_edge_indices": list(front_indices),
                }
            )
            continue
        polygon = orient(row.geometry, sign=1.0)
        origin = polygon.centroid
        local = translate(polygon, xoff=-origin.x, yoff=-origin.y)
        floors = height.floor_count or max(
            1, round((height.regularized_height_m or height.continuous_height_m) / 2.8)
        )
        minimum_dimension = min(
            local.bounds[2] - local.bounds[0], local.bounds[3] - local.bounds[1]
        )
        style = (
            "corner"
            if len(front_indices) > 1
            else ("narrow" if minimum_dimension < 6 else "courtyard")
        )
        height_m = height.regularized_height_m or height.continuous_height_m
        try:
            spec = propose_building(
                local,
                front_edges=front_indices,
                floors=floors,
                height_m=height_m,
                style=style,
                seed=seed + objectid,
                setback_m=setback_m,
                boundary="open",
                objectid=objectid,
            )
        except ValueError as error:
            report.append(
                {
                    "objectid": objectid,
                    "status": "skipped",
                    "reason": f"grammar_rejected: {error}",
                    "street_edge_indices": list(front_indices),
                }
            )
            continue
        spec = replace(
            spec,
            height=height,
            metadata={
                **spec.metadata,
                "local_origin_utm": [origin.x, origin.y],
                "street_edge_indices": list(front_indices),
                "street_front_method": "outward_clearance_to_neighbouring_parcels",
            },
        )
        specs.append((objectid, spec, (origin.x, origin.y)))
        report.append(
            {
                "objectid": objectid,
                "status": "generated",
                "street_edge_indices": list(front_indices),
                "height_m": height_m,
                "height_quality": height.quality,
                "style": style,
            }
        )
    return specs, report
