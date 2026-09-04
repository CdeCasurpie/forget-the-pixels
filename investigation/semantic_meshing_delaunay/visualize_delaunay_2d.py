import os
import struct
import numpy as np
import matplotlib.pyplot as plt
import pycolmap
import cv2
from scipy.spatial import Delaunay
import open3d as o3d
import warnings

warnings.filterwarnings("ignore")

DIR_BASE = "/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/semantic_meshing_delaunay"
DATA_DIR = os.path.join(DIR_BASE, "data")
PLY_PATH = os.path.join(DATA_DIR, "fused_lightglue.ply")
VIS_PATH = os.path.join(DATA_DIR, "fused_lightglue.ply.vis")
SPARSE_DIR = os.path.join(DATA_DIR, "sparse")
PATH_IMG = os.path.join(DATA_DIR, "images")
OUT_PLOT = "/home/cesar/.gemini/antigravity-cli/brain/71b0c72d-e878-4409-a05f-4428e83e4a5a/delaunay_2d_plot.png"

image_to_points = {}
with open(VIS_PATH, "rb") as f:
    num_points = struct.unpack("<Q", f.read(8))[0]
    for pt_idx in range(num_points):
        num_visible_images = struct.unpack("<I", f.read(4))[0]
        image_ids = struct.unpack("<" + "I"*num_visible_images, f.read(4*num_visible_images))
        for img_id in image_ids:
            if img_id not in image_to_points: image_to_points[img_id] = []
            image_to_points[img_id].append(pt_idx)

rec = pycolmap.Reconstruction(SPARSE_DIR)
pcd = o3d.io.read_point_cloud(PLY_PATH)
dense_points = np.asarray(pcd.points)

cam_list = [img for img in rec.images.values() if img.image_id in image_to_points and len(image_to_points[img.image_id]) > 0]
cam_list = sorted(cam_list, key=lambda x: x.name)

# Escogeremos la cámara 10 para que sea representativa (puedes cambiarla)
img_obj = cam_list[10] 
cam = rec.cameras[img_obj.camera_id]

idx = image_to_points[img_obj.image_id]
pts3d = dense_points[idx]

T_world_to_cam = np.eye(4)
if hasattr(img_obj, 'cam_from_world'):
    T_world_to_cam[:3, :4] = img_obj.cam_from_world().matrix()
else:
    T_world_to_cam[:3, :3] = img_obj.rotmat()
    T_world_to_cam[:3, 3] = img_obj.tvec

R = T_world_to_cam[:3, :3]
t = T_world_to_cam[:3, 3].reshape(3,1)
pts_cam = (R @ pts3d.T) + t

if hasattr(cam, 'calibration_matrix'): K = cam.calibration_matrix()
else: K = np.eye(3); K[0,0] = cam.params[0]; K[1,1] = cam.params[0]; K[0,2] = cam.params[1]; K[1,2] = cam.params[2]

pts_px = (K @ pts_cam)
pts_px = pts_px[:2, :] / pts_px[2, :]
pts_2d = pts_px.T

tri = Delaunay(pts_2d)

img_path = os.path.join(PATH_IMG, img_obj.name)
img_rgb = cv2.imread(img_path)
img_rgb = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2RGB)

plt.figure(figsize=(16, 9))
plt.imshow(img_rgb)
plt.triplot(pts_2d[:, 0], pts_2d[:, 1], tri.simplices, color='cyan', linewidth=0.3, alpha=0.6)
plt.plot(pts_2d[:, 0], pts_2d[:, 1], '.', color='red', markersize=0.5, alpha=0.8)
plt.axis('off')
plt.title(f"2D Delaunay Triangulation - {img_obj.name}", fontsize=20, color='white', backgroundcolor='black')
plt.tight_layout()
plt.savefig(OUT_PLOT, dpi=300, facecolor='black', bbox_inches='tight')
print(f"Grafico guardado en {OUT_PLOT}")
