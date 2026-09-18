"""Typed, serializable contracts independent from CLI, plotting, and export."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class LotGeometry:
    objectid: int
    crs: str
    footprint_xy: tuple[tuple[float, float], ...]
    source_row: int | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CameraPose:
    latitude: float
    longitude: float
    heading_deg: float
    pitch_deg: float | None = None
    roll_deg: float | None = None
    camera_height_m: float = 2.5


@dataclass(frozen=True)
class PanoramaView:
    pano_id: str
    image_path: Path
    pose: CameraPose
    capture_date: str | None = None
    capture_year: int | None = None
    cylindrical_path: Path | None = None
    target_bearing_deg: float | None = None
    relative_yaw_deg: float | None = None
    camera_to_lot_m: float | None = None


@dataclass(frozen=True)
class Alignment2D:
    east_m: float = 0.0
    north_m: float = 0.0
    camera_height_m: float = 2.5
    source: str = "unverified"


@dataclass(frozen=True)
class ReconstructionInput:
    """Everything known before inferring a building from multiple views."""
    lot: LotGeometry
    views: tuple[PanoramaView, ...]
    alignment: Alignment2D
    projection: dict[str, Any] = field(default_factory=dict)
    satellite_image_path: Path | None = None


@dataclass(frozen=True)
class RoofObservation:
    pano_id: str
    target_xy: tuple[float, float]
    yaw_deg: float
    column_x: float
    cut_y: float
    base_y: float
    image_width: int
    image_height: int
    distance_m: float
    separation: float
    usable: bool
    individual_height_m: float


@dataclass(frozen=True)
class HeightEstimate:
    continuous_height_m: float
    reprojection_rmse_px: float
    used_pano_ids: tuple[str, ...]
    regularized_height_m: float | None = None
    floor_count: int | None = None
    floor_height_m: float | None = None
    quality: str = "unreviewed"


@dataclass(frozen=True)
class BuildingSpecification:
    """Geometry and rules consumed by the future procedural mesh generator."""
    footprint_xy: tuple[tuple[float, float], ...]
    crs: str
    height: HeightEstimate
    facade_edges: tuple[dict[str, Any], ...] = ()
    roof: dict[str, Any] = field(default_factory=lambda: {"kind": "flat"})
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MeshData:
    """Renderer-independent mesh representation for future OBJ/GLB exporters."""
    vertices: np.ndarray
    faces: np.ndarray
    uv: np.ndarray | None = None
    face_materials: np.ndarray | None = None
    materials: tuple[dict[str, Any], ...] = ()
