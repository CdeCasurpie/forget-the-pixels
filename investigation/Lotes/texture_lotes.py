#!/usr/bin/env python3
"""
texture_lotes.py

Proyección fotométrica (Olvida los Píxeles - Fase 3)
Calcula las paredes de los lotes catastrales y usa la matemática de COLMAP
para proyectar los píxeles de los drones directamente como texturas UV.
"""
import open3d as o3d
import geopandas as gpd
import pandas as pd
import numpy as np
import pyproj
import pycolmap
from shapely.geometry import Polygon
import shapely.affinity
import sys
import os

print("\033[96m[INFO]\033[0m Iniciando Proyección Fotométrica (Olvida los Píxeles)...")

# 1. RUTAS
DIR_BASE = os.path.dirname(os.path.abspath(__file__))
PATH_NUBE = os.path.join(DIR_BASE, "nube_sparse", "sparse_1fps_aligned.ply")
PATH_SHP = os.path.join(DIR_BASE, "shp_files", "BARRANCO_LM_geogpsperu_SuyoPomalia.shp")
PATH_COLMAP = os.path.join(DIR_BASE, "nube_sparse", "0_aligned")
PATH_OBJ = os.path.join(DIR_BASE, "lotes_texturados.obj")
PATH_MTL = os.path.join(DIR_BASE, "lotes_texturados.mtl")

# 2. CARGAR DATA GEOMÉTRICA
pcd = o3d.io.read_point_cloud(PATH_NUBE)
points_ecef = np.asarray(pcd.points)

transformer = pyproj.Transformer.from_crs("EPSG:4978", "EPSG:32718", always_xy=True)
x_utm, y_utm, z_utm = transformer.transform(points_ecef[:, 0], points_ecef[:, 1], points_ecef[:, 2])
points_utm = np.column_stack((x_utm, y_utm, z_utm))
centro_local = np.mean(points_utm, axis=0) # Origen local

print("\033[96m[INFO]\033[0m Cargando modelo COLMAP (poses)...")
try:
    rec = pycolmap.Reconstruction(PATH_COLMAP)
    print(f"\033[92m[OK]\033[0m {len(rec.images)} imágenes con poses cargadas.")
except Exception as e:
    print(f"\033[91m[ERROR]\033[0m No se pudo cargar COLMAP: {e}")
    sys.exit(1)

# Usamos el catastro original (sin desplazar al origen) porque las cámaras
# de COLMAP en este experimento están en coordenadas ECEF originales!
# CUIDADO: La cámara de COLMAP está en ECEF. La proyección de ECEF a píxeles 
# funciona directamente con img.cam_from_world() * punto_ECEF.
# Por lo tanto, ¡todas nuestras intersecciones matemáticas deben hacerse en ECEF!

# Pero el Shapefile está en UTM. Vamos a convertir el Shapefile a ECEF.
print("\033[96m[INFO]\033[0m Convirtiendo Catastro UTM -> ECEF para texturizado...")
gdf = gpd.read_file(PATH_SHP)
if gdf.crs != "EPSG:32718":
    gdf = gdf.to_crs("EPSG:32718")

# Filtrar BBox en UTM para ser rápidos
MARGEN = 150.0
min_x, max_x = np.min(points_utm[:, 0]) - MARGEN, np.max(points_utm[:, 0]) + MARGEN
min_y, max_y = np.min(points_utm[:, 1]) - MARGEN, np.max(points_utm[:, 1]) + MARGEN
gdf_filtrado = gdf.cx[min_x:max_x, min_y:max_y].copy()

# Para calcular alturas en ECEF es complicado porque ECEF es curvo (es la Tierra).
# Vamos a extraer los polígonos, asignarles Z en UTM (usando el 5to y 90mo percentil igual que extrude_lotes),
# y LUEGO convertir los vértices de las paredes de UTM -> ECEF.
transformer_back = pyproj.Transformer.from_crs("EPSG:32718", "EPSG:4978", always_xy=True)

# Alturas en UTM
altura_suelo_utm = np.percentile(points_utm[:, 2], 5)

