"""Future procedural grammar consumes a BuildingSpecification, never raw images."""

from .specification import build_building_specification, write_building_specification

__all__ = ["build_building_specification", "write_building_specification"]
