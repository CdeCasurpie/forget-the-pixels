import os
import math
import numpy as np
import open3d as o3d
import cv2
import streetlevel.streetview as sv

def latlon_to_meters(lat, lon, lat0, lon0):
    R = 6378137.0
    dlat = math.radians(lat - lat0)
    dlon = math.radians(lon - lon0)
    y = dlat * R
    x = dlon * R * math.cos(math.radians(lat0))
    return x, y

def pano_to_pointcloud(pano, img, lat0, lon0):
    depth = pano.depth.data 
    H, W = depth.shape
    
    img_resized = cv2.resize(np.array(img), (W, H))
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    
    yaw = 2 * np.pi * (u / W) - np.pi
    pitch = np.pi * (0.5 - (v / H))
    
    valid = (depth > 0) & (depth < 80) # Cortamos a 80m para evitar cielo/ruido lejano
    yaw = yaw[valid]
    pitch = pitch[valid]
    d = depth[valid]
    
    # Eje X invertido para arreglar el mirror
    x = - (d * np.cos(pitch) * np.sin(yaw))
    y = d * np.cos(pitch) * np.cos(yaw)
    z = d * np.sin(pitch)
    
    points = np.stack([x, y, z], axis=1)
    colors = img_resized[valid] / 255.0
    
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors)
    
    # Alinear al Norte Global
    heading_rad = math.radians(-pano.heading)
    R_heading = o3d.geometry.get_rotation_matrix_from_xyz((0, 0, heading_rad))
    pcd.rotate(R_heading, center=(0, 0, 0))
    
    # Posicionar en GPS
    tx, ty = latlon_to_meters(pano.lat, pano.lon, lat0, lon0)
    tz = pano.elevation if pano.elevation else 0.0
    pcd.translate((tx, ty, tz))
    
    return pcd

def main():
    target_lat = -12.137248
    target_lon = -77.020423
    count = 15 # Usamos 15 fotos para armar el trayecto
    
    print(f"Buscando panorama inicial en ({target_lat}, {target_lon})...")
    pano = sv.find_panorama(target_lat, target_lon)
    if not pano: return

    full_pano = sv.find_panorama_by_id(pano.id)
    target_year = full_pano.date.year
    
    valid_panos = [full_pano]
    seen_ids = {full_pano.id}
    queue = [full_pano]
    
    while queue and len(valid_panos) < count:
        current = queue.pop(0)
        if not hasattr(current, 'neighbors') or not current.neighbors:
            continue
        for n in current.neighbors:
            if len(valid_panos) >= count:
                break
            if n.id not in seen_ids:
                seen_ids.add(n.id)
                full_n = sv.find_panorama_by_id(n.id)
                if full_n and full_n.date and full_n.date.year == target_year:
                    valid_panos.append(full_n)
                    queue.append(full_n)

    print(f"Encontrados {len(valid_panos)} panoramas continuos.")
    
    lat0, lon0 = valid_panos[0].lat, valid_panos[0].lon
    global_pcd = o3d.geometry.PointCloud()
    
    for i, p in enumerate(valid_panos):
        print(f" -> Fusionando foto [{i+1}/{len(valid_panos)}]: {p.id}")
        p_depth = sv.find_panorama_by_id(p.id, download_depth=True)
        img = sv.get_panorama(p_depth, zoom=1) # Zoom 1 para que al fusionar 15 no explote la RAM
        
        if p_depth.depth:
            pcd = pano_to_pointcloud(p_depth, img, lat0, lon0)
            global_pcd += pcd

    print("Limpiando puntos atípicos de la fusión...")
    global_pcd = global_pcd.voxel_down_sample(voxel_size=0.15)
    global_pcd, _ = global_pcd.remove_statistical_outlier(nb_neighbors=25, std_ratio=1.5)
    
    out_path = "/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/semantic_meshing_gsv/data/gsv_global.ply"
    o3d.io.write_point_cloud(out_path, global_pcd)
    print(f"Mega-nube guardada en {out_path}!")

if __name__ == "__main__":
    main()
