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
    kind: str  # window | door | gate | balcony_window
    u_m: float  # borde izquierdo, distancia desde vertex_a en metros
    v_m: float  # posición vertical (base de la abertura)
    width_m: float
    height_m: float
    frame_width_m: float = 0.06
    recess_m: float = 0.08
    source: str = "assumed"
    view_id: str | None = None
    score: float = 0.0
    style: str = "sliding"  # sliding | casement | transom | paneled
    grille: bool = False
    mullion_columns: int = 2
    mullion_rows: int = 2
    balcony_depth_m: float = 0.75
    prefab: str = "legacy"  # slim_window | wood_panel | metal_gate | roller | storefront | louver
    curtain: float = 0.0  # fraction covered from the sides
    grille_pattern: str = "vertical"  # vertical | grid | diamond


@dataclass(frozen=True)
class FacadeMaterialRegion:
    """Rectangular finish zone in facade-local metres, behind any openings."""

    u_m: float
    v_m: float
    width_m: float
    height_m: float
    material_slot: str
    source: str = "assumed"
    score: float = 0.0


@dataclass(frozen=True)
class FacadeProjection:
    """Secondary mass attached to a facade, including curved canopy slabs."""

    kind: str  # panel | frame | ledge | canopy | curved_canopy
    u_m: float
    v_m: float
    width_m: float
    height_m: float
    depth_m: float
    material_slot: str = "accent"
    border_width_m: float = 0.18
    source: str = "assumed"
    score: float = 0.0
    label: str = ""  # optional relief lettering for sign panels


@dataclass(frozen=True)
class ExteriorStairSpecification:
    """Simple facade-anchored switchback stair occupying free parcel area."""

    u_m: float
    base_z_m: float
    target_z_m: float
    flight_width_m: float = 1.15
    run_m: float = 3.0
    step_count: int = 18
    switchback: bool = True
    material_slot: str = "accent"
    railing_material_slot: str = "metal"
    source: str = "assumed"
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
    cladding: str = "stucco"  # stucco | horizontal
    balcony_pattern: str = "vertical"  # vertical | diamond
    services: bool = False
    wall_material: str = "plaster"
    ground_floor_material: str | None = None
    material_regions: tuple[FacadeMaterialRegion, ...] = ()
    projections: tuple[FacadeProjection, ...] = ()
    exterior_stairs: tuple[ExteriorStairSpecification, ...] = ()
    ornamented: bool = True


@dataclass(frozen=True)
class SetbackSpecification:
    depth_m: float = 0.0
    surface: str = "pavement"
    boundary: str = "open"
    boundary_height_m: float = 1.8
    source: str = "assumed"
    edge_indices: tuple[int, ...] = ()  # parcel exterior after CCW normalization
    gate_width_m: float = 2.8


@dataclass(frozen=True)
class RoofSpecification:
    kind: str = "flat"
    slope_deg: float = 0.0
    parapet_height_m: float = 0.5
    source: str = "assumed"
    terrace_room: bool = True
    canopy: bool = True
    water_tank: bool = True



@dataclass(frozen=True)
class TextureSet:
    """A collection of PBR texture maps defining a material's surface."""

    name: str
    base_color_path: str | None = None
    normal_path: str | None = None
    orm_path: str | None = None
    roughness_path: str | None = None
    metallic_path: str | None = None
    ao_path: str | None = None
    scale_u: float = 1.0
    scale_v: float = 1.0
    normal_convention: str = "opengl"
    provenance: str = "unknown"


@dataclass(frozen=True)
class MaterialSpecification:
    """One semantic PBR material selected by the architectural grammar."""

    slot: str
    family: str
    base_color_rgb: tuple[float, float, float]
    roughness: float
    metallic: float = 0.0
    opacity: float = 1.0
    texture_set: str | None = None
    real_scale_m: float = 1.0
    normal_strength: float = 1.0
    weathering: float = 0.0
    source: str = "grammar_default"
    confidence: float = 0.0


@dataclass(frozen=True)
class BuildingAppearance:
    """Material vocabulary used by walls, openings, roofs and site surfaces."""

    materials: tuple[MaterialSpecification, ...] = ()
    source: str = "grammar_default"


@dataclass(frozen=True)
class BuildingSpecification:
    """Explicit geometry and rules consumed by the procedural mesh generator."""

    footprint_xy: tuple[tuple[float, float], ...]
    crs: str
    height: HeightEstimate
    facade_edges: tuple[FacadeSpecification, ...] = ()
    setback: SetbackSpecification | None = None
    roof: RoofSpecification = field(default_factory=RoofSpecification)
    metadata: dict[str, Any] = field(default_factory=dict)
    parcel_xy: tuple[tuple[float, float], ...] | None = None
    footprint_holes: tuple[tuple[tuple[float, float], ...], ...] = ()
    parcel_holes: tuple[tuple[tuple[float, float], ...], ...] = ()
    appearance: BuildingAppearance = field(default_factory=BuildingAppearance)
    seed: int = 0


@dataclass(frozen=True)
class MeshData:
    """Renderer-independent mesh representation for future OBJ/GLB exporters."""

    vertices: np.ndarray
    faces: np.ndarray
    uv: np.ndarray | None = None
    face_materials: np.ndarray | None = None
    materials: tuple[dict[str, Any], ...] = ()
    parts: tuple[dict[str, Any], ...] = ()
