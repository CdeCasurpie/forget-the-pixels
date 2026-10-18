import trimesh
import json
import numpy as np

scene = trimesh.load("outputs/cuadras_completas/cuadra_completa.glb", force='scene')

lot_meshes = []
for name, geom in scene.geometry.items():
    if "lot_1850" in name or name.startswith("lot_1850"):
        lot_meshes.append((name, geom))

if not lot_meshes:
    print("Could not find names with lot_1850 in geometry. Checking graph nodes...")
    for node_name, node in scene.graph.nodes.items():
        if "lot_1850" in str(node_name):
            print(f"Found node: {node_name}")
            if hasattr(node, 'geometry') and node.geometry is not None:
                lot_meshes.append((node_name, scene.geometry[node.geometry]))

for name, geom in lot_meshes:
    bounds = geom.bounds
    print(f"{name}: bounds y {bounds[0][1]:.2f} to {bounds[1][1]:.2f}")

