#!/usr/bin/env python3
"""
visualize_3d_lotes_nube.py

Este script carga la nube de puntos sparse generada por COLMAP (coordenadas ECEF),
la convierte a coordenadas UTM (para que coincida con el catastro),
y renderiza simultáneamente la nube de puntos y los lotes catastrales en 3D.
"""
import open3d as o3d
import geopandas as gpd
import numpy as np
import pyproj
from shapely.geometry import Polygon, MultiPolygon
import sys
import os

print("\033[96m[INFO]\033[0m Iniciando visualizador 3D...")

# ============================================================
# 1. RUTAS DE ARCHIVOS
# ============================================================
DIR_BASE = os.path.dirname(os.path.abspath(__file__))
PATH_NUBE = os.path.join(DIR_BASE, "nube_sparse", "sparse_1fps_aligned.ply")
PATH_SHP = os.path.join(DIR_BASE, "shp_files", "BARRANCO_LM_geogpsperu_SuyoPomalia.shp")

if not os.path.exists(PATH_NUBE):
    print(f"\033[91m[ERROR]\033[0m No se encontro la nube: {PATH_NUBE}")
    sys.exit(1)
if not os.path.exists(PATH_SHP):
    print(f"\033[91m[ERROR]\033[0m No se encontro el shapefile: {PATH_SHP}")
    sys.exit(1)

# ============================================================
# 2. CARGAR Y TRANSFORMAR NUBE DE PUNTOS (ECEF -> UTM)
# ============================================================
print("\033[96m[INFO]\033[0m Cargando nube de puntos (ECEF)...")
pcd = o3d.io.read_point_cloud(PATH_NUBE)
points_ecef = np.asarray(pcd.points)

if len(points_ecef) == 0:
    print("\033[91m[ERROR]\033[0m La nube de puntos esta vacia.")
    sys.exit(1)

print("\033[96m[INFO]\033[0m Transformando ECEF (EPSG:4978) a UTM 18S (EPSG:32718)...")
# EPSG:4978 es el sistema ECEF tridimensional
# EPSG:32718 es UTM Zona 18 Sur (Peru)
transformer = pyproj.Transformer.from_crs("EPSG:4978", "EPSG:32718", always_xy=True)

# points_ecef[:, 0] es X, [:, 1] es Y, [:, 2] es Z en ECEF
x_utm, y_utm, z_utm = transformer.transform(
    points_ecef[:, 0], points_ecef[:, 1], points_ecef[:, 2]
)

points_utm = np.column_stack((x_utm, y_utm, z_utm))

# IMPORTANTE: OpenGL (Open3D) sufre de "jittering" si las coordenadas son muy grandes
# porque los floats de 32 bits pierden precision. UTM usa valores en el rango de millones.
# Por lo tanto, desplazamos todo el espacio hacia un origen local (0, 0, 0).
centro_local = np.mean(points_utm, axis=0)
points_local = points_utm - centro_local

# Actualizar la nube de puntos con las nuevas coordenadas
pcd.points = o3d.utility.Vector3dVector(points_local)

# ============================================================
# 3. CARGAR Y FILTRAR LOTES CATASTRALES (UTM)
# ============================================================
print("\033[96m[INFO]\033[0m Cargando shapefile de lotes...")
gdf = gpd.read_file(PATH_SHP)

# Asegurar que esta en UTM 18S
if gdf.crs != "EPSG:32718":
    print("\033[93m[WARN]\033[0m Reproyectando shapefile a EPSG:32718...")
    gdf = gdf.to_crs("EPSG:32718")

# Para que el render sea rapido y limpio, solo graficamos los lotes que
# esten cerca de nuestra nube de puntos. Calculamos el Bounding Box + Margen.
MARGEN = 150.0  # metros
min_x = np.min(points_utm[:, 0]) - MARGEN
max_x = np.max(points_utm[:, 0]) + MARGEN
min_y = np.min(points_utm[:, 1]) - MARGEN
max_y = np.max(points_utm[:, 1]) + MARGEN

print(f"\033[96m[INFO]\033[0m Filtrando lotes en el area (BBox: {min_x:.0f}, {min_y:.0f} hasta {max_x:.0f}, {max_y:.0f})")
gdf_filtrado = gdf.cx[min_x:max_x, min_y:max_y]
print(f"\033[92m[OK]\033[0m Lotes a renderizar: {len(gdf_filtrado)} de {len(gdf)}")

# ============================================================
# 4. CREAR GEOMETRIA 3D DE LOS LOTES (Open3D LineSet)
# ============================================================
print("\033[96m[INFO]\033[0m Extruyendo poligonos 2D al espacio 3D...")
lines_points = []
lines_indices = []
idx = 0

# Colocamos los lotes ligeramente debajo del "suelo" real de la nube.
# Usamos el percentil 5 de Z en lugar del minimo absoluto (np.min) porque 
# COLMAP siempre genera algunos puntos "basura" flotando muy por debajo de la calle.
altura_suelo = np.percentile(points_local[:, 2], 5) - 2.0

for geom in gdf_filtrado.geometry:
    if geom is None:
        continue
        
    polygons = [geom] if isinstance(geom, Polygon) else list(geom.geoms)
    for poly in polygons:
        # Extraer coordenadas del exterior del poligono
        coords = list(poly.exterior.coords)
        for i in range(len(coords) - 1):
            # Punto inicio de la linea (aplicando el desplazamiento local!)
            p1_x = coords[i][0] - centro_local[0]
            p1_y = coords[i][1] - centro_local[1]
            
            # Punto fin de la linea
            p2_x = coords[i+1][0] - centro_local[0]
            p2_y = coords[i+1][1] - centro_local[1]
            
            lines_points.append([p1_x, p1_y, altura_suelo])
            lines_points.append([p2_x, p2_y, altura_suelo])
            lines_indices.append([idx, idx + 1])
            idx += 2

line_set = o3d.geometry.LineSet(
    points=o3d.utility.Vector3dVector(lines_points),
    lines=o3d.utility.Vector2iVector(lines_indices),
)
# Pintar los lotes de rojo para que contrasten
line_set.paint_uniform_color([1.0, 0.2, 0.2])

# ============================================================
# 5. RENDERIZAR
# ============================================================
print("\033[92m[SUCCESS]\033[0m Abriendo visor 3D (Usa el mouse para rotar, Shift+Mouse para mover)")
o3d.visualization.draw_geometries(
    [pcd, line_set],
    window_name="Proyecto Toma - COLMAP Sparse + Catastro",
    width=1280,
    height=720,
    point_show_normal=False
)
