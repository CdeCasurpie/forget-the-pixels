import sys; sys.path.insert(0, 'src')
from procedural_modeling.mesh_builder import MeshBuilder
original_solid = MeshBuilder.solid
def logging_solid(self, shape, bottom, top, material="plaster", semantic="wall", **kwargs):
    clipped = shape.intersection(self.parcel)
    if semantic == "wall" and material == "concrete":
        print(f"CONCRETE WALL: shape={list(shape.exterior.coords)}")
        print(f"  intersection area: {clipped.area}")
    original_solid(self, shape, bottom, top, material, semantic, **kwargs)
MeshBuilder.solid = logging_solid
import debug_walls
