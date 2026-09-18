"""Procedural geometry consumes explicit specifications, never raw images."""

from .specification import build_building_specification, write_building_specification
from .grammar import generate_mesh
from .layout import propose_building
from .io import read_specification
from .validation import validate_mesh

__all__ = [
    "build_building_specification",
    "write_building_specification",
    "generate_mesh",
    "propose_building",
    "read_specification",
    "validate_mesh",
]
