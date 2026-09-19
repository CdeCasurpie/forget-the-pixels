"""Stable data contracts shared by the urban reconstruction pipeline."""

from .models import (
    Alignment2D,
    BuildingAppearance,
    BuildingSpecification,
    CameraPose,
    ExteriorStairSpecification,
    FacadeMaterialRegion,
    FacadeProjection,
    FacadeSpecification,
    HeightEstimate,
    LotGeometry,
    MeshData,
    MaterialSpecification,
    Opening,
    PanoramaView,
    ReconstructionInput,
    RoofObservation,
    TextureSet,
)

__all__ = [
    "Alignment2D", "BuildingAppearance", "BuildingSpecification", "CameraPose",
    "ExteriorStairSpecification", "FacadeMaterialRegion", "FacadeProjection",
    "FacadeSpecification", "HeightEstimate", "LotGeometry", "MaterialSpecification",
    "MeshData", "Opening", "PanoramaView", "ReconstructionInput", "RoofObservation", "TextureSet",
]
