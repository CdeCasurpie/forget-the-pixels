import sys; sys.path.insert(0, 'src')
from procedural_modeling.mesh_builder import MeshBuilder
original_box = MeshBuilder.box
def logging_box(self, a, t, n, u1, u2, z1, z2, w1, w2, material="plaster", semantic="wall", **kwargs):
    if semantic == "wall":
        print(f"WALL BOX: mat={material}, u=({u1}, {u2}), z=({z1}, {z2}), w=({w1}, {w2})")
    original_box(self, a, t, n, u1, u2, z1, z2, w1, w2, material, semantic, **kwargs)
MeshBuilder.box = logging_box
import debug_walls
