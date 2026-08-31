import os
import cv2
import numpy as np
import open3d as o3d
import torch
from PIL import Image
from transformers import pipeline

from modules.geometry import extract_pinhole_from_equi, unproject_rgbd_to_3d

def main():
    print("Iniciando prueba con un solo panorama...")
    
    # 1. Cargar una sola imagen equirectangular
    pano_file = "data/imagenes_gsv_ampliado/000_EZ_BP13ke0Ens6hmZOdwzQ.jpg"
    if not os.path.exists(pano_file):
        print(f"Error: No se encontró la imagen {pano_file}")
        return
        
    equi_bgr = cv2.imread(pano_file)
    equi_rgb = cv2.cvtColor(equi_bgr, cv2.COLOR_BGR2RGB)
    
    # 2. Inicializar Depth Anything V2
    print("Cargando modelo Depth Anything V2...")
    device = 0 if torch.cuda.is_available() else -1
    depth_pipe = pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device=device)
    
    # Configuraciones de vistas (Pinhole)
    FOV = 90
    W, H = 512, 512
    yaws = [0, 90, 180, 270] # Frente, Derecha, Atrás, Izquierda
    
    all_points = []
    all_colors = []
    
    print("Procesando vistas Pinhole...")
    for yaw in yaws:
        print(f"  -> Extrayendo vista a {yaw} grados...")
        
        # Extraer imagen RGB pinhole y su rotación
        pinhole_rgb, K, R = extract_pinhole_from_equi(equi_rgb, FOV, yaw, 0, W, H)
        
        # Estimar mapa de profundidad
        result = depth_pipe(Image.fromarray(pinhole_rgb))
        # Extraer imagen PIL en lugar del tensor crudo
        depth_image = result["depth"]
        depth_array = np.array(depth_image, dtype=np.float32)
        
        # Z = Constante / (disparidad_0_255 + 1.0)
        Z = 1000.0 / (depth_array + 1.0)
        
        # Ignorar píxeles demasiado lejanos (cielo)
        mask = Z < 50.0 
        Z[~mask] = 0
        
        # Desproyectar a 3D (Se usa R para alinear esta vista al panorama original)
        pts_world, colors = unproject_rgbd_to_3d(pinhole_rgb, Z, K, R)
        
        all_points.append(pts_world)
        all_colors.append(colors)
        
        # Opcional: Guardar el RGB pinhole para depurar
        os.makedirs("outputs/debug", exist_ok=True)
        cv2.imwrite(f"outputs/debug/debug_pinhole_{yaw}.jpg", cv2.cvtColor(pinhole_rgb, cv2.COLOR_RGB2BGR))
        
    # Juntar todas las vistas
    print("Generando nube de puntos combinada...")
    final_pts = np.vstack(all_points)
    final_colors = np.vstack(all_colors)
    
    # Puntos rojos en el origen de la cámara
    cam_pts = np.random.randn(200, 3) * 0.1
    cam_colors = np.ones((200, 3)) * [1.0, 0.0, 0.0]
    
    final_pts = np.vstack((final_pts, cam_pts))
    final_colors = np.vstack((final_colors, cam_colors))
    
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(final_pts)
    pcd.colors = o3d.utility.Vector3dVector(final_colors)
    
    # Guardar
    os.makedirs("outputs/pointclouds", exist_ok=True)
    out_file = "outputs/pointclouds/test_single_pano.ply"
    o3d.io.write_point_cloud(out_file, pcd)
    print(f"¡Listo! Se guardó la reconstrucción de esta cámara en {out_file}")

if __name__ == "__main__":
    main()
