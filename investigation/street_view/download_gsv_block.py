import os
import json
import cv2
import numpy as np
import streetlevel.streetview as sv
import math

def get_bounding_box_panos(lat_center, lon_center, max_count=40):
    panos = []
    seen = set()
    
    p = sv.find_panorama(lat_center, lon_center)
    if not p: return []
    
    full_p = sv.find_panorama_by_id(p.id)
    target_year = full_p.date.year
    
    queue = [full_p]
    seen.add(full_p.id)
    
    while queue and len(panos) < max_count:
        curr = queue.pop(0)
        panos.append(curr)
        
        if curr.neighbors:
            for n in curr.neighbors:
                if n.id not in seen:
                    seen.add(n.id)
                    full_n = sv.find_panorama_by_id(n.id)
                    if full_n and full_n.date.year == target_year:
                        queue.append(full_n)
                        
    return panos[:max_count]

def create_perspective_split(img, pano_id, out_dir, fov=90):
    h, w = img.shape[:2]
    out_size = 1024
    K = np.array([
        [out_size / (2 * np.tan(np.radians(fov) / 2)), 0, out_size / 2],
        [0, out_size / (2 * np.tan(np.radians(fov) / 2)), out_size / 2],
        [0, 0, 1]
    ], dtype=np.float32)
    
    for i in range(8):
        yaw = i * 45
        pitch = 0
        
        theta = np.radians(yaw)
        phi = np.radians(pitch)
        
        Rx = np.array([
            [1, 0, 0],
            [0, np.cos(phi), -np.sin(phi)],
            [0, np.sin(phi), np.cos(phi)]
        ])
        Ry = np.array([
            [np.cos(theta), 0, np.sin(theta)],
            [0, 1, 0],
            [-np.sin(theta), 0, np.cos(theta)]
        ])
        R = Ry @ Rx
        
        u, v = np.meshgrid(np.arange(out_size), np.arange(out_size))
        
        x = (u - K[0, 2]) / K[0, 0]
        y = (v - K[1, 2]) / K[1, 1]
        z = np.ones_like(x)
        
        rays = np.stack([x, y, z], axis=-1)
        rays_rot = rays @ R.T
        
        sph_theta = np.arctan2(rays_rot[..., 0], rays_rot[..., 2])
        sph_phi = np.arcsin(rays_rot[..., 1] / np.linalg.norm(rays_rot, axis=-1))
        
        map_x = (sph_theta / (2 * np.pi) + 0.5) * w
        map_y = (sph_phi / np.pi + 0.5) * h
        
        map_x = np.mod(map_x, w).astype(np.float32)
        map_y = map_y.astype(np.float32)
        
        # Como la mascara original ya se aplicó a la imagen 360,
        # la proyeccion heredara la oscuridad perfectamente.
        persp = cv2.remap(img, map_x, map_y, cv2.INTER_LINEAR)
        
        out_name = os.path.join(out_dir, f"{pano_id}_view{i}.jpg")
        cv2.imwrite(out_name, persp)

def main():
    lat = -12.137248
    lon = -77.020423
    out_dir = "/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/data_block/images"
    os.makedirs(out_dir, exist_ok=True)
    
    # Cargar mascara maestra
    mask_path = "/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/base_mask_360.png"
    if not os.path.exists(mask_path):
        print("Error: No se encontro base_mask_360.png")
        return
    master_mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    
    print("Obteniendo bloque continuo de 40 panoramas (Ruta cuadra)...")
    panos = get_bounding_box_panos(lat, lon, 40)
    
    metadata = {}
    for i, p in enumerate(panos):
        print(f"[{i+1}/{len(panos)}] Procesando {p.id}...")
        img_pil = sv.get_panorama(p, zoom=2)
        img_cv2 = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        
        # APLICAR MASCARA MAESTRA 360
        img_masked = cv2.bitwise_and(img_cv2, img_cv2, mask=master_mask)
        
        create_perspective_split(img_masked, p.id, out_dir)
        
        for v in range(8):
            metadata[f"{p.id}_view{v}.jpg"] = {
                "lat": p.lat,
                "lon": p.lon,
                "heading": p.heading,
                "alt": 100.0
            }
        
    import csv
    csv_file = "/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/data_block/gps.csv"
    with open(csv_file, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "lat", "lon", "alt"])
        for fname, m in metadata.items():
            writer.writerow([fname, m["lat"], m["lon"], m["alt"]])
            
    print("¡Descarga completada con MASCARA POLIGONAL MAESTRA!")

if __name__ == "__main__":
    main()
