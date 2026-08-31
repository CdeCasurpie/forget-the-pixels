import os
import cv2
import numpy as np
import open3d as o3d
import torch
from PIL import Image
from transformers import pipeline

from modules.geometry import extract_pinhole_from_equi, unproject_rgbd_to_3d

def main():
    print("Iniciando prueba Pinhole con Overlap (Muros Rectos + Sin Cortes)...")
    
    pano_file = "data/imagenes_gsv_ampliado/000_EZ_BP13ke0Ens6hmZOdwzQ.jpg"
    equi_bgr = cv2.imread(pano_file)
    equi_rgb = cv2.cvtColor(equi_bgr, cv2.COLOR_BGR2RGB)
    
    dev = 0 if torch.cuda.is_available() else -1
    depth_pipe = pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device=dev)
    
    # FOV > 90 para crear superposición (overlap) entre las cámaras
    FOV = 100 
    W, H = 512, 512
    yaws = [0, 90, 180, 270]
    
    views = []
    
    # 1. Extraer y procesar cada vista de forma independiente
    for yaw in yaws:
        pin_rgb, K, R = extract_pinhole_from_equi(equi_rgb, FOV, yaw, 0, W, H)
        result = depth_pipe(Image.fromarray(pin_rgb))
        depth_array = np.array(result["depth"], dtype=np.float32)
        
        # Z crudo (relativo)
        Z_rel = 1000.0 / (depth_array + 1.0)
        
        views.append({
            "yaw": yaw,
            "rgb": pin_rgb,
            "Z": Z_rel,
            "K": K,
            "R": R,
            "scale": 1.0
        })
        
    print("Alineando escalas usando las zonas de superposición...")
    
    # 2. Alinear las escalas en base al overlap
    # Para saber qué píxeles se superponen, desproyectamos una malla 3D de la vista B
    # y la proyectamos en la cámara de la vista A.
    
    for i in range(3):
        vA = views[i]
        vB = views[i+1]
        
        # Tomar una muestra de puntos de vB (ej. el borde izquierdo, que choca con vA)
        # Borde izquierdo de vB es columnas 0 a 100
        u, v = np.meshgrid(np.arange(0, 100, 5), np.arange(0, H, 5))
        u, v = u.ravel(), v.ravel()
        Z_B = vB["Z"][v, u]
        
        # Pasar a 3D en el mundo global
        cx, cy = vB["K"][0,2], vB["K"][1,2]
        fx, fy = vB["K"][0,0], vB["K"][1,1]
        x_c = (u - cx) * Z_B / fx
        y_c = (v - cy) * Z_B / fy
        pts_cam_B = np.stack((x_c, y_c, Z_B), axis=-1)
        pts_world = pts_cam_B @ vB["R"]
        
        # Proyectar estos puntos del mundo a la cámara vA
        pts_cam_A = pts_world @ vA["R"].T
        
        # Quedarnos solo con los que caen delante de la cámara A
        z_A = pts_cam_A[:, 2]
        valid = z_A > 0.1
        pts_cam_A = pts_cam_A[valid]
        Z_B_val = Z_B[valid]
        
        # Proyectar a pixeles en A
        u_A = (pts_cam_A[:, 0] * fx / z_A) + cx
        v_A = (pts_cam_A[:, 1] * fy / z_A) + cy
        
        # Filtrar los que caen dentro de la imagen A
        inside = (u_A >= 0) & (u_A < W) & (v_A >= 0) & (v_A < H)
        u_A = np.round(u_A[inside]).astype(int)
        v_A = np.round(v_A[inside]).astype(int)
        Z_B_val = Z_B_val[inside]
        
        if len(Z_B_val) > 10:
            Z_A_val = vA["Z"][v_A, u_A] * vA["scale"]
            # Calcular cuánto hay que multiplicar vB para que empate con vA
            ratio = np.median(Z_A_val / Z_B_val)
            vB["scale"] = ratio
            print(f"  Alineando vista {vB['yaw']} con {vA['yaw']}: factor = {ratio:.3f}")
        else:
            print(f"  Fallo alineando {vB['yaw']} con {vA['yaw']}")

    # 3. Generar la nube final
    print("Generando nube...")
    all_pts, all_col = [], []
    for v in views:
        # Aplicar la escala calculada
        Z_final = v["Z"] * v["scale"]
        
        # Filtrar cielo (disparidad original muy pequeña)
        sky_mask = (1000.0 / v["Z"]) < 10.0
        Z_final[sky_mask] = 0
        
        pts, col = unproject_rgbd_to_3d(v["rgb"], Z_final, v["K"], v["R"])
        all_pts.append(pts)
        all_col.append(col)
        
    final_pts = np.vstack(all_pts)
    final_col = np.vstack(all_col)
    
    # Punto central rojo
    cam_pts = np.random.randn(200, 3) * 0.1
    cam_col = np.ones((200, 3)) * [1, 0, 0]
    final_pts = np.vstack((final_pts, cam_pts))
    final_colors = np.vstack((final_col, cam_col))
    
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(final_pts)
    pcd.colors = o3d.utility.Vector3dVector(final_colors)
    
    os.makedirs("outputs/pointclouds", exist_ok=True)
    out = "outputs/pointclouds/test_pinhole_overlap.ply"
    o3d.io.write_point_cloud(out, pcd)
    print(f"¡Listo! {out} guardado.")

if __name__ == "__main__":
    main()
