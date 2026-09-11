import pycolmap
import numpy as np

rec = pycolmap.Reconstruction("../Lotes/nube_sparse/0_aligned")
pts = [p.xyz for p in list(rec.points3D.values())[:5]]
print(f"Sample COLMAP points: {pts}")

if len(pts) > 0:
    mean_pt = np.mean(pts, axis=0)
    print(f"Mean pt: {mean_pt}")
