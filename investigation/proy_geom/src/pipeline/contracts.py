"""Public API types. The reconstruct_building implementation comes after grammar design."""
from dataclasses import dataclass

from domain import BuildingSpecification, MeshData, ReconstructionInput


@dataclass(frozen=True)
class ReconstructionConfig:
    floor_height_m: float = 2.8
    use_satellite_footprint: bool = False


@dataclass(frozen=True)
class ReconstructionResult:
    input: ReconstructionInput
    specification: BuildingSpecification
    mesh: MeshData | None = None
