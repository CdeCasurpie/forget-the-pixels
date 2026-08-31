#!/usr/bin/env python3
"""
extrude_lotes.py

Este script carga la nube de puntos y el catastro, realiza un Spatial Join
para encontrar qué puntos caen dentro de qué lote, filtra la vegetación y 
el ruido, calcula la altura óptima del techo (roof) y extruye los polígonos
catastrales en 3D.
"""
import open3d as o3d
import geopandas as gpd
import pandas as pd
import numpy as np
import pyproj
import trimesh
from shapely.geometry import Polygon
import shapely.affinity
import sys
import os

print("\033[96m[INFO]\033[0m Iniciando motor de extrusión 3D (Lotes -> Edificios)...")

# ============================================================
# 1. RUTAS DE ARCHIVOS
# ============================================================
DIR_BASE = os.path.dirname(os.path.abspath(__file__))
PATH_NUBE = os.path.join(DIR_BASE, "nube_sparse", "sparse_1fps_aligned.ply")
PATH_SHP = os.path.join(DIR_BASE, "shp_files", "BARRANCO_LM_geogpsperu_SuyoPomalia.shp")

# ============================================================
# 2. CARGAR Y TRANSFORMAR NUBE (ECEF -> UTM)
# ============================================================
print("\033[96m[INFO]\033[0m Cargando nube de puntos...")
pcd = o3d.io.read_point_cloud(PATH_NUBE)
points_ecef = np.asarray(pcd.points)
colors = np.asarray(pcd.colors)  # RGB [0, 1]

transformer = pyproj.Transformer.from_crs("EPSG:4978", "EPSG:32718", always_xy=True)
x_utm, y_utm, z_utm = transformer.transform(points_ecef[:, 0], points_ecef[:, 1], points_ecef[:, 2])
points_utm = np.column_stack((x_utm, y_utm, z_utm))

# Origen local
centro_local = np.mean(points_utm, axis=0)
points_local = points_utm - centro_local
pcd.points = o3d.utility.Vector3dVector(points_local)

# ============================================================
# 3. LIMPIEZA LÓGICA (Solo para calcular altura, NO se borran del render final)
# ============================================================
print("\033[96m[INFO]\033[0m Filtrando vegetación y ruido para el cálculo de alturas...")
R, G, B = colors[:, 0], colors[:, 1], colors[:, 2]

# Índice de Exceso de Verde (Excess Green) para detectar árboles/pastos
ExG = 2 * G - R - B
is_vegetation = ExG > 0.05  # Umbral para considerar un punto como planta

# Nos quedamos con los puntos que NO son vegetación
points_no_veg = points_local[~is_vegetation]

# Limpiamos ruido estadístico (puntos flotantes en el cielo o subterráneos)
pcd_clean = o3d.geometry.PointCloud()
pcd_clean.points = o3d.utility.Vector3dVector(points_no_veg)
# remove_statistical_outlier devuelve (nube_filtrada, indices_validos)
pcd_clean, ind = pcd_clean.remove_statistical_outlier(nb_neighbors=20, std_ratio=1.5)
points_clean = np.asarray(pcd_clean.points)

print(f"\033[92m[OK]\033[0m Puntos limpios usados para medir altura: {len(points_clean)} (de {len(points_local)} originales)")

# ============================================================
# 4. CARGAR Y DESPLAZAR CATASTRO
# ============================================================
print("\033[96m[INFO]\033[0m Cargando y desplazando catastro...")
gdf = gpd.read_file(PATH_SHP)
if gdf.crs != "EPSG:32718":
    gdf = gdf.to_crs("EPSG:32718")

MARGEN = 150.0
min_x, max_x = np.min(points_utm[:, 0]) - MARGEN, np.max(points_utm[:, 0]) + MARGEN
min_y, max_y = np.min(points_utm[:, 1]) - MARGEN, np.max(points_utm[:, 1]) + MARGEN
gdf_filtrado = gdf.cx[min_x:max_x, min_y:max_y].copy()

# Desplazar polígonos al origen local para que el cruce coincida
def shift_polygon(geom):
    if geom is None: return None
    return shapely.affinity.translate(geom, xoff=-centro_local[0], yoff=-centro_local[1])

gdf_filtrado.geometry = gdf_filtrado.geometry.apply(shift_polygon)

# ============================================================
# 5. SPATIAL JOIN (Cruce de Puntos con Polígonos)
# ============================================================
print("\033[96m[INFO]\033[0m Ejecutando Spatial Join (emparejando puntos con lotes)...")
df_pts = pd.DataFrame(points_clean, columns=['x', 'y', 'z'])
geom_pts = gpd.points_from_xy(df_pts.x, df_pts.y)
gdf_pts = gpd.GeoDataFrame(df_pts, geometry=geom_pts)

