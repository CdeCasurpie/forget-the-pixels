import os
import glob
import numpy as np
import open3d as o3d
from PIL import Image
import torch
from transformers import pipeline
from streetlevel import streetview
import pyproj

def rot_z(angle_rad):
    c = np.cos(angle_rad)
    s = np.sin(angle_rad)
    return np.array([
        [c, -s, 0],
        [s,  c, 0],
        [0,  0, 1]
    ])

def get_metadata(pano_id):
    pano = streetview.find_panorama_by_id(pano_id)
    return pano.lat, pano.lon, pano.heading

def equirectangular_to_pointcloud(rgb, depth_map):
    H, W = depth_map.shape
    
    # Crear malla de coordenadas (u, v)
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    
    # Normalizar a [0, 1]
    u = u.astype(float) / W
    v = v.astype(float) / H
    
    # Convertir a ángulos esféricos
    lon = (u - 0.5) * 2 * np.pi
    lat = (0.5 - v) * np.pi
    
    # Convertir a métrico heurístico (Depth Anything V2 suele devolver un mapa de disparidad relativa 0-255)
    # Valores altos = cerca, Valores bajos = lejos
    depth_map = np.clip(depth_map, 1.0, 255.0)
    
    # Filtro simple: ignorar cielo (cerca del cenit y muy lejos)
    mask = (depth_map > 10) & (lat < np.radians(45)) 
    
    # Calcular profundidad métrica pseudo-real
    depth = (255.0 / depth_map) * 3.0 # Escalar a metros aprox
    
    # Esféricas a Cartesianas (X=derecha, Y=frente, Z=arriba)
    x = depth * np.cos(lat) * np.sin(lon)
    y = depth * np.cos(lat) * np.cos(lon)
    z = depth * np.sin(lat)
    
    points = np.stack((x, y, z), axis=-1)[mask]
    colors = rgb[mask] / 255.0
    
    return points, colors

def main():
    print("Cargando modelo Depth Anything V2...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    pipe = pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device=0 if device=="cuda" else -1)
    
    # Convertidor de Coordenadas Lat/Lon a UTM Zona 18S (Lima)
    # Usamos UTM para trabajar en metros reales
    transformer = pyproj.Transformer.from_crs("epsg:4326", "epsg:32718", always_xy=True)
    
    images = glob.glob("imagenes_gsv/*.jpg")
    if not images:
        print("No se encontraron imágenes en imagenes_gsv/")
        return
        
    all_points = []
    all_colors = []
    centers = []
    
    for file in images:
        pano_id = os.path.basename(file).replace(".jpg", "").split("_", 3)[-1]
        print(f"Procesando panorama {pano_id}...")
        
        # 1. Obtener metadata de Street View
        lat, lon, heading = get_metadata(pano_id)
        utm_x, utm_y = transformer.transform(lon, lat)
        centers.append([utm_x, utm_y, 0.0])
        print(f"  Coordenadas UTM: X={utm_x:.2f}, Y={utm_y:.2f}, Heading={heading}°")
        
        # 2. Cargar imagen y estimar profundidad
        img = Image.open(file).convert("RGB")
        # Reducir resolución para no saturar memoria
        img.thumbnail((1024, 512))
        rgb = np.array(img)
        
        print("  Estimando profundidad con IA...")
        result = pipe(img)
        depth_img = result["depth"]
        depth_map = np.array(depth_img).astype(float)
        
        # 3. Desproyectar equirectangular a 3D
        points, colors = equirectangular_to_pointcloud(rgb, depth_map)
        
        # 4. Rotar según el Heading del carro
        # El centro de la equirectangular (u=0.5) es el frente (Y positivo).
        # El Heading es el ángulo horario desde el Norte.
        # En UTM, Y es Norte, X es Este.
        # Rotamos alrededor de Z (negativo porque Heading es horario y rotación matricial es antihoraria).
        heading_rad = np.radians(heading)
        R = rot_z(-heading_rad)
        points = points @ R.T
        
        # 5. Trasladar a coordenadas UTM globales
        points[:, 0] += utm_x
        points[:, 1] += utm_y
        
        all_points.append(points)
        all_colors.append(colors)
        
    # Combinar todas las nubes
    print("Combinando nubes y centrando...")
    all_points = np.vstack(all_points)
    all_colors = np.vstack(all_colors)
    
    # 6. Centrar todo en 0,0,0
    mean_center = np.mean(centers, axis=0)
    all_points -= mean_center
    
    # 7. Guardar como PLY
    print("Guardando reconstuccion_gsv.ply...")
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(all_points)
    pcd.colors = o3d.utility.Vector3dVector(all_colors)
    
    # Opcional: limpiar ruido con Statistical Outlier Removal
    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    
    o3d.io.write_point_cloud("reconstuccion_gsv.ply", pcd)
    print("¡Listo! Archivo 'reconstuccion_gsv.ply' generado exitosamente.")

if __name__ == "__main__":
    main()
