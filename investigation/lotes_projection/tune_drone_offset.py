import os
import cv2
import numpy as np
from loaders import CRSManager, DataLoader
from projection import ZBufferProjector
import matplotlib.pyplot as plt

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
PATH_NUBE_COLMAP = os.path.join(DIR_BASE, "../Lotes/nube_sparse/0_aligned")
PATH_SHP = os.path.join(DIR_BASE, "../Lotes/shp_files/BARRANCO_LM_geogpsperu_SuyoPomalia.shp")
PATH_IMAGES = os.path.join(DIR_BASE, "../Lotes/images")
PATH_OFFSET = os.path.join(DIR_BASE, "../Lotes/offset_config.json")

crs = CRSManager()
loader = DataLoader(crs_manager=crs, offset_json_path=PATH_OFFSET)

print("Cargando modelo...")
cameras, pts_enu, colors = loader.load_colmap_model(PATH_NUBE_COLMAP)

# Pick a camera to tune (e.g., the 5th one or one looking at the street)
cam = cameras[5] if len(cameras) > 5 else cameras[0]
img_path = os.path.join(PATH_IMAGES, cam.image_name)
if not os.path.exists(img_path):
    print(f"No se encontró la imagen {img_path}")
    exit()

img = cv2.imread(img_path)

os.makedirs("tune_offsets", exist_ok=True)

offsets_to_test = [
    (0, 0),
    (5, 5), (-5, -5), (5, -5), (-5, 5),
    (10, 10), (-10, -10), (10, -10), (-10, 10),
    (0, 5), (0, -5), (5, 0), (-5, 0),
    (0, 10), (0, -10), (10, 0), (-10, 0)
]

print("Generando offsets...")
for ox, oy in offsets_to_test:
    loader.offset = {'x': float(ox), 'y': float(oy), 'angle': 0.0}
    lots = loader.load_cadastre(PATH_SHP, pts_enu)
    
    img_copy = img.copy()
    
    for lot in lots:
        strips_2d, bbox, is_visible = ZBufferProjector.project_lot_to_camera(lot, cam)
        if is_visible and strips_2d is not None:
            for strip in strips_2d:
                for i in range(len(strip) - 1):
                    p1 = (int(strip[i][0]), int(strip[i][1]))
                    p2 = (int(strip[i+1][0]), int(strip[i+1][1]))
                    cv2.line(img_copy, p1, p2, (0, 0, 255), 2)
                    
    cv2.putText(img_copy, f"Offset X:{ox} Y:{oy}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 4)
    out_name = f"tune_offsets/offset_{ox}_{oy}.jpg"
    cv2.imwrite(out_name, img_copy)
    print(f"Guardado {out_name}")

print("Listo!")
