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
class Opening:
    kind: str              # "window" | "door" | "gate"
    u_m: float             # posición horizontal en la fachada (centro o borde, definamos borde izquierdo por ahora)
    v_m: float             # posición vertical (base de la abertura)
    width_m: float
    height_m: float
    frame_width_m: float = 0.06
    recess_m: float = 0.08
    source: str = "assumed"
    view_id: str | None = None
    score: float = 0.0

@dataclass(frozen=True)
class FacadeSpecification:
    edge_id: str
    vertex_a: tuple[float, float]
    vertex_b: tuple[float, float]
    width_m: float
    normal_xy: tuple[float, float]
    floor_levels_m: tuple[float, ...]
    wall_color_rgb: tuple[int, int, int] = (200, 190, 170)
    openings: tuple[Opening, ...] = ()
    observed: bool = False
    is_front: bool = False
    assigned_views: tuple[str, ...] = ()

@dataclass(frozen=True)
class SetbackSpecification:
    depth_m: float = 0.0
    surface: str = "pavement"
    boundary: str = "open"
    boundary_height_m: float = 1.8
    source: str = "assumed"

@dataclass(frozen=True)
class RoofSpecification:
    kind: str = "flat"
    slope_deg: float = 0.0
    parapet_height_m: float = 0.5
    source: str = "assumed"

@dataclass(frozen=True)
class BuildingSpecification:
    """Geometry and rules consumed by the future procedural mesh generator."""
    footprint_xy: tuple[tuple[float, float], ...]
    crs: str
    height: HeightEstimate
    facade_edges: tuple[FacadeSpecification, ...] = ()
    setback: SetbackSpecification | None = None
    roof: RoofSpecification = field(default_factory=RoofSpecification)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MeshData:
    """Renderer-independent mesh representation for future OBJ/GLB exporters."""
    vertices: np.ndarray
    faces: np.ndarray
    uv: np.ndarray | None = None
    face_materials: np.ndarray | None = None
    materials: tuple[dict[str, Any], ...] = ()
