#!/usr/bin/env python3
"""
texture_lotes.py
Genera una malla 3D texturizada de los lotes utilizando Triángulos puros y Raycasting
para evitar oclusiones y distorsiones afines (Perspective Splitting).
"""
import open3d as o3d
import geopandas as gpd
import pandas as pd
import numpy as np
import pyproj
import pycolmap
from shapely.geometry import Polygon
import trimesh
import sys
import os

print("\033[96m[INFO]\033[0m Iniciando Proyección Fotométrica V2 (Triángulos + Raycasting)...")

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
PATH_NUBE = os.path.join(DIR_BASE, "nube_sparse", "sparse_1fps_aligned.ply")
PATH_SHP = os.path.join(DIR_BASE, "shp_files", "BARRANCO_LM_geogpsperu_SuyoPomalia.shp")
PATH_COLMAP = os.path.join(DIR_BASE, "nube_sparse", "0_aligned")
PATH_OBJ = os.path.join(DIR_BASE, "lotes_texturados.obj")
PATH_MTL = os.path.join(DIR_BASE, "lotes_texturados.mtl")

pcd = o3d.io.read_point_cloud(PATH_NUBE)
points_ecef = np.asarray(pcd.points)

transformer = pyproj.Transformer.from_crs("EPSG:4978", "EPSG:32718", always_xy=True)
transformer_back = pyproj.Transformer.from_crs("EPSG:32718", "EPSG:4978", always_xy=True)

x_utm, y_utm, z_utm = transformer.transform(points_ecef[:, 0], points_ecef[:, 1], points_ecef[:, 2])
points_utm = np.column_stack((x_utm, y_utm, z_utm))
centro_local = np.mean(points_utm, axis=0)
altura_suelo_utm = np.percentile(points_utm[:, 2], 5)

print("\033[96m[INFO]\033[0m Cargando modelo COLMAP (poses)...")
rec = pycolmap.Reconstruction(PATH_COLMAP)

print("\033[96m[INFO]\033[0m Filtrando catastro al área del dron...")
gdf = gpd.read_file(PATH_SHP).to_crs("EPSG:32718")
min_x, max_x = np.min(points_utm[:, 0]) - 50.0, np.max(points_utm[:, 0]) + 50.0
min_y, max_y = np.min(points_utm[:, 1]) - 50.0, np.max(points_utm[:, 1]) + 50.0
gdf_filtrado = gdf.cx[min_x:max_x, min_y:max_y].copy()

# ---> PARCHE DE ALINEACIÓN GEOESPACIAL <---
PATH_OFFSET = os.path.join(DIR_BASE, "offset_config.json")
OFFSET_X, OFFSET_Y, ANGLE_DEG = 0.0, 0.0, 0.0
if os.path.exists(PATH_OFFSET):
    try:
        import json
        with open(PATH_OFFSET, 'r') as f:
            d = json.load(f)
            OFFSET_X, OFFSET_Y = d.get('x', 0.0), d.get('y', 0.0)
            ANGLE_DEG = d.get('angle', 0.0)
    except: pass
print(f"[PARCHE] Aplicando corrección de Catastro: X {OFFSET_X:+.2f}m, Y {OFFSET_Y:+.2f}m, Rot {ANGLE_DEG:+.2f}°")

# Calcular centro local para pivot de rotación (mismo de siempre)
transformer = pyproj.Transformer.from_crs("EPSG:4978", "EPSG:32718", always_xy=True)
points_ecef = np.asarray(pcd.points)
x_utm, y_utm, z_utm = transformer.transform(points_ecef[:, 0], points_ecef[:, 1], points_ecef[:, 2])
centro_local = np.mean(np.column_stack((x_utm, y_utm, z_utm)), axis=0)

gdf_filtrado.geometry = gdf_filtrado.geometry.rotate(ANGLE_DEG, origin=(centro_local[0], centro_local[1]))
gdf_filtrado.geometry = gdf_filtrado.geometry.translate(xoff=OFFSET_X, yoff=OFFSET_Y)
# ------------------------------------------

# Calcular Alturas
colors = np.asarray(pcd.colors)
R, G, B = colors[:, 0], colors[:, 1], colors[:, 2]
pcd_clean = o3d.geometry.PointCloud()
pcd_clean.points = o3d.utility.Vector3dVector(points_utm[(2 * G - R - B) <= 0.05])
pcd_clean, _ = pcd_clean.remove_statistical_outlier(20, 1.5)
df_pts = pd.DataFrame(np.asarray(pcd_clean.points), columns=['x', 'y', 'z'])
joined = gpd.sjoin(gpd.GeoDataFrame(df_pts, geometry=gpd.points_from_xy(df_pts.x, df_pts.y), crs="EPSG:32718"), gdf_filtrado, how='inner', predicate='within')
grouped = joined.groupby('index_right')

