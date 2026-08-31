import open3d as o3d
import geopandas as gpd
import numpy as np
import pyproj
import os

print("\033[96m[INFO]\033[0m Iniciando Herramienta de Alineación Manual (Catastro vs Dron)")

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
PATH_NUBE = os.path.join(DIR_BASE, "nube_sparse", "sparse_1fps_aligned.ply")
PATH_SHP = os.path.join(DIR_BASE, "shp_files", "BARRANCO_LM_geogpsperu_SuyoPomalia.shp")

# 1. Cargar Nube
print("\033[96m[INFO]\033[0m Cargando nube de puntos...")
pcd = o3d.io.read_point_cloud(PATH_NUBE)
points_ecef = np.asarray(pcd.points)

transformer = pyproj.Transformer.from_crs("EPSG:4978", "EPSG:32718", always_xy=True)
x_utm, y_utm, z_utm = transformer.transform(points_ecef[:, 0], points_ecef[:, 1], points_ecef[:, 2])
points_utm = np.column_stack((x_utm, y_utm, z_utm))
centro_local = np.mean(points_utm, axis=0)
altura_suelo_utm = np.percentile(points_utm[:, 2], 5)

pcd_local = o3d.geometry.PointCloud()
pcd_local.points = o3d.utility.Vector3dVector(points_utm - centro_local)
pcd_local.colors = pcd.colors

# 2. Cargar Lotes y hacer LineSet
print("\033[96m[INFO]\033[0m Cargando polígonos del catastro...")
gdf = gpd.read_file(PATH_SHP).to_crs("EPSG:32718")
MARGEN = 150.0
min_x, max_x = np.min(points_utm[:, 0]) - MARGEN, np.max(points_utm[:, 0]) + MARGEN
min_y, max_y = np.min(points_utm[:, 1]) - MARGEN, np.max(points_utm[:, 1]) + MARGEN
gdf_filtrado = gdf.cx[min_x:max_x, min_y:max_y]

ls_points = []
ls_lines = []
idx_offset = 0

from shapely.geometry import Polygon
for idx, row in gdf_filtrado.iterrows():
    poly = row.geometry
    if poly is None: continue
    polygons = [poly] if isinstance(poly, Polygon) else list(poly.geoms)
    for p in polygons:
        coords = list(p.exterior.coords)
        for c in coords:
            ls_points.append([c[0] - centro_local[0], c[1] - centro_local[1], altura_suelo_utm - centro_local[2]])
        for i in range(len(coords)-1):
            ls_lines.append([idx_offset + i, idx_offset + i + 1])
        idx_offset += len(coords)

line_set = o3d.geometry.LineSet()
line_set.points = o3d.utility.Vector3dVector(ls_points)
line_set.lines = o3d.utility.Vector2iVector(ls_lines)
line_set.paint_uniform_color([1, 0, 0]) # Rojo para el catastro

# Variables de estado
offset_x = 0.0
offset_y = 0.0
step_size = 0.5 # 50 cm

def move(dx, dy, vis):
    global offset_x, offset_y
    offset_x += dx
    offset_y += dy
    line_set.translate((dx, dy, 0.0))
    vis.update_geometry(line_set)
    print(f"\033[92m[ALINEACIÓN]\033[0m Offset actual -> X: {offset_x:+.2f} m, Y: {offset_y:+.2f} m")
    return False

def key_w(vis): return move(0, step_size, vis)
def key_s(vis): return move(0, -step_size, vis)
def key_d(vis): return move(step_size, 0, vis)
def key_a(vis): return move(-step_size, 0, vis)

def key_plus(vis):
    global step_size
    step_size *= 2.0
    print(f"\033[93m[PASO]\033[0m Velocidad aumentada a: {step_size:.2f} m")
    return False

def key_minus(vis):
    global step_size
    step_size /= 2.0
    print(f"\033[93m[PASO]\033[0m Velocidad reducida a: {step_size:.2f} m")
    return False

vis = o3d.visualization.VisualizerWithKeyCallback()
vis.create_window(window_name="Alineador de Catastro (WASD para mover)", width=1280, height=720)
vis.get_render_option().background_color = np.asarray([0.1, 0.1, 0.1])
vis.add_geometry(pcd_local)
vis.add_geometry(line_set)

# WASD
vis.register_key_callback(ord('W'), key_w)
vis.register_key_callback(ord('S'), key_s)
vis.register_key_callback(ord('A'), key_a)
vis.register_key_callback(ord('D'), key_d)
# Teclas + y - (en algunos teclados es = y -)
vis.register_key_callback(ord('='), key_plus)
vis.register_key_callback(ord('+'), key_plus)
vis.register_key_callback(ord('-'), key_minus)

print("\n\033[97m" + "="*50)
print(" CONTROLES DE ALINEACIÓN")
print("="*50)
print("  [W] : Mover al NORTE (+Y)")
print("  [S] : Mover al SUR (-Y)")
print("  [D] : Mover al ESTE (+X)")
print("  [A] : Mover al OESTE (-X)")
print("  [+] : Aumentar tamaño del paso (más rápido)")
print("  [-] : Reducir tamaño del paso (más precisión)")
print("="*50 + "\033[0m\n")

vis.run()
vis.destroy_window()