# Cruce espacial: ¿Qué punto cae dentro de qué lote?
joined = gpd.sjoin(gdf_pts, gdf_filtrado, how='inner', predicate='within')
grouped = joined.groupby('index_right')

# ============================================================
# 6. EXTRUSIÓN 3D (Lotes a Edificios)
# ============================================================
print("\033[96m[INFO]\033[0m Calculando alturas y construyendo mallas 3D...")
# Altura base (suelo): calculada sobre la nube original para ser robustos
altura_suelo = np.percentile(points_local[:, 2], 5)

final_mesh = o3d.geometry.TriangleMesh()

lotes_observados = 0
lotes_por_defecto = 0

for idx, row in gdf_filtrado.iterrows():
    poly = row.geometry
    if poly is None: continue
    
    # Extraer polígonos simples (si es un MultiPolygon, iteramos)
    polygons = [poly] if isinstance(poly, Polygon) else list(poly.geoms)
    
    # Calcular altura del edificio
    if idx in grouped.groups:
        z_vals = grouped.get_group(idx)['z'].values
        if len(z_vals) >= 5:
            # Usamos el percentil 90 de altura dentro de este lote
            roof_z = np.percentile(z_vals, 90)
            height = max(3.0, roof_z - altura_suelo)
            color = [0.9, 0.9, 0.9] # Blanco mate para edificios observados
            lotes_observados += 1
        else:
            height = 3.0 # Altura por defecto (1 piso) si hay muy pocos puntos
            color = [0.8, 0.6, 0.6] # Rojizo para lotes ciegos (sin vista de dron)
            lotes_por_defecto += 1
    else:
        height = 3.0
        color = [0.8, 0.6, 0.6]
        lotes_por_defecto += 1
        
    for p in polygons:
        try:
            # Extruir polígono usando Trimesh
            tm = trimesh.creation.extrude_polygon(p, height=height)
            
            # Trimesh extruye desde Z=0. Subimos el edificio al nivel del suelo real.
            tm.vertices[:, 2] += altura_suelo
            
            # Convertir la malla a formato Open3D
            o3d_mesh = o3d.geometry.TriangleMesh()
            o3d_mesh.vertices = o3d.utility.Vector3dVector(tm.vertices)
            o3d_mesh.triangles = o3d.utility.Vector3iVector(tm.faces)
            o3d_mesh.compute_vertex_normals()
            o3d_mesh.paint_uniform_color(color)
            
            # Sumar a la malla maestra (para renderizar todo súper rápido)
            final_mesh += o3d_mesh
        except Exception as e:
            # Polígonos topológicamente inválidos a veces fallan al extruir
            pass

print(f"\033[92m[OK]\033[0m Malla construida: {lotes_observados} edif. calculados reales, {lotes_por_defecto} lotes por defecto (1 piso).")

# ============================================================
# 7. RENDER
# ============================================================
import pycolmap

print("\033[96m[INFO]\033[0m Cargando cámaras del dron para visualizarlas...")
try:
    rec = pycolmap.Reconstruction(os.path.join(DIR_BASE, "nube_sparse", "sparse_1fps_aligned.ply").replace("sparse_1fps_aligned.ply", "0_aligned"))
    cam_meshes = []
    
    # Crear un material/color rojo para las camaras
    for img_id, img in rec.images.items():
        # ECEF
        c_ecef = img.projection_center()
        
        # Transformar a UTM
        x_u, y_u, z_u = transformer.transform(c_ecef[0], c_ecef[1], c_ecef[2])
        
        # Transformar a Local
        x_l = x_u - centro_local[0]
        y_l = y_u - centro_local[1]
        z_l = z_u - centro_local[2] # Ajuste Z al centro local
        
        # Crear un pequeño tetraedro o esfera roja para representar la camara
        # Usaremos octaedros/esferas pequeñas para mejor rendimiento
        cam_mesh = o3d.geometry.TriangleMesh.create_octahedron(radius=2.0)
        cam_mesh.paint_uniform_color([1.0, 0.0, 0.0]) # Rojo puro
        cam_mesh.translate([x_l, y_l, z_l])
        
        cam_meshes.append(cam_mesh)
        
    print(f"\033[92m[SUCCESS]\033[0m Se cargaron {len(cam_meshes)} cámaras como indicadores rojos.")
except Exception as e:
    print(f"\033[93m[WARNING]\033[0m No se pudieron cargar las cámaras: {e}")
    cam_meshes = []

print("\033[92m[SUCCESS]\033[0m Abriendo visor 3D...")

o3d.visualization.draw_geometries(
    [pcd, final_mesh] + cam_meshes,
    window_name="PFC1 - Extrusión Paramétrica Catastro + Nube Sparse",
    width=1280,
    height=720,
    mesh_show_wireframe=True,
    mesh_show_back_face=False
)