# Necesitamos unir puntos UTM a los polígonos UTM para sacar las alturas
print("\033[96m[INFO]\033[0m Calculando alturas de los lotes...")
colors = np.asarray(pcd.colors)
R, G, B = colors[:, 0], colors[:, 1], colors[:, 2]
ExG = 2 * G - R - B
is_veg = ExG > 0.05
pcd_clean = o3d.geometry.PointCloud()
pcd_clean.points = o3d.utility.Vector3dVector(points_utm[~is_veg])
pcd_clean, ind = pcd_clean.remove_statistical_outlier(20, 1.5)
pts_clean_utm = np.asarray(pcd_clean.points)

df_pts = pd.DataFrame(pts_clean_utm, columns=['x', 'y', 'z'])
geom_pts = gpd.points_from_xy(df_pts.x, df_pts.y)
gdf_pts = gpd.GeoDataFrame(df_pts, geometry=geom_pts)
joined = gpd.sjoin(gdf_pts, gdf_filtrado, how='inner', predicate='within')
grouped = joined.groupby('index_right')

# ============================================================
# 3. TEXTURIZACIÓN Y ESCRITURA OBJ
# ============================================================
print("\033[96m[INFO]\033[0m Proyectando texturas y escribiendo OBJ...")

f_obj = open(PATH_OBJ, "w")
f_mtl = open(PATH_MTL, "w")

f_obj.write(f"mtllib lotes_texturados.mtl\n")

# Crear el MTL
for img_id, img in rec.images.items():
    f_mtl.write(f"newmtl mat_{img.name}\n")
    f_mtl.write(f"Ka 1.0 1.0 1.0\nKd 1.0 1.0 1.0\n")
    f_mtl.write(f"map_Kd images/{img.name}\n\n")

vertex_idx = 1
uv_idx = 1
paredes_texturizadas = 0

