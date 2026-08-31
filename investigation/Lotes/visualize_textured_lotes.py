#!/usr/bin/env python3
"""
visualize_textured_lotes.py

Visor 3D interactivo que integra:
1. La nube de puntos dispersa (original).
2. El mapa catastral 2D (líneas).
3. Los edificios 3D extruidos Y texturizados fotométricamente.
"""
import open3d as o3d
import geopandas as gpd
import numpy as np
import pyproj
import trimesh
from shapely.geometry import Polygon
import os

print("\033[96m[INFO]\033[0m Iniciando Visor Maestro (Texturas + Nube + Catastro)...")

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
PATH_NUBE = os.path.join(DIR_BASE, "nube_sparse", "sparse_1fps_aligned.ply")
PATH_SHP = os.path.join(DIR_BASE, "shp_files", "BARRANCO_LM_geogpsperu_SuyoPomalia.shp")
PATH_OBJ = os.path.join(DIR_BASE, "lotes_texturados.obj")

# 1. CARGAR NUBE Y TRANSFORMAR A UTM LOCAL (Igual que los otros scripts)
print("\033[96m[INFO]\033[0m Cargando Nube de Puntos (ECEF)...")
pcd = o3d.io.read_point_cloud(PATH_NUBE)
points_ecef = np.asarray(pcd.points)
colors = np.asarray(pcd.colors)

print("\033[96m[INFO]\033[0m Transformando ECEF -> UTM...")
transformer = pyproj.Transformer.from_crs("EPSG:4978", "EPSG:32718", always_xy=True)
x_utm, y_utm, z_utm = transformer.transform(points_ecef[:, 0], points_ecef[:, 1], points_ecef[:, 2])
points_utm = np.column_stack((x_utm, y_utm, z_utm))

centro_local = np.mean(points_utm, axis=0)
points_local = points_utm - centro_local
points_local[:, 2] = points_utm[:, 2] # Mantener el Z original como en texture_lotes.py

# Crear PointCloud para Trimesh
pc_trimesh = trimesh.points.PointCloud(vertices=points_local, colors=(colors * 255).astype(np.uint8))

# 2. CARGAR CATASTRO Y CREAR LÍNEAS 3D
print("\033[96m[INFO]\033[0m Cargando Mapa Catastral 2D...")
gdf = gpd.read_file(PATH_SHP)
if gdf.crs != "EPSG:32718":
    gdf = gdf.to_crs("EPSG:32718")

MARGEN = 150.0
min_x, max_x = np.min(points_utm[:, 0]) - MARGEN, np.max(points_utm[:, 0]) + MARGEN
min_y, max_y = np.min(points_utm[:, 1]) - MARGEN, np.max(points_utm[:, 1]) + MARGEN
gdf_filtrado = gdf.cx[min_x:max_x, min_y:max_y].copy()

altura_suelo = np.percentile(points_utm[:, 2], 5)

rutas_2d = []
for idx, row in gdf_filtrado.iterrows():
    poly = row.geometry
    if poly is None: continue
    polygons = [poly] if isinstance(poly, Polygon) else list(poly.geoms)
    
    for p in polygons:
        coords = np.array(p.exterior.coords)
        # Transformar a UTM Local
        coords[:, 0] -= centro_local[0]
        coords[:, 1] -= centro_local[1]
        
        # Añadir Z
        coords_3d = np.column_stack((coords[:, 0], coords[:, 1], np.full(len(coords), altura_suelo)))
        
        # Crear Path3D
        rutas_2d.append(trimesh.load_path(coords_3d))

# Combinar todas las rutas en un solo Path para rendimiento
if rutas_2d:
    mapa_3d = trimesh.path.util.concatenate(rutas_2d)
    mapa_3d.colors = np.tile([255, 0, 0, 255], (len(mapa_3d.entities), 1)) # Rojo
else:
    mapa_3d = None

# 3. CARGAR EDIFICIOS TEXTURIZADOS
print("\033[96m[INFO]\033[0m Cargando Edificios Texturizados (.OBJ + .MTL)...")
# Trimesh lee automáticamente los .mtl y aplica las imágenes UV
escena_texturizada = trimesh.load(PATH_OBJ)

# 4. ENSAMBLAR ESCENA Y MOSTRAR
print("\033[92m[SUCCESS]\033[0m Ensamblando escena final...")
scene = trimesh.Scene()
scene.add_geometry(pc_trimesh)
if mapa_3d:
    scene.add_geometry(mapa_3d)

# Añadir cada material/malla de la escena texturizada
for geom_name, geom in escena_texturizada.geometry.items():
    scene.add_geometry(geom)

print("\033[92m[OK]\033[0m Abriendo visor. (Arrastra con el click izquierdo para rotar, click derecho para pan)")
# Configurar pyglet para que evite fallos de OpenGL core context en Wayland
try:
    import pyglet
    pyglet.options['shadow_window'] = False
except:
    pass

scene.show(
    caption="PFC1 - Visor Final: Catastro 2D + Puntos + Texturas Proyectadas",
    smooth=False, # Mantiene las caras planas de los edificios
    background=[40, 40, 40, 255]
)
