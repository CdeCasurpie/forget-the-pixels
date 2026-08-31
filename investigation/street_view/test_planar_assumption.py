import os
import cv2
import numpy as np
import open3d as o3d
import torch
from PIL import Image
from transformers import pipeline
from skimage.segmentation import felzenszwalb, mark_boundaries
import matplotlib.pyplot as plt

from modules.geometry import extract_pinhole_from_equi, unproject_rgbd_to_3d

def fit_and_project_plane(pts):
    """
    Ajusta un plano ideal a una nube de puntos 3D usando RANSAC y proyecta
    los puntos sobre ese plano, forzándolos a ser perfectamente rectos.
    """
    if len(pts) < 10:
        return pts # No hay suficientes puntos para un plano
        
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts)
    
    try:
        # RANSAC para encontrar el plano matemático perfecto
        plane_model, inliers = pcd.segment_plane(distance_threshold=1.5,
                                                 ransac_n=3,
                                                 num_iterations=200)
        a, b, c, d = plane_model
        
        # Vector normal del plano
        n = np.array([a, b, c])
        n = n / np.linalg.norm(n)
        
        # Distancia de cada punto original al plano
        distances = (pts @ n) + d
        
        # Proyectar los puntos contra el plano matemático
        pts_projected = pts - np.outer(distances, n)
        return pts_projected
        
    except Exception as e:
        return pts

def main():
    print("Iniciando prueba de ASUNCIÓN PLANAR (Muros matemáticamente rectos)...")
    
    pano_file = "data/imagenes_gsv_ampliado/000_EZ_BP13ke0Ens6hmZOdwzQ.jpg"
    equi_bgr = cv2.imread(pano_file)
    equi_rgb = cv2.cvtColor(equi_bgr, cv2.COLOR_BGR2RGB)
    
    # Extraer solo la vista Frontal para esta prueba
    FOV = 100
    W, H = 640, 640
    yaw = 0 
    pin_rgb, K, R = extract_pinhole_from_equi(equi_rgb, FOV, yaw, 0, W, H)
    
    # 1. Segmentación por Color (Superpixeles Felzenszwalb)
    print("Segmentando la imagen en planos estructurales (Felzenszwalb)...")
    # Ajustar 'scale' define el tamaño de los segmentos (mayor = muros enteros)
    segments = felzenszwalb(pin_rgb, scale=300.0, sigma=0.8, min_size=500)
    
    # Guardar imagen de los segmentos encontrados para debug
    boundaries = mark_boundaries(pin_rgb, segments)
    os.makedirs("outputs/debug", exist_ok=True)
    cv2.imwrite("outputs/debug/planar_segmentation.jpg", (boundaries * 255).astype(np.uint8))
    print("  -> Imagen de segmentación guardada en outputs/debug/planar_segmentation.jpg")
    
    # 2. IA para Profundidad base
    print("Calculando profundidad inicial con Depth Anything...")
    dev = 0 if torch.cuda.is_available() else -1
    depth_pipe = pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device=dev)
    result = depth_pipe(Image.fromarray(pin_rgb))
    depth_array = np.array(result["depth"], dtype=np.float32)
    
    # Ecuación de profundidad relativa pura (sin cortes)
    Z = 1000.0 / (depth_array + 1.0)
    
    # 3. Desproyectar puntos ruidosos (Cielo y ruido neural)
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    cx, cy = K[0,2], K[1,2]
    fx, fy = K[0,0], K[1,1]
    
    X_cam = (u - cx) * Z / fx
    Y_cam = (v - cy) * Z / fy
    pts_cam = np.stack((X_cam, Y_cam, Z), axis=-1)
    
    pts_world_raw = pts_cam @ R.T
    
    all_planar_pts = []
    all_colors = []
    
    # 4. APLASTAR cada segmento contra su Plano 3D Ideal
    print(f"Detectados {len(np.unique(segments))} segmentos/muros. Aplastando geometría...")
    
    for seg_id in np.unique(segments):
        mask = (segments == seg_id)
        
        pts_segment = pts_world_raw[mask]
        colors_segment = pin_rgb[mask] / 255.0
        
        # Ignorar si es muy pequeño
        if len(pts_segment) < 200:
            continue
            
        # Ignorar segmentos que están demasiado lejos (Cielo / Fondo)
        Z_segment_cam = Z[mask]
        if np.median(Z_segment_cam) > 30.0:
            continue
            
        # Ajustar el plano matemático para el muro/fachada
        pts_planar = fit_and_project_plane(pts_segment)
        
        all_planar_pts.append(pts_planar)
        all_colors.append(colors_segment)
        
    final_pts = np.vstack(all_planar_pts)
    final_colors = np.vstack(all_colors)
    
    # Guardar Nube de Puntos Plana (Estructural)
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(final_pts)
    pcd.colors = o3d.utility.Vector3dVector(final_colors)
    
    os.makedirs("outputs/pointclouds", exist_ok=True)
    out_file = "outputs/pointclouds/test_planar_assumption.ply"
    o3d.io.write_point_cloud(out_file, pcd)
    print(f"¡Listo! Se guardó la abstracción planar en {out_file}")

if __name__ == "__main__":
    main()