print("\033[96m[INFO]\033[0m Construyendo geometría base (Triangulación de Lotes)...")
vertices = []
faces = []

# Guardamos un mapeo de vértices a ECEF para la matemática de la cámara
vertices_ecef = []

def add_vertex(u_x, u_y, u_z):
    # Convertir a UTM local para el visualizador
    v_local = [u_x - centro_local[0], u_y - centro_local[1], u_z]
    vertices.append(v_local)
    
    # ECEF para proyecciones
    e_x, e_y, e_z = transformer_back.transform(u_x, u_y, u_z)
    vertices_ecef.append([e_x, e_y, e_z])
    return len(vertices) - 1

for idx, row in gdf_filtrado.iterrows():
    poly = row.geometry
    if poly is None: continue
    
    altura = 3.0
    if idx in grouped.groups:
        z_vals = grouped.get_group(idx)['z'].values
        if len(z_vals) >= 5: altura = max(3.0, np.percentile(z_vals, 90) - altura_suelo_utm)
        
    polygons = [poly] if isinstance(poly, Polygon) else list(poly.geoms)
    for p in polygons:
        coords = list(p.exterior.coords)
        for i in range(len(coords)-1):
            p1 = np.array(coords[i])
            p2 = np.array(coords[i+1])
            
            # Subdividir para evitar estiramiento (máx 3m)
            longitud = np.linalg.norm(p2[:2] - p1[:2])
            num_segs = max(1, int(np.ceil(longitud / 3.0)))
            
            for j in range(num_segs):
                sp1 = p1 + (p2 - p1) * (j / num_segs)
                sp2 = p1 + (p2 - p1) * ((j+1) / num_segs)
                
                i1 = add_vertex(sp1[0], sp1[1], altura_suelo_utm)
                i2 = add_vertex(sp2[0], sp2[1], altura_suelo_utm)
                i3 = add_vertex(sp2[0], sp2[1], altura_suelo_utm + altura)
                i4 = add_vertex(sp1[0], sp1[1], altura_suelo_utm + altura)
                
                # Crear DOS TRIÁNGULOS (en vez de un Quad)
                faces.append([i1, i2, i3])
                faces.append([i1, i3, i4])
                
        # Techos (triangulados)
        try:
            techo_v, techo_f = trimesh.creation.triangulate_polygon(p)
            idx_start = len(vertices)
            for tv in techo_v:
                add_vertex(tv[0], tv[1], altura_suelo_utm + altura)
            for tf in techo_f:
                # El techo está mirando hacia arriba (esperamos)
                faces.append([idx_start + tf[0], idx_start + tf[1], idx_start + tf[2]])
        except Exception:
            pass

vertices = np.array(vertices)
faces = np.array(faces)
vertices_ecef = np.array(vertices_ecef)

mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
print(f"\033[92m[OK]\033[0m Malla abstracta creada: {len(faces)} triángulos.")

print("\033[96m[INFO]\033[0m Calculando proyecciones y oclusiones (Raycasting)...")
f_obj = open(PATH_OBJ, "w")
f_mtl = open(PATH_MTL, "w")

f_obj.write(f"mtllib lotes_texturados.mtl\n")
for img_id, img in rec.images.items():
    f_mtl.write(f"newmtl mat_{img.name}\nKa 0.0 0.0 0.0\nKd 1.0 1.0 1.0\nmap_Kd images/{img.name}\n\n")

# Escribir vértices locales
for v in vertices:
    f_obj.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")

uv_idx = 1
triangulos_texturizados = 0

# Convertir posiciones de camara a numpy
cam_positions = {img.name: img.projection_center() for _, img in rec.images.items()}

# Preparar motor de raycasting (Trimesh automático)
intersector = mesh.ray

