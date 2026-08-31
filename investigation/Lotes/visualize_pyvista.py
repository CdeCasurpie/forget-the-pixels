#!/usr/bin/env python3
"""
visualize_pyvista.py

Visor 3D interactivo usando PyVista (VTK Backend).
Reemplaza a Trimesh para evitar problemas de pantalla negra con Pyglet en Arch Linux / Wayland.
"""
import pyvista as pv
import open3d as o3d
import geopandas as gpd
import numpy as np
import pyproj
from shapely.geometry import Polygon
import os

print("\033[96m[INFO]\033[0m Iniciando Visor Maestro (Backend: PyVista VTK)...")

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
PATH_NUBE = os.path.join(DIR_BASE, "nube_sparse", "sparse_1fps_aligned.ply")
PATH_SHP = os.path.join(DIR_BASE, "shp_files", "BARRANCO_LM_geogpsperu_SuyoPomalia.shp")
PATH_OBJ = os.path.join(DIR_BASE, "lotes_texturados.obj")

plotter = pv.Plotter(title="PFC1 - Visor Final: Catastro 2D + Puntos + Texturas Proyectadas")
plotter.set_background("#282828") # Fondo gris oscuro

# 1. CARGAR NUBE DE PUNTOS
print("\033[96m[INFO]\033[0m Cargando Nube de Puntos (ECEF -> UTM)...")
pcd = o3d.io.read_point_cloud(PATH_NUBE)
points_ecef = np.asarray(pcd.points)
colors = np.asarray(pcd.colors)

transformer = pyproj.Transformer.from_crs("EPSG:4978", "EPSG:32718", always_xy=True)
x_utm, y_utm, z_utm = transformer.transform(points_ecef[:, 0], points_ecef[:, 1], points_ecef[:, 2])
points_utm = np.column_stack((x_utm, y_utm, z_utm))

centro_local = np.mean(points_utm, axis=0)
points_local = points_utm - centro_local
points_local[:, 2] = points_utm[:, 2] # Mantener Z original

pc_vt = pv.PolyData(points_local)
pc_vt['RGB'] = (colors * 255).astype(np.uint8)
plotter.add_mesh(pc_vt, scalars='RGB', rgb=True, point_size=3.0, render_points_as_spheres=True)

# 2. CARGAR CATASTRO 2D (Lineas Rojas)
print("\033[96m[INFO]\033[0m Cargando Mapa Catastral 2D...")
gdf = gpd.read_file(PATH_SHP)
if gdf.crs != "EPSG:32718":
    gdf = gdf.to_crs("EPSG:32718")

MARGEN = 150.0
min_x, max_x = np.min(points_utm[:, 0]) - MARGEN, np.max(points_utm[:, 0]) + MARGEN
min_y, max_y = np.min(points_utm[:, 1]) - MARGEN, np.max(points_utm[:, 1]) + MARGEN
gdf_filtrado = gdf.cx[min_x:max_x, min_y:max_y].copy()

altura_suelo = np.percentile(points_utm[:, 2], 5)

for idx, row in gdf_filtrado.iterrows():
    poly = row.geometry
    if poly is None: continue
    polygons = [poly] if isinstance(poly, Polygon) else list(poly.geoms)
    
    for p in polygons:
        coords = np.array(p.exterior.coords)
        coords[:, 0] -= centro_local[0]
        coords[:, 1] -= centro_local[1]
        coords_3d = np.column_stack((coords[:, 0], coords[:, 1], np.full(len(coords), altura_suelo)))
        
        # Crear lineas en PyVista
        lines_poly = pv.PolyData()
        lines_poly.points = coords_3d
        cells = np.full((len(coords_3d)-1, 3), 2, dtype=np.int_)
        cells[:, 1] = np.arange(0, len(coords_3d)-1)
        cells[:, 2] = np.arange(1, len(coords_3d))
        lines_poly.lines = cells
        plotter.add_mesh(lines_poly, color='red', line_width=2.0)

# 3. CARGAR EDIFICIOS TEXTURIZADOS
print("\033[96m[INFO]\033[0m Cargando Edificios Texturizados (.OBJ + .MTL)...")
try:
    mesh_obj = pv.read(PATH_OBJ)
    plotter.add_mesh(mesh_obj, smooth_shading=False)
except Exception as e:
    print(f"\033[91m[ERROR]\033[0m Error cargando texturas en PyVista: {e}")

print("\033[92m[SUCCESS]\033[0m Ensamblando escena final...")
plotter.show()
