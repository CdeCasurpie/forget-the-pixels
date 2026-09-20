"""Translate measured reconstruction evidence into grammar-ready parameters."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from domain import BuildingSpecification, HeightEstimate, ReconstructionInput
from vision.estimation import regularize_height_to_floors


def build_building_specification(
    reconstruction_input: ReconstructionInput, height_fit: dict
) -> BuildingSpecification:
    """Build the neutral LOD1 specification; no mesh or architectural grammar yet."""
    regularized = regularize_height_to_floors(height_fit["height_m"])
    height = HeightEstimate(
        continuous_height_m=float(height_fit["height_m"]),
        reprojection_rmse_px=float(height_fit["rmse_normalized_px"]),
        used_pano_ids=tuple(height_fit.get("used_pano_ids", ())),
        regularized_height_m=regularized["regularized_height_m"],
        floor_count=regularized["floor_count"],
        floor_height_m=regularized["floor_height_m"],
        quality=str(height_fit.get("quality", "unreviewed")),
    )
    return BuildingSpecification(
        footprint_xy=reconstruction_input.lot.footprint_xy,
        crs=reconstruction_input.lot.crs,
        height=height,
        metadata={
            "objectid": reconstruction_input.lot.objectid,
            "alignment": reconstruction_input.alignment,
        },
    )


def write_building_specification(
    specification: BuildingSpecification, output: Path
) -> None:
    """Persist a grammar-ready specification without committing to a mesh format."""
    payload = {"schema_version": 3, **asdict(specification)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