for face_idx, face in enumerate(faces):
    # Obtener info en ECEF para matemática matemática fotogramétrica
    ve1, ve2, ve3 = vertices_ecef[face[0]], vertices_ecef[face[1]], vertices_ecef[face[2]]
    centro_ecef = (ve1 + ve2 + ve3) / 3.0
    normal_ecef = np.cross(ve2 - ve1, ve3 - ve1)
    n_norm = np.linalg.norm(normal_ecef)
    if n_norm > 0: normal_ecef /= n_norm
    
    # Centro en coordenadas Locales para Raycasting
    centro_local_3d = (vertices[face[0]] + vertices[face[1]] + vertices[face[2]]) / 3.0
    
    best_img = None
    best_score = -1
    best_uvs = None
    
    # Recolectar candidatos
    candidatos = []
    for _, img in rec.images.items():
        cam_ecef = cam_positions[img.name]
        ray = cam_ecef - centro_ecef
        dist = np.linalg.norm(ray)
        if dist < 1.0 or dist > 150.0: continue
        
        dot = np.dot(ray / dist, normal_ecef)
        if abs(dot) > 0.02: # Permitir ángulos rasantes y obviar el orden de los vértices (winding)
            cam = rec.cameras[img.camera_id]
            u1 = cam.img_from_cam(img.cam_from_world() * ve1)
            u2 = cam.img_from_cam(img.cam_from_world() * ve2)
            u3 = cam.img_from_cam(img.cam_from_world() * ve3)
            
            if u1 is not None and u2 is not None and u3 is not None:
                xs = [u1[0], u2[0], u3[0]]
                ys = [u1[1], u2[1], u3[1]]
                if min(xs) >= 0 and max(xs) <= cam.width and min(ys) >= 0 and max(ys) <= cam.height:
                    area = (max(xs) - min(xs)) * (max(ys) - min(ys))
                    score = area * dot
                    candidatos.append({'img': img, 'score': score, 'uvs': [u1, u2, u3], 'cam_ecef': cam_ecef, 'dist': dist, 'w': cam.width, 'h': cam.height})
    
    # Ordenar candidatos por mejor puntaje
    candidatos.sort(key=lambda x: x['score'], reverse=True)
    
    # Validar oclusión usando Raycasting
    for cand in candidatos:
        # Trazar rayo desde el centro de la cara local hacia la camara en coord locales
        cam_u_x, cam_u_y, cam_u_z = transformer.transform(cand['cam_ecef'][0], cand['cam_ecef'][1], cand['cam_ecef'][2])
        cam_local = np.array([cam_u_x - centro_local[0], cam_u_y - centro_local[1], cam_u_z])
        
        ray_dir_local = cam_local - centro_local_3d
        dist_local = np.linalg.norm(ray_dir_local)
        ray_dir_local /= dist_local
        
        # Desplazar origen para no auto-intersectar la misma cara (evitar errores de precisión u overlap de lotes)
        ray_origen = centro_local_3d + ray_dir_local * 0.5
        
        # Tirar el rayo!
        locations, index_ray, index_tri = intersector.intersects_location([ray_origen], [ray_dir_local])
        
        occluded = False
        if len(locations) > 0:
            # Revisar si el choque es ANTES de llegar a la cámara
            hit_dist = np.linalg.norm(locations[0] - ray_origen)
            if hit_dist < dist_local - 1.0: # Si choca con algo 1 metro antes de la cámara...
                occluded = True
                
        if not occluded:
            best_img = cand['img']
            best_uvs = cand['uvs']
            cam_w = cand['w']
            cam_h = cand['h']
            break # Encontramos la mejor!
            
    if best_img is not None:
        f_obj.write(f"vt {best_uvs[0][0]/cam_w:.5f} {1.0 - best_uvs[0][1]/cam_h:.5f}\n")
        f_obj.write(f"vt {best_uvs[1][0]/cam_w:.5f} {1.0 - best_uvs[1][1]/cam_h:.5f}\n")
        f_obj.write(f"vt {best_uvs[2][0]/cam_w:.5f} {1.0 - best_uvs[2][1]/cam_h:.5f}\n")
        
        f_obj.write(f"usemtl mat_{best_img.name}\n")
        f_obj.write(f"f {face[0]+1}/{uv_idx} {face[1]+1}/{uv_idx+1} {face[2]+1}/{uv_idx+2}\n")
        uv_idx += 3
        triangulos_texturizados += 1
    else:
        # Sin textura
        f_obj.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")

f_obj.close()
f_mtl.close()

print(f"\033[92m[SUCCESS]\033[0m Proyección Fotométrica Finalizada.")
print(f"\033[96m[INFO]\033[0m Se exportaron {triangulos_texturizados} triángulos texturizados perfectamente.")
