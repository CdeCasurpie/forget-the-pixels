import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
from domain.theta import ThetaCandidate, MassingControls, SiteControls, ReconstructionContext
from modeling.theta import generate_from_theta
import numpy as np
import trimesh

parcel_coords = [(0, 0), (10, 0), (10, 20), (0, 20)]
fronts = (0,)

massing = MassingControls(
    pattern="front_tall_rear_low", front_setback_m=3.0,
    upper_setback_m=None, front_depth_m=6.0,
    low_floors=1, podium_floors=None
)
theta = ThetaCandidate(
    height_m=6.0, floors=2, family="mixed_use", primary_color=(0.8, 0.2, 0.2),
    massing=massing, schema_version="0.2"
)
ctx = ReconstructionContext(parcel=tuple(parcel_coords), fronts=fronts)

mesh_data = generate_from_theta(ctx, theta)

scene = trimesh.Scene()
scene.add_geometry(trimesh.Trimesh(vertices=mesh_data.vertices, faces=mesh_data.faces))
scene.export("bug_test.glb")
print("Exported bug_test.glb")
