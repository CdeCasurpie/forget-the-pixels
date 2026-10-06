import cv2
import numpy as np
import geopandas as gpd
import open3d as o3d
import pyproj
import contextily as cx
from shapely.geometry import Polygon
import json
import os

print("\033[96m[INFO]\033[0m Iniciando Alineador 2D Satelital...")

DIR_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Lotes"))
PATH_NUBE = os.path.join(DIR_BASE, "nube_sparse", "sparse_1fps_aligned.ply")
PATH_SHP = os.path.join(DIR_BASE, "shp_files", "BARRANCO_LM_geogpsperu_SuyoPomalia.shp")
PATH_OFFSET = os.path.join(DIR_BASE, "offset_config.json")

# 1. Cargar offset inicial
offset_x, offset_y, angle_deg = 0.0, 0.0, 0.0
if os.path.exists(PATH_OFFSET):
    try:
        with open(PATH_OFFSET, 'r') as f:
            d = json.load(f)
            offset_x = d.get('x', 0.0)
            offset_y = d.get('y', 0.0)
            angle_deg = d.get('angle', 0.0)
    except: pass

def save_offset():
    with open(PATH_OFFSET, 'w') as f:
        json.dump({'x': offset_x, 'y': offset_y, 'angle': angle_deg}, f)

# 2. Cargar nube para saber los límites
pcd = o3d.io.read_point_cloud(PATH_NUBE)
points_ecef = np.asarray(pcd.points)

transformer = pyproj.Transformer.from_crs("EPSG:4978", "EPSG:32718", always_xy=True)
x_utm, y_utm, z_utm = transformer.transform(points_ecef[:, 0], points_ecef[:, 1], points_ecef[:, 2])
points_utm = np.column_stack((x_utm, y_utm, z_utm))
centro_local = np.mean(points_utm, axis=0)

min_x, max_x = np.min(points_utm[:, 0]) - 50, np.max(points_utm[:, 0]) + 50
min_y, max_y = np.min(points_utm[:, 1]) - 50, np.max(points_utm[:, 1]) + 50

# 3. Cargar Shapefile y recortar
gdf = gpd.read_file(PATH_SHP).to_crs("EPSG:32718")
gdf_filtrado = gdf.cx[min_x:max_x, min_y:max_y].copy()
geom_original = gdf_filtrado.geometry.copy() # Guardar geometría original

# 4. Obtener límites en WGS84 para Contextily
transformer_wgs84 = pyproj.Transformer.from_crs("EPSG:32718", "EPSG:4326", always_xy=True)
lon_min, lat_min = transformer_wgs84.transform(min_x, min_y)
lon_max, lat_max = transformer_wgs84.transform(max_x, max_y)

print("\033[96m[INFO]\033[0m Descargando imagen satelital...")
img_basemap, ext_wm = cx.bounds2img(lon_min, lat_min, lon_max, lat_max, ll=True, zoom=19, source=cx.providers.Esri.WorldImagery)
img_basemap = cv2.cvtColor(img_basemap, cv2.COLOR_RGBA2BGR)
H, W, _ = img_basemap.shape

wm_min_x, wm_max_x, wm_min_y, wm_max_y = ext_wm
res_x = (wm_max_x - wm_min_x) / W
res_y = (wm_max_y - wm_min_y) / H
# Factor de conversión aproximado de píxeles a metros UTM (para el mouse)
meters_per_px_x = (max_x - min_x) / W
meters_per_px_y = (max_y - min_y) / H

# Variables de UI
dragging = False
rotating = False
last_mx, last_my = 0, 0
window_name = "Alineador 2D (Click Izquierdo: Mover | Click Derecho: Rotar)"

def render():
    global img_basemap, gdf_filtrado, offset_x, offset_y, angle_deg
    
    # Aplicar transformación en UTM
    geom_transformed = geom_original.rotate(angle_deg, origin=(centro_local[0], centro_local[1]))
    geom_transformed = geom_transformed.translate(xoff=offset_x, yoff=offset_y)
    
    # Proyectar a Web Mercator para dibujar
    gdf_temp = gpd.GeoDataFrame(geometry=geom_transformed, crs="EPSG:32718")
    gdf_wm = gdf_temp.to_crs("EPSG:3857")
    
    img_draw = img_basemap.copy()
    
    for poly in gdf_wm.geometry:
        if poly is None: continue
        polygons = [poly] if isinstance(poly, Polygon) else list(poly.geoms)
        for p in polygons:
            coords = np.array(p.exterior.coords)
            # Convertir coordenadas Web Mercator a píxeles
            px = ((coords[:, 0] - wm_min_x) / res_x).astype(np.int32)
            py = (H - (coords[:, 1] - wm_min_y) / res_y).astype(np.int32) # Y invierte en imágenes
            pts = np.column_stack((px, py)).reshape((-1, 1, 2))
            cv2.polylines(img_draw, [pts], isClosed=True, color=(0, 0, 255), thickness=2)
            
    # Texto de estado
    text = f"Offset X: {offset_x:+.2f}m  Y: {offset_y:+.2f}m  Rot: {angle_deg:+.2f} deg"
    cv2.putText(img_draw, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4)
    cv2.putText(img_draw, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
    
    cv2.imshow(window_name, img_draw)

def mouse_callback(event, x, y, flags, param):
    global dragging, rotating, last_mx, last_my, offset_x, offset_y, angle_deg
    
    if event == cv2.EVENT_LBUTTONDOWN:
        dragging = True
        last_mx, last_my = x, y
    elif event == cv2.EVENT_RBUTTONDOWN:
        rotating = True
        last_mx, last_my = x, y
    elif event == cv2.EVENT_LBUTTONUP:
        dragging = False
        save_offset()
    elif event == cv2.EVENT_RBUTTONUP:
        rotating = False
        save_offset()
    elif event == cv2.EVENT_MOUSEMOVE:
        if dragging:
            dx = x - last_mx
            dy = y - last_my
            # En la imagen, +Y es abajo, por lo que arrastrar abajo aumenta dy. 
            # UTM Y es norte (arriba). Así que invertimos dy.
            offset_x += dx * meters_per_px_x
            offset_y -= dy * meters_per_px_y
            last_mx, last_my = x, y
            render()
        elif rotating:
            dx = x - last_mx
            angle_deg -= dx * 0.1 # Sensibilidad de rotación
            last_mx, last_my = x, y
            render()

cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.resizeWindow(window_name, 1000, 1000)
cv2.setMouseCallback(window_name, mouse_callback)

print("\n\033[97m" + "="*50)
print(" CONTROLES DE ALINEACIÓN 2D")
print("="*50)
print("  Click IZQUIERDO y Arrastrar : Trasladar (X, Y)")
print("  Click DERECHO y Arrastrar   : Rotar (Ángulo)")
print("  Presiona 'ESC' o 'Q'        : Guardar y Salir")
print("="*50 + "\033[0m\n")

render()
while True:
    k = cv2.waitKey(1) & 0xFF
    if k == 27 or k == ord('q'): # ESC o Q
        break

save_offset()
cv2.destroyAllWindows()
