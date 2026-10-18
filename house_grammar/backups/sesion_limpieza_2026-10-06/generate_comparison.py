import sys
import shapely
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
from shapely.geometry import Polygon, LineString, Point
from domain.theta import ThetaCandidate, MassingControls, SiteControls, ReconstructionContext
from modeling.theta import generate_from_theta
from domain.theta import NuisanceParameters
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

def render_mesh(mesh_data, out_png):
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_subplot(111, projection='3d')
    polygons = [mesh_data.vertices[face] for face in mesh_data.faces]
    
    # Simple shading: color walls based on normal
    facecolors = []
    for face in mesh_data.faces:
        v0, v1, v2 = mesh_data.vertices[face]
        normal = np.cross(v1 - v0, v2 - v0)
        n_len = np.linalg.norm(normal)
        if n_len > 0: normal /= n_len
        # Light direction
        light = np.array([0.5, -0.5, 0.7])
        light /= np.linalg.norm(light)
        intensity = np.dot(normal, light) * 0.5 + 0.5
        c = 0.3 + 0.5 * intensity
        facecolors.append([c, c, c+0.1, 1.0])

    collection = Poly3DCollection(polygons, facecolors=facecolors, linewidths=0.5, edgecolors='k', alpha=1.0)
    ax.add_collection3d(collection)

    max_range = np.array([
        mesh_data.vertices[:,0].max() - mesh_data.vertices[:,0].min(),
        mesh_data.vertices[:,1].max() - mesh_data.vertices[:,1].min(),
        mesh_data.vertices[:,2].max() - mesh_data.vertices[:,2].min()
    ]).max() / 2.0
    mid_x = (mesh_data.vertices[:,0].max() + mesh_data.vertices[:,0].min()) * 0.5
    mid_y = (mesh_data.vertices[:,1].max() + mesh_data.vertices[:,1].min()) * 0.5
    mid_z = (mesh_data.vertices[:,2].max() + mesh_data.vertices[:,2].min()) * 0.5

    ax.set_xlim(mid_x - max_range, mid_x + max_range)
    ax.set_ylim(mid_y - max_range, mid_y + max_range)
    ax.set_zlim(mid_z - max_range, mid_z + max_range)
    ax.view_init(elev=25, azim=-60)
    ax.axis('off')
    plt.savefig(out_png, dpi=200, bbox_inches='tight', pad_inches=0)
    plt.close()

def main():
    # Irregular lot (added 1e-13 to trigger float precision bug)
    parcel_coords = [(0.0, 0.0), (10.0000000000001, 0.0), (10.0000000000001, 20.0), (0.0, 20.0)]
    fronts = (0,)
    m = MassingControls(
        pattern="front_tall_rear_low", front_setback_m=3.0,
        upper_setback_m=None, front_depth_m=6.0,
        low_floors=1, podium_floors=None
    )
    theta = ThetaCandidate(
        height_m=6.0, floors=2, family="mixed_use", primary_color=(1,1,1),
        massing=m, schema_version="0.2"
    )
    ctx = ReconstructionContext(parcel=tuple(parcel_coords), fronts=fronts)
    nuisance = NuisanceParameters(seed=42)
    mesh_data = generate_from_theta(ctx, theta, nuisance)
    render_mesh(mesh_data, sys.argv[1])

if __name__ == "__main__":
    main()
