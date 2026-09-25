"""Experimental architectural target, NOT theta-v1. Distances are local metres.

Null is unknown; empty entity tuples are observed absence. Evidence lives outside
the generation values. Strict decoding rejects misspelled/unsupported fields.
"""
from __future__ import annotations

import json
import math
import types
from numbers import Real
from dataclasses import asdict, dataclass, fields, is_dataclass, field
from typing import Any, Union, get_args, get_origin, get_type_hints

from domain.models import Opening, FacadeProjection, FacadeMaterialRegion, ExteriorStairSpecification


@dataclass(frozen=True)
class ReconstructionContext:
    parcel: tuple[tuple[float, float], ...]
    fronts: tuple[int, ...]
    crs: str = "EPSG:32718"
    metric_origin: tuple[float, float, float] = (0., 0., 0.)
    locked_height_m: float | None = None


@dataclass(frozen=True)
class Observation:
    view_id: str
    image_path: str
    camera_xyz: tuple[float, float, float] | None = None
    heading_pitch_roll_deg: tuple[float, float, float] | None = None
    timestamp: str | None = None


@dataclass(frozen=True)
class Evidence:
    state: str  # observed | inferred | unknown | externally_known
    confidence: float | None = None
    view_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class MassingControls:
    pattern: str | None = None
    front_setback_m: float | None = None
    upper_setback_m: float | None = None
    podium_floors: int | None = None
    front_depth_m: float | None = None
    low_floors: int | None = None
    corner_reach_m: float | None = None


@dataclass(frozen=True)
class ArchitecturalMass:
    role: str
    footprint: tuple[tuple[float, float], ...]
    levels_m: tuple[float, ...]  # authoritative; base/roof/floors are derived


@dataclass(frozen=True)
class OpeningEdit:
    """Sparse correction of one generated bay on one local storey."""
    floor: int
    bay: int
    action: str  # suppress | replace
    opening: Opening | None = None


@dataclass(frozen=True)
class FacadeControls:
    mode: str = "repeat"  # explicit replaces ALL repeated entities on that edge
    bay_count: int | None = None
    bay_axes_m: tuple[float, ...] | None = None
    window_ratio: float | None = None
    window_height_m: float | None = None
    sill_m: float | None = None
    balconies: bool | None = None
    balcony_depth_m: float | None = None
    gallery_depth_m: float | None = None
    awning_depth_m: float | None = None
    cladding: str | None = None
    services: bool | None = None
    openings: tuple[Opening, ...] | None = None
    projections: tuple[FacadeProjection, ...] | None = None
    material_regions: tuple[FacadeMaterialRegion, ...] | None = None
    stairs: tuple[ExteriorStairSpecification, ...] | None = None
    opening_edits: tuple[OpeningEdit, ...] | None = None
    added_openings: tuple[Opening, ...] | None = None


@dataclass(frozen=True)
class FacadeOverride:
    mass_role: str
    edge: int  # canonical CCW mass ring, starting at lexicographically smallest vertex
    controls: FacadeControls


@dataclass(frozen=True)
class RoofControls:
    kind: str | None = None
    parapet_m: float | None = None
    slope_deg: float | None = None
    props: tuple[RoofObject, ...] | None = None


@dataclass(frozen=True)
class RoofOverride:
    mass_ref: str  # canonical role:index; unique legacy role accepted on input
    kind: str | None = None
    parapet_m: float | None = None
    slope_deg: float | None = None


@dataclass(frozen=True)
class RoofObject:
    mass_role: str
    kind: str
    xy: tuple[float, float]
    rotation_deg: float = 0.
    scale: float = 1.


@dataclass(frozen=True)
class FenceRun:
    edge: int  # canonical parcel edge
    start_m: float
    end_m: float
    kind: str
    height_m: float
    gate_u: float | None = None
    gate_width: float = 0.
    garage_u: float | None = None
    garage_width: float = 0.


