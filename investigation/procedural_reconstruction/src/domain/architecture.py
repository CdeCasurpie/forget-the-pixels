from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class EvidenceValue:
    value: Any
    source: str
    confidence: float
    view_ids: tuple[str, ...] = ()
    locked: bool = False

@dataclass(frozen=True)
class BuildingProgram:
    use: str
    occupancy: str
    placement: str
    architectural_language: str
    finish_profile: str
    maintenance: str
    construction_state: str
    seed: int
    front_setback: float = 0.0
    side_setback: float = 0.0
    primary_color: tuple[float, float, float] = (0.8, 0.8, 0.8)
    side_wall_finish: str = "raw"
    has_fence: bool = True
    fence_type: str = "reja"
    is_corner: bool = False

@dataclass(frozen=True)
class ParcelContext:
    polygon: tuple[tuple[float, float], ...]
    holes: tuple[tuple[tuple[float, float], ...], ...] = ()
    crs: str = "EPSG:32718"
    local_origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    neighbor_ids: tuple[str, ...] = ()
    explicit_fronts: tuple[int, ...] = ()
    terrain_datum: float = 0.0

@dataclass(frozen=True)
class EdgeRef:
    id: str
    endpoints: tuple[tuple[float, float], tuple[float, float]]
    ring_id: int
    orientation: int

@dataclass(frozen=True)
class MassSpec:
    id: str
    footprint: tuple[tuple[float, float], ...]
    base_z: float
    roof_z: float
    floor_levels: tuple[float, ...]
    role: str
    roof_spec: Any
    parent_ids: tuple[str, ...] = ()
    support_ids: tuple[str, ...] = ()

@dataclass(frozen=True)
class FacadeSpecV4:
    mass_id: str
    edge_ref: EdgeRef
    exposed_intervals: tuple[tuple[float, float], ...]
    floor_ranges: tuple[tuple[int, int], ...]
    bays: tuple[Any, ...]
    openings: tuple[Any, ...]
    material_regions: tuple[Any, ...]

@dataclass(frozen=True)
class ComponentRecord:
    id: str
    semantic: str
    mass_id: str
    parent_id: str
    support_ids: tuple[str, ...]
    local_transform: tuple[float, ...]  # 4x4 matrix flattened
    collision_class: str
    mesh_slice: tuple[int, int]

@dataclass(frozen=True)
class RoofSurface:
    """One continuous roof plane over part of a mass.

    A sloped surface rises from `eave_point` along `inward_normal`, so a tile
    apron can hang below the wall head over the pavement while the same plane
    climbs to a ridge inside the lot.
    """
    polygon: tuple[tuple[float, float], ...]
    kind: str  # flat | tile_shed | corrugated
    base_z: float
    slope_deg: float = 0.0
    eave_point: tuple[float, float] = (0.0, 0.0)
    inward_normal: tuple[float, float] = (0.0, 1.0)
    thickness_m: float = 0.14


@dataclass(frozen=True)
class RoofProp:
    """One object standing on a roof, placed in world XY."""
    kind: str
    position: tuple[float, float]
    rotation_deg: float = 0.0
    scale: float = 1.0
    seed: int = 0


@dataclass(frozen=True)
class RoofPlan:
    mass_id: str
    surfaces: tuple[RoofSurface, ...]
    props: tuple[RoofProp, ...] = ()
    parapet_height_m: float = 0.5
    parapet_profile: str = "cap"  # none | cap
    roof_z: float = 0.0


@dataclass(frozen=True)
class SitePlan:
    masses: tuple[MassSpec, ...]
    free_space: tuple[tuple[float, float], ...]
    access_nodes: tuple[Any, ...]
    boundaries: tuple[Any, ...]
    exclusion_zones: tuple[Any, ...]

@dataclass(frozen=True)
class BuildingSpecificationV4:
    program: BuildingProgram
    context: ParcelContext
    site_plan: SitePlan
    facades: tuple[FacadeSpecV4, ...]
    components: tuple[ComponentRecord, ...]
    seed: int
