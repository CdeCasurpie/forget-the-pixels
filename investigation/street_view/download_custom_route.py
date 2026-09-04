import os
import json
import cv2
import csv
import numpy as np
import streetlevel.streetview as sv
import math
import argparse

def get_focal_length(fov_deg, width):
    fov_rad = math.radians(fov_deg)
    return (width / 2.0) / math.tan(fov_rad / 2.0)

def create_perspective_split(pano_img, fov=135, width=1024, height=1024):
    pano_cv = cv2.cvtColor(np.array(pano_img), cv2.COLOR_RGB2BGR)
    pano_h, pano_w = pano_cv.shape[:2]
    
    focal = get_focal_length(fov, width)
    K = np.array([
        [focal, 0, width/2],
        [0, focal, height/2],
        [0, 0, 1]
    ], dtype=np.float32)
    
    splits = []
    angles = [0, 45, 90, 135, 180, 225, 270, 315]
    for angle in angles:
        yaw = math.radians(angle)
        pitch = 0.0
        
        R_y = np.array([
            [math.cos(yaw), 0, math.sin(yaw)],
            [0, 1, 0],
            [-math.sin(yaw), 0, math.cos(yaw)]
        ])
        R_x = np.array([
            [1, 0, 0],
            [0, math.cos(pitch), -math.sin(pitch)],
            [0, math.sin(pitch), math.cos(pitch)]
        ])
        R = R_y @ R_x
        
        map_x = np.zeros((height, width), dtype=np.float32)
        map_y = np.zeros((height, width), dtype=np.float32)
        
        y_coords, x_coords = np.indices((height, width))
        x_c = x_coords - width/2
        y_c = y_coords - height/2
        z_c = np.full_like(x_c, focal)
        
        pts_3d = np.stack([x_c, y_c, z_c], axis=-1).reshape(-1, 3)
        pts_rot = pts_3d @ R.T
        
        x_rot = pts_rot[:, 0]
        y_rot = pts_rot[:, 1]
        z_rot = pts_rot[:, 2]
        
        lon = np.arctan2(x_rot, z_rot)
        lat = np.arcsin(np.clip(y_rot / np.linalg.norm(pts_rot, axis=1), -1, 1))
        
        lon_norm = (lon / (2 * math.pi)) + 0.5
        lat_norm = (lat / math.pi) + 0.5
        
        map_x_flat = lon_norm * pano_w
        map_y_flat = lat_norm * pano_h
        
        # Corrección de bordes esféricos
        map_x_flat = np.where(map_x_flat >= pano_w, map_x_flat - pano_w, map_x_flat)
        map_x_flat = np.where(map_x_flat < 0, map_x_flat + pano_w, map_x_flat)
        
        map_x = map_x_flat.reshape(height, width).astype(np.float32)
        map_y = map_y_flat.reshape(height, width).astype(np.float32)
        
        persp = cv2.remap(pano_cv, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        splits.append(persp)
        
    return splits

def main():
    parser = argparse.ArgumentParser(description="Descarga y divide panoramas GSV interactivos.")
    parser.add_argument("--route_json", default="../custom_route.json", help="JSON de la ruta interactiva seleccionada.")
    parser.add_argument("--out_dir", default="data_custom_route", help="Directorio de salida local para el dataset.")
    args = parser.parse_args()

    route_file = os.path.abspath(args.route_json)
    out_dir = os.path.abspath(args.out_dir)
    images_dir = os.path.join(out_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    
    if not os.path.exists(route_file):
        print(f"Error: No se encontro el archivo de ruta {route_file}.")
        print("Ejecuta primero: make run-gsv-route-selector")
        return
        
    with open(route_file, 'r') as f:
        route = json.load(f)
        
    fov = 135
    width, height = 1024, 1024
    focal = get_focal_length(fov, width)
    print(f"Descargando {len(route)} panoramas en FOV {fov}...")
    print(f"Focal matemático exacto para COLMAP: {focal:.2f}px")
    
    metadata = {}
    
    # Limpiar directorio de salida
    for f_name in os.listdir(images_dir):
        os.remove(os.path.join(images_dir, f_name))
        
    for i, p_info in enumerate(route):
        pid = p_info['id']
        print(f"[{i+1}/{len(route)}] Procesando Panorama ID: {pid}...")
        
        full_p = sv.find_panorama_by_id(pid)
        img_pil = sv.get_panorama(full_p, zoom=2)
        
        splits = create_perspective_split(img_pil, fov=fov, width=width, height=height)
        
        for v_idx, persp in enumerate(splits):
            h, w = persp.shape[:2]
            # Máscara negra en la zona inferior para borrar el auto
            persp[int(h*0.75):, :] = 0 
            
            out_name = f"{pid}_view{v_idx}.jpg"
            out_path = os.path.join(images_dir, out_name)
            cv2.imwrite(out_path, persp)
            
            metadata[out_name] = {
                "lat": p_info['lat'],
                "lon": p_info['lon'],
                "alt": 100.0 # Altitud default ficticia, requerida por colmap model_aligner
            }
            
    csv_file = os.path.join(out_dir, "gps.csv")
    with open(csv_file, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "lat", "lon", "alt"])
        for fname, m in metadata.items():
            writer.writerow([fname, m["lat"], m["lon"], m["alt"]])
            
    print(f"\n¡Completado! Dataset generado en: {out_dir}")
    print("Para subir a Khipu y procesar, ejecuta:")
    print("  make run-gsv-khipu-deploy PROJECT_NAME=mi_proyecto_1")

if __name__ == "__main__":
    main()