@dataclass(frozen=True)
class SiteControls:
    fence: str | None = None  # none | reja | concreto | ladrillos | concreto_bajo
    garden: bool | None = None
    runs: tuple[FenceRun, ...] | None = None  # explicit runs replace automatic fences


@dataclass(frozen=True)
class MaterialControl:
    slot: str
    template: str  # existing material slot as physical/texture template
    color: tuple[float, float, float] | None = None


@dataclass(frozen=True)
class ThetaCandidate:
    schema_version: str = "0.2"
    height_m: float | None = None
    floors: int | None = None
    family: str | None = None
    massing: MassingControls = field(default_factory=MassingControls)
    facade: FacadeControls = field(default_factory=FacadeControls)
    facades: tuple[FacadeOverride, ...] = ()
    roof: RoofControls = field(default_factory=RoofControls)
    roofs: tuple[RoofOverride, ...] = ()
    site: SiteControls = field(default_factory=SiteControls)
    primary_color: tuple[float, float, float] | None = None
    side_material: str | None = None
    masses: tuple[ArchitecturalMass, ...] | None = None
    materials: tuple[MaterialControl, ...] = ()
    finish: str | None = None


@dataclass(frozen=True)
class NuisanceParameters:
    seed: int = 0
    curtains: bool = True


@dataclass(frozen=True)
class GrammarConfig:
    implementation: str = "theta-candidate-v0"
    grammar_reference: str = "grammar-v1.0"
    completion_policy: str = "conservative-0.2"
    detail: int = 2


@dataclass(frozen=True)
class ReconstructionRequest:
    context: ReconstructionContext
    theta: ThetaCandidate
    nuisance: NuisanceParameters = field(default_factory=NuisanceParameters)
    config: GrammarConfig = field(default_factory=GrammarConfig)
    observations: tuple[Observation, ...] = ()
    evidence: dict[str, Evidence] = field(default_factory=dict)


def decode(cls, value, path="$ "):
    """Recursive strict typed JSON decoder, also used to validate dataclass input."""
    origin, args = get_origin(cls), get_args(cls)
    if cls is Any:
        if value is not None:
            raise ValueError(path + ": legacy opaque fields must remain null")
        return None
    if origin in (Union, types.UnionType):
        for option in args:
            try:
                return decode(option, value, path)
            except (ValueError, TypeError):
                pass
        raise ValueError(f"{path}: incompatible value {value!r}")
    if cls is type(None):
        if value is not None:
            raise ValueError(path + ": expected null")
        return None
    if is_dataclass(cls):
        if not isinstance(value, dict):
            raise ValueError(path + ": expected object")
        names = {f.name for f in fields(cls)}
        if set(value) - names:
            raise ValueError(f"{path}: unsupported fields {sorted(set(value)-names)}")
        hints = get_type_hints(cls)
        return cls(**{k: decode(hints[k], v, path + "." + k) for k, v in value.items()})
    if origin is tuple:
        if not isinstance(value, (list, tuple)):
            raise ValueError(path + ": expected array")
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(decode(args[0], v, f"{path}[{i}]") for i, v in enumerate(value))
        if len(value) != len(args):
            raise ValueError(path + ": wrong array length")
        return tuple(decode(t, v, path) for t, v in zip(args, value))
    if origin is dict:
        if not isinstance(value, dict):
            raise ValueError(path + ": expected mapping")
        return {decode(args[0], k, path): decode(args[1], v, path + "." + k) for k, v in value.items()}
    if cls is float:
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
            raise ValueError(path + ": expected finite number")
        return float(value)
    if type(value) is not cls:
        raise ValueError(path + f": expected {cls.__name__}")
    return value


def canonical(value) -> str:
    normalized = decode(type(value), asdict(value))
    return json.dumps(asdict(normalized), sort_keys=True, separators=(",", ":"), allow_nan=False)


def from_json(text: str) -> ReconstructionRequest:
    return decode(ReconstructionRequest, json.loads(text))
