import os
import cv2
import numpy as np
import open3d as o3d
import torch
import matplotlib.pyplot as plt
from PIL import Image
from transformers import pipeline

from modules.geometry import extract_pinhole_from_equi, unproject_rgbd_to_3d

def main():
    print("Iniciando prueba con una sola vista (Frente)...")
    
    pano_file = "data/imagenes_gsv_ampliado/000_EZ_BP13ke0Ens6hmZOdwzQ.jpg"
    if not os.path.exists(pano_file):
        print(f"Error: No se encontró la imagen {pano_file}")
        return
        
    equi_bgr = cv2.imread(pano_file)
    equi_rgb = cv2.cvtColor(equi_bgr, cv2.COLOR_BGR2RGB)
    
    print("Cargando modelo Depth Anything V2...")
    device = 0 if torch.cuda.is_available() else -1
    depth_pipe = pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device=device)
    
    FOV = 90
    W, H = 512, 512
    yaw = 0  # Solo al frente
    
    print(f"Extrayendo vista a {yaw} grados...")
    pinhole_rgb, K, R = extract_pinhole_from_equi(equi_rgb, FOV, yaw, 0, W, H)
    
    print("Estimando profundidad...")
    result = depth_pipe(Image.fromarray(pinhole_rgb))
    # Extraer la imagen PIL en lugar del tensor raw (evita valores negativos)
    depth_image = result["depth"]
    depth_array = np.array(depth_image, dtype=np.float32)
    
    print(f"Stats del Depth (0-255): min={depth_array.min():.3f}, max={depth_array.max():.3f}, mean={depth_array.mean():.3f}")
    
    os.makedirs("outputs/debug", exist_ok=True)
    cv2.imwrite("outputs/debug/test_single_rgb.jpg", cv2.cvtColor(pinhole_rgb, cv2.COLOR_RGB2BGR))
    cv2.imwrite("outputs/debug/test_single_depth_raw.jpg", depth_array.astype(np.uint8))
    
    # En la imagen PIL, 255 = cerca, 0 = lejos.
    # Convertimos a Profundidad Z. Sumamos offset para no dividir entre 0.
    # Z = Constante / disparidad_normalizada
    Z = 1000.0 / (depth_array + 1.0)  
    
    print(f"Stats de Z (Metros): min={Z.min():.3f}, max={Z.max():.3f}, mean={Z.mean():.3f}")
    
    # Ignorar cielo
    mask = Z < 50.0
    Z[~mask] = 0
    
    # Desproyectar asumiendo cámara en el origen y sin rotar (Identidad) para ver la nube de 1 sola vista pura.
    pts_world, colors = unproject_rgbd_to_3d(pinhole_rgb, Z, K, np.eye(3))
    
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts_world)
    pcd.colors = o3d.utility.Vector3dVector(colors)
    
    # Guardar
    os.makedirs("outputs/pointclouds", exist_ok=True)
    out_file = "outputs/pointclouds/test_single_view_only.ply"
    o3d.io.write_point_cloud(out_file, pcd)
    print(f"¡Listo! Se guardó {out_file} y las imágenes en outputs/debug/")

if __name__ == "__main__":
    main()
