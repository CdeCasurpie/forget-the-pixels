import sys
import trimesh
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

scene = trimesh.load(sys.argv[1], force='scene')

fig = plt.figure(figsize=(10, 10))
ax = fig.add_subplot(111, projection='3d')

all_vertices = []
for name, geom in scene.geometry.items():
    vertices = geom.vertices
    faces = geom.faces
    all_vertices.append(vertices)
    
    polygons = [vertices[face] for face in faces]
    collection = Poly3DCollection(polygons, facecolors='lightgray', linewidths=0.2, edgecolors='k', alpha=0.9)
    ax.add_collection3d(collection)

all_vertices = np.vstack(all_vertices)
max_range = np.array([
    all_vertices[:,0].max() - all_vertices[:,0].min(),
    all_vertices[:,1].max() - all_vertices[:,1].min(),
    all_vertices[:,2].max() - all_vertices[:,2].min()
]).max() / 2.0

mid_x = (all_vertices[:,0].max() + all_vertices[:,0].min()) * 0.5
mid_y = (all_vertices[:,1].max() + all_vertices[:,1].min()) * 0.5
mid_z = (all_vertices[:,2].max() + all_vertices[:,2].min()) * 0.5

ax.set_xlim(mid_x - max_range, mid_x + max_range)
ax.set_ylim(mid_y - max_range, mid_y + max_range)
ax.set_zlim(mid_z - max_range, mid_z + max_range)

ax.view_init(elev=30, azim=45)
ax.axis('off')

plt.savefig(sys.argv[1].replace('.glb', '.png'), dpi=200, bbox_inches='tight', pad_inches=0)
