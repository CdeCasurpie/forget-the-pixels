import os
import cv2
import numpy as np
import open3d as o3d
import torch
from PIL import Image
from transformers import pipeline

def unproject_spherical(equi_rgb, equi_depth, B=4):
    """
    Desproyecta una imagen equirectangular (360) directamente a 3D usando coordenadas esféricas.
    equi_rgb: Imagen de color (H, W, 3)
    equi_depth: Mapa de profundidad relativo/radial (H, W)
    B: Factor de submuestreo (salta B pixeles para no hacer la nube tan pesada)
    """
    H, W = equi_depth.shape
    
    # Crear grilla de pixeles (saltando de B en B)
    u, v = np.meshgrid(np.arange(0, W, B), np.arange(0, H, B))
    u = u.ravel()
    v = v.ravel()
    
    # Valores de color y profundidad para esos pixeles
    colors = equi_rgb[v, u] / 255.0
    depth_val = equi_depth[v, u]
    
    # Descartamos el cielo (valores de disparidad muy bajos, o profundidad muy lejana)
    # Como usamos el output raw 0-255 de Depth Anything, 0 es muy lejos (cielo).
    valid_mask = depth_val > 10.0
    
    u = u[valid_mask]
    v = v[valid_mask]
    depth_val = depth_val[valid_mask]
    colors = colors[valid_mask]
    
    # Convertir disparidad (0-255) a Distancia Radial R (Metros)
    # R = Constante / disparidad
    R = 1000.0 / (depth_val + 1.0)
    
    # Limitar el radio máximo (ej. 50 metros)
    dist_mask = R < 50.0
    u = u[dist_mask]
    v = v[dist_mask]
    R = R[dist_mask]
    colors = colors[dist_mask]
    
    # Convertir coordenadas de imagen (u, v) a ángulos esféricos (theta, phi)
    # theta (Longitud / Yaw): de -PI a +PI (0 está en el centro de la imagen)
    theta = (u / W - 0.5) * 2 * np.pi
    
    # phi (Latitud / Pitch): de +PI/2 (arriba) a -PI/2 (abajo)
    phi = (0.5 - v / H) * np.pi
    
    # Convertir esféricas a cartesianas (X, Y, Z)
    # Asumimos: Y es ARRIBA, Z es ADELANTE, X es DERECHA
    X = R * np.cos(phi) * np.sin(theta)
    Y = R * np.sin(phi)
    Z = R * np.cos(phi) * np.cos(theta)
    
    pts_3d = np.stack((X, Y, Z), axis=-1)
    
    return pts_3d, colors

def main():
    print("Iniciando desproyección ESFÉRICA directa de 1 panorama...")
    
    pano_file = "data/imagenes_gsv_ampliado/000_EZ_BP13ke0Ens6hmZOdwzQ.jpg"
    if not os.path.exists(pano_file):
        print(f"Error: No se encontró la imagen {pano_file}")
        return
        
    equi_bgr = cv2.imread(pano_file)
    equi_rgb = cv2.cvtColor(equi_bgr, cv2.COLOR_BGR2RGB)
    
    print("Cargando modelo Depth Anything V2...")
    device = 0 if torch.cuda.is_available() else -1
    depth_pipe = pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device=device)
    
    print("Estimando mapa de profundidad 360°...")
    result = depth_pipe(Image.fromarray(equi_rgb))
    equi_depth = np.array(result["depth"], dtype=np.float32)
    
    print("Desproyectando directamente a nube de puntos esférica...")
    # B=4 toma 1 pixel de cada 4x4, dando una buena densidad
    pts_world, colors = unproject_spherical(equi_rgb, equi_depth, B=4)
    
    # Agregar un punto rojo gigante en el origen (cámara) para referencia
    cam_pts = np.random.randn(500, 3) * 0.1
    cam_colors = np.ones((500, 3)) * [1.0, 0.0, 0.0]
    
    final_pts = np.vstack((pts_world, cam_pts))
    final_colors = np.vstack((colors, cam_colors))
    
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(final_pts)
    pcd.colors = o3d.utility.Vector3dVector(final_colors)
    
    # Guardar
    os.makedirs("outputs/pointclouds", exist_ok=True)
    out_file = "outputs/pointclouds/test_spherical_direct.ply"
    o3d.io.write_point_cloud(out_file, pcd)
    print(f"¡Listo! Se guardó la nube esférica en {out_file} ({len(pts_world):,} puntos)")

if __name__ == "__main__":
    main()
