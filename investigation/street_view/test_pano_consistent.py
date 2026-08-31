import os
import cv2
import numpy as np
import open3d as o3d
import torch
from PIL import Image
from transformers import pipeline

from modules.geometry import extract_pinhole_from_equi, unproject_rgbd_to_3d

def main():
    print("Iniciando prueba de consistencia de panorama (SIN CORTES)...")
    
    pano_file = "data/imagenes_gsv_ampliado/000_EZ_BP13ke0Ens6hmZOdwzQ.jpg"
    if not os.path.exists(pano_file):
        print(f"Error: No se encontró la imagen {pano_file}")
        return
        
    equi_bgr = cv2.imread(pano_file)
    equi_rgb = cv2.cvtColor(equi_bgr, cv2.COLOR_BGR2RGB)
    
    print("Cargando modelo Depth Anything V2...")
    device = 0 if torch.cuda.is_available() else -1
    depth_pipe = pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device=device)
    
    # LA MAGIA PARA EVITAR CORTES: 
    # Ejecutar el modelo de profundidad sobre TODO EL PANORAMA 360 al mismo tiempo.
    # Así, la red neuronal normaliza la escala de toda la escena globalmente,
    # en lugar de normalizar cada recorte Pinhole de forma independiente.
    print("Estimando profundidad global del panorama 360...")
    result_global = depth_pipe(Image.fromarray(equi_rgb))
    
    # Extraemos la imagen PIL de profundidad y la pasamos a float32
    equi_depth_pil = result_global["depth"]
    equi_depth = np.array(equi_depth_pil, dtype=np.float32)
    
    FOV = 90
    W, H = 512, 512
    yaws = [0, 90, 180, 270]
    
    all_points = []
    all_colors = []
    
    print("Extrayendo vistas Pinhole consistentes...")
    for yaw in yaws:
        print(f"  -> Procesando vista a {yaw} grados...")
        
        # 1. Extraer recorte RGB
        pinhole_rgb, K, R = extract_pinhole_from_equi(equi_rgb, FOV, yaw, 0, W, H)
        
        # 2. Extraer recorte de Profundidad EXACTAMENTE con la misma matriz matemática
        # Esto asegura que el depth Pinhole coincida pixel a pixel con el RGB Pinhole
        pinhole_depth, _, _ = extract_pinhole_from_equi(equi_depth, FOV, yaw, 0, W, H)
        
        # Guardar para debug
        os.makedirs("outputs/debug", exist_ok=True)
        cv2.imwrite(f"outputs/debug/consistent_rgb_{yaw}.jpg", cv2.cvtColor(pinhole_rgb, cv2.COLOR_RGB2BGR))
        cv2.imwrite(f"outputs/debug/consistent_depth_{yaw}.jpg", pinhole_depth.astype(np.uint8))
        
        # 3. Filtrar cielo y objetos muy lejanos
        # En la imagen PIL, el cielo (muy lejos) tiene valores cercanos a 0.
        # Las cosas muy cerca tienen valores cercanos a 255.
        sky_threshold = 20.0 # Si la disparidad es menor a 20, es cielo o fondo infinito
        
        # Convertimos a Profundidad Z en metros (escala relativa por ahora)
        Z = 1000.0 / (pinhole_depth + 1.0)
        
        # Aplicamos la máscara para eliminar el cielo (evitar muros fantasma)
        mask_sky = pinhole_depth < sky_threshold
        Z[mask_sky] = 0.0
        
        # 4. Desproyectar a 3D
        pts_world, colors = unproject_rgbd_to_3d(pinhole_rgb, Z, K, R)
        
        all_points.append(pts_world)
        all_colors.append(colors)
        
    print("Generando nube de puntos sin costuras (seamless)...")
    final_pts = np.vstack(all_points)
    final_colors = np.vstack(all_colors)
    
    cam_pts = np.random.randn(200, 3) * 0.1
    cam_colors = np.ones((200, 3)) * [1.0, 0.0, 0.0]
    final_pts = np.vstack((final_pts, cam_pts))
    final_colors = np.vstack((final_colors, cam_colors))
    
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(final_pts)
    pcd.colors = o3d.utility.Vector3dVector(final_colors)
    
    os.makedirs("outputs/pointclouds", exist_ok=True)
    out_file = "outputs/pointclouds/test_pano_consistent.ply"
    o3d.io.write_point_cloud(out_file, pcd)
    print(f"¡Listo! Se guardó en {out_file}")

if __name__ == "__main__":
    main()
