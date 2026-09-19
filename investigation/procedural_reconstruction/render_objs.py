import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from pathlib import Path
import sys

def render_obj(obj_path, out_png):
    vertices = []
    faces = []
    
    with open(obj_path, 'r') as f:
        for line in f:
            if line.startswith('v '):
                parts = line.split()
                vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif line.startswith('f '):
                parts = line.split()
                # obj is 1-indexed
                face = [int(p.split('/')[0]) - 1 for p in parts[1:4]]
                faces.append(face)
                
    if not vertices or not faces:
        return
        
    vertices = np.array(vertices)
    
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_subplot(111, projection='3d')
    
    # Calculate bounds for isometric scaling
    max_range = np.array([
        vertices[:,0].max() - vertices[:,0].min(),
        vertices[:,1].max() - vertices[:,1].min(),
        vertices[:,2].max() - vertices[:,2].min()
    ]).max() / 2.0
    
    mid_x = (vertices[:,0].max() + vertices[:,0].min()) * 0.5
    mid_y = (vertices[:,1].max() + vertices[:,1].min()) * 0.5
    mid_z = (vertices[:,2].max() + vertices[:,2].min()) * 0.5
    
    ax.set_xlim(mid_x - max_range, mid_x + max_range)
    ax.set_ylim(mid_y - max_range, mid_y + max_range)
    ax.set_zlim(mid_z - max_range, mid_z + max_range)
    
    # Create polygons
    polygons = []
    for face in faces:
        polygons.append([vertices[idx] for idx in face])
        
    collection = Poly3DCollection(polygons, facecolors='w', linewidths=0.2, edgecolors='k', alpha=1.0)
    ax.add_collection3d(collection)
    
    # View angle (Isometric-ish)
    ax.view_init(elev=30, azim=45)
    ax.axis('off')
    
    plt.savefig(out_png, dpi=200, bbox_inches='tight', pad_inches=0)
    plt.close()

if __name__ == "__main__":
    out_dir = Path("steps/step10_procedural_generation_test/outputs")
    for obj in out_dir.glob("*.obj"):
        png_path = obj.with_suffix('.png')
        print(f"Rendering {obj} to {png_path}...")
        render_obj(obj, png_path)