for idx, row in gdf_filtrado.iterrows():
    poly = row.geometry
    if poly is None: continue
    
    # Altura en UTM
    if idx in grouped.groups:
        z_vals = grouped.get_group(idx)['z'].values
        if len(z_vals) >= 5:
            roof_z = np.percentile(z_vals, 90)
            altura = max(3.0, roof_z - altura_suelo_utm)
        else:
            altura = 3.0
    else:
        altura = 3.0
        
    polygons = [poly] if isinstance(poly, Polygon) else list(poly.geoms)
    
    for p in polygons:
        coords = list(p.exterior.coords)
        for i in range(len(coords)-1):
            p1_utm = coords[i]
            p2_utm = coords[i+1]
            
            # Vértices de la pared en UTM
            v1_u = [p1_utm[0], p1_utm[1], altura_suelo_utm]
            v2_u = [p2_utm[0], p2_utm[1], altura_suelo_utm]
            v3_u = [p2_utm[0], p2_utm[1], altura_suelo_utm + altura]
            v4_u = [p1_utm[0], p1_utm[1], altura_suelo_utm + altura]
            
            # Convertir a ECEF
            x_e, y_e, z_e = transformer_back.transform(
                [v1_u[0], v2_u[0], v3_u[0], v4_u[0]],
                [v1_u[1], v2_u[1], v3_u[1], v4_u[1]],
                [v1_u[2], v2_u[2], v3_u[2], v4_u[2]]
            )
            v1_e = np.array([x_e[0], y_e[0], z_e[0]])
            v2_e = np.array([x_e[1], y_e[1], z_e[1]])
            v3_e = np.array([x_e[2], y_e[2], z_e[2]])
            v4_e = np.array([x_e[3], y_e[3], z_e[3]])
            
            # Escribir vértices espaciales en el OBJ (desplazados al origen local ECEF o UTM?
            # ECEF puro es gigante. Los OBJ fallan con números gigantes. Desplazaremos el OBJ a centro_local de UTM!)
            # Asi que los vertices del OBJ seran en UTM local (facil para 3D viewer)
            
            v1_local = v1_u - np.append(centro_local[:2], 0)
            v2_local = v2_u - np.append(centro_local[:2], 0)
            v3_local = v3_u - np.append(centro_local[:2], 0)
            v4_local = v4_u - np.append(centro_local[:2], 0)
            v1_local[2] = v1_u[2] # No desplazamos Z
            v2_local[2] = v2_u[2]
            v3_local[2] = v3_u[2]
            v4_local[2] = v4_u[2]
            
            f_obj.write(f"v {v1_local[0]:.4f} {v1_local[1]:.4f} {v1_local[2]:.4f}\n")
            f_obj.write(f"v {v2_local[0]:.4f} {v2_local[1]:.4f} {v2_local[2]:.4f}\n")
            f_obj.write(f"v {v3_local[0]:.4f} {v3_local[1]:.4f} {v3_local[2]:.4f}\n")
            f_obj.write(f"v {v4_local[0]:.4f} {v4_local[1]:.4f} {v4_local[2]:.4f}\n")
            
            # Buscar mejor camara (en ECEF)
            centro_ecef = (v1_e + v2_e + v3_e + v4_e) / 4.0
            
            # Normal de la pared (ECEF)
            vec1 = v2_e - v1_e
            vec2 = v4_e - v1_e
            normal_ecef = np.cross(vec1, vec2)
            norm = np.linalg.norm(normal_ecef)
            if norm > 0: normal_ecef /= norm
            
            best_img = None
            best_score = -9999
            
            for img_id, img in rec.images.items():
                cam_center = img.projection_center()
                ray = cam_center - centro_ecef
                dist = np.linalg.norm(ray)
                if dist < 1.0 or dist > 150.0: continue # Muy cerca o muy lejos
                
                ray_dir = ray / dist
                dot = np.dot(ray_dir, normal_ecef)
                
                if dot > 0.2: # La camara esta de frente a la pared
                    # Proyectar centro
                    p2d = rec.cameras[img.camera_id].img_from_cam(img.cam_from_world() * centro_ecef)
                    cam = rec.cameras[img.camera_id]
                    if p2d is not None and 0 <= p2d[0] < cam.width and 0 <= p2d[1] < cam.height:
                        score = dot / dist # Mas perpendicular y mas cerca = mejor
                        if score > best_score:
                            best_score = score
                            best_img = img
                            
            if best_img is not None:
                # Calcular UVs para los 4 vertices
                cam = rec.cameras[best_img.camera_id]
                uv1 = cam.img_from_cam(best_img.cam_from_world() * v1_e)
                uv2 = cam.img_from_cam(best_img.cam_from_world() * v2_e)
                uv3 = cam.img_from_cam(best_img.cam_from_world() * v3_e)
                uv4 = cam.img_from_cam(best_img.cam_from_world() * v4_e)
                
                if uv1 is not None and uv2 is not None and uv3 is not None and uv4 is not None:
                    f_obj.write(f"vt {uv1[0]/cam.width:.5f} {1.0 - uv1[1]/cam.height:.5f}\n")
                    f_obj.write(f"vt {uv2[0]/cam.width:.5f} {1.0 - uv2[1]/cam.height:.5f}\n")
                    f_obj.write(f"vt {uv3[0]/cam.width:.5f} {1.0 - uv3[1]/cam.height:.5f}\n")
                    f_obj.write(f"vt {uv4[0]/cam.width:.5f} {1.0 - uv4[1]/cam.height:.5f}\n")
                    
                    f_obj.write(f"usemtl mat_{best_img.name}\n")
                    f_obj.write(f"f {vertex_idx}/{uv_idx} {vertex_idx+1}/{uv_idx+1} {vertex_idx+2}/{uv_idx+2} {vertex_idx+3}/{uv_idx+3}\n")
                    uv_idx += 4
                    paredes_texturizadas += 1
                else:
                    f_obj.write(f"f {vertex_idx} {vertex_idx+1} {vertex_idx+2} {vertex_idx+3}\n")
            else:
                # Escribir sin textura (o un color base)
                f_obj.write(f"f {vertex_idx} {vertex_idx+1} {vertex_idx+2} {vertex_idx+3}\n")
                
            vertex_idx += 4

f_obj.close()
f_mtl.close()

print(f"\033[92m[SUCCESS]\033[0m Se escribio {PATH_OBJ} con {paredes_texturizadas} paredes texturizadas perfectamente desde el dron.")
print("\033[96m[INFO]\033[0m Ahora puedes abrir este archivo en Blender o con un visor 3D para asombrarte.")
