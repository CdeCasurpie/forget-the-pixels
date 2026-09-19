import open3d as o3d
import geopandas as gpd
import pandas as pd
import numpy as np
import pyproj
import pycolmap
import trimesh
from shapely.geometry import Polygon
import os
import json
import cv2

print("\033[96m[INFO]\033[0m Iniciando Debugger V4 (Alineación en Vivo + Malla)...")

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
PATH_NUBE = os.path.join(DIR_BASE, "nube_sparse", "sparse_1fps_aligned.ply")
PATH_SHP = os.path.join(DIR_BASE, "shp_files", "BARRANCO_LM_geogpsperu_SuyoPomalia.shp")
PATH_COLMAP = os.path.join(DIR_BASE, "nube_sparse", "0_aligned")
PATH_IMG = os.path.join(DIR_BASE, "images")
PATH_OFFSET = os.path.join(DIR_BASE, "offset_config.json")

# Leer Offset
offset_x, offset_y, angle_deg = 0.0, 0.0, 0.0
if os.path.exists(PATH_OFFSET):
    try:
        with open(PATH_OFFSET, 'r') as f:
            d = json.load(f)
            offset_x, offset_y = d.get('x', 0.0), d.get('y', 0.0)
            angle_deg = d.get('angle', 0.0)
    except: pass
print(f"\033[92m[CONFIG]\033[0m Offset: X={offset_x:.2f}m, Y={offset_y:.2f}m, Rot={angle_deg:.2f}°")

def save_offset():
    with open(PATH_OFFSET, 'w') as f:
        json.dump({'x': offset_x, 'y': offset_y}, f)

pcd = o3d.io.read_point_cloud(PATH_NUBE)
points_ecef = np.asarray(pcd.points)

transformer = pyproj.Transformer.from_crs("EPSG:4978", "EPSG:32718", always_xy=True)
transformer_back = pyproj.Transformer.from_crs("EPSG:32718", "EPSG:4978", always_xy=True)

x_utm, y_utm, z_utm = transformer.transform(points_ecef[:, 0], points_ecef[:, 1], points_ecef[:, 2])
points_utm = np.column_stack((x_utm, y_utm, z_utm))
centro_local = np.mean(points_utm, axis=0)
altura_suelo_utm = np.percentile(points_utm[:, 2], 5)

pcd_local = o3d.geometry.PointCloud()
pcd_local.points = o3d.utility.Vector3dVector(points_utm - centro_local)
pcd_local.colors = pcd.colors

rec = pycolmap.Reconstruction(PATH_COLMAP)
cam_list = list(rec.images.values())
cam_list.sort(key=lambda x: x.name)
current_cam_idx = 0
show_image = False
pcd_bg = o3d.geometry.PointCloud()
is_pcd_bg_added = False
show_mesh = False
is_mesh_added = False
step_size = 0.25 # 25 cm por tecla

print("\033[96m[INFO]\033[0m Extruyendo polígonos y generando malla...")
gdf = gpd.read_file(PATH_SHP).to_crs("EPSG:32718")
MARGEN = 150.0
min_x, max_x = np.min(points_utm[:, 0]) - MARGEN, np.max(points_utm[:, 0]) + MARGEN
min_y, max_y = np.min(points_utm[:, 1]) - MARGEN, np.max(points_utm[:, 1]) + MARGEN
gdf_filtrado = gdf.cx[min_x:max_x, min_y:max_y].copy()
gdf_filtrado.geometry = gdf_filtrado.geometry.rotate(angle_deg, origin=(centro_local[0], centro_local[1]))
gdf_filtrado.geometry = gdf_filtrado.geometry.translate(xoff=offset_x, yoff=offset_y)

colors = np.asarray(pcd.colors)
R, G, B = colors[:, 0], colors[:, 1], colors[:, 2]
pcd_clean = o3d.geometry.PointCloud()
pcd_clean.points = o3d.utility.Vector3dVector(points_utm[(2 * G - R - B) <= 0.05])
pcd_clean, _ = pcd_clean.remove_statistical_outlier(20, 1.5)
df_pts = pd.DataFrame(np.asarray(pcd_clean.points), columns=['x', 'y', 'z'])
joined = gpd.sjoin(gpd.GeoDataFrame(df_pts, geometry=gpd.points_from_xy(df_pts.x, df_pts.y), crs="EPSG:32718"), gdf_filtrado, how='inner', predicate='within')
grouped = joined.groupby('index_right')

ls_points = []
ls_lines = []
mesh_vertices = []
mesh_faces = []

idx_lines = 0
idx_mesh = 0

for idx, row in gdf_filtrado.iterrows():
    poly = row.geometry
    if poly is None: continue
    altura = 3.0
    if idx in grouped.groups:
        z_vals = grouped.get_group(idx)['z'].values
        if len(z_vals) >= 5: altura = max(3.0, np.percentile(z_vals, 90) - altura_suelo_utm)
        
    polygons = [poly] if isinstance(poly, Polygon) else list(poly.geoms)
    for p in polygons:
        # Generar LineSet (Wireframe)
        coords = list(p.exterior.coords)
        for c in coords:
            ls_points.append([c[0] - centro_local[0], c[1] - centro_local[1], altura_suelo_utm - centro_local[2]])
            ls_points.append([c[0] - centro_local[0], c[1] - centro_local[1], altura_suelo_utm + altura - centro_local[2]])
        for i in range(len(coords)-1):
            base1 = idx_lines + i*2
            top1  = base1 + 1
            base2 = idx_lines + (i+1)*2
            top2  = base2 + 1
            ls_lines.extend([[base1, base2], [top1, top2], [base1, top1]])
        ls_lines.append([idx_lines + (len(coords)-1)*2, idx_lines + (len(coords)-1)*2 + 1])
        idx_lines += len(coords)*2

        # Generar TriangleMesh (Planos sólidos)
        try:
            techo_v, techo_f = trimesh.creation.triangulate_polygon(p)
            for v in techo_v:
                mesh_vertices.append([v[0] - centro_local[0], v[1] - centro_local[1], altura_suelo_utm + altura - centro_local[2]])
            for f in techo_f:
                mesh_faces.append([f[0] + idx_mesh, f[1] + idx_mesh, f[2] + idx_mesh])
            idx_mesh += len(techo_v)
            
            # Paredes
            for i in range(len(coords)-1):
                p1, p2 = coords[i], coords[i+1]
                v_idx = len(mesh_vertices)
                mesh_vertices.append([p1[0] - centro_local[0], p1[1] - centro_local[1], altura_suelo_utm - centro_local[2]])
                mesh_vertices.append([p2[0] - centro_local[0], p2[1] - centro_local[1], altura_suelo_utm - centro_local[2]])
                mesh_vertices.append([p2[0] - centro_local[0], p2[1] - centro_local[1], altura_suelo_utm + altura - centro_local[2]])
                mesh_vertices.append([p1[0] - centro_local[0], p1[1] - centro_local[1], altura_suelo_utm + altura - centro_local[2]])
                mesh_faces.extend([[v_idx, v_idx+1, v_idx+2], [v_idx, v_idx+2, v_idx+3]])
                idx_mesh += 4
        except:
            pass

line_set = o3d.geometry.LineSet()
line_set.points = o3d.utility.Vector3dVector(ls_points)
line_set.lines = o3d.utility.Vector2iVector(ls_lines)
line_set.paint_uniform_color([1, 0, 0])

mesh_lotes = o3d.geometry.TriangleMesh()
if len(mesh_vertices) > 0:
    mesh_lotes.vertices = o3d.utility.Vector3dVector(mesh_vertices)
    mesh_lotes.triangles = o3d.utility.Vector3iVector(mesh_faces)
    mesh_lotes.compute_vertex_normals()
    mesh_lotes.paint_uniform_color([0.2, 0.8, 0.2]) # Verde suave
    # Open3D legacy no soporta transparencia RGBA fácilmente, así que usaremos el color y toggle.

o_ecef = transformer_back.transform(centro_local[0], centro_local[1], centro_local[2])
x_ecef = transformer_back.transform(centro_local[0]+1, centro_local[1], centro_local[2])
y_ecef = transformer_back.transform(centro_local[0], centro_local[1]+1, centro_local[2])
z_ecef = transformer_back.transform(centro_local[0], centro_local[1], centro_local[2]+1)
vec_x = (np.array(x_ecef) - np.array(o_ecef)); vec_x /= np.linalg.norm(vec_x)
vec_y = (np.array(y_ecef) - np.array(o_ecef)); vec_y /= np.linalg.norm(vec_y)
vec_z = (np.array(z_ecef) - np.array(o_ecef)); vec_z /= np.linalg.norm(vec_z)

T_local_to_ecef = np.eye(4)
T_local_to_ecef[:3, 0] = vec_x
T_local_to_ecef[:3, 1] = vec_y
T_local_to_ecef[:3, 2] = vec_z
T_local_to_ecef[:3, 3] = o_ecef

U, _, Vt = np.linalg.svd(T_local_to_ecef[:3, :3])
T_local_to_ecef[:3, :3] = U @ Vt

def update_image_plane(img_obj, cam):
    global pcd_bg
    img_path = os.path.join(PATH_IMG, img_obj.name)
    if not os.path.exists(img_path): return
    cv_img = cv2.imread(img_path)
    if cv_img is None: return
    scale = 0.25
    cv_img = cv2.resize(cv_img, (0,0), fx=scale, fy=scale)
    cv_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    
    H, W, _ = cv_img.shape
    fx, fy = cam.params[0] * scale, cam.params[1] * scale
    cx, cy = cam.params[2] * scale, cam.params[3] * scale
    
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    Z_dist = 200.0
    X, Y = (u - cx) * Z_dist / fx, (v - cy) * Z_dist / fy
    Z = np.full_like(X, Z_dist)
    pts_cam = np.stack((X.flatten(), Y.flatten(), Z.flatten()), axis=1)
    
    T_ecef_to_cam = np.eye(4)
    T_ecef_to_cam[:3, :4] = img_obj.cam_from_world().matrix()
    T_cam_cv_to_local = np.linalg.inv(T_ecef_to_cam @ T_local_to_ecef)
    pts_world = (T_cam_cv_to_local[:3, :3] @ pts_cam.T).T + T_cam_cv_to_local[:3, 3]
    
    pcd_bg.points = o3d.utility.Vector3dVector(pts_world)
    pcd_bg.colors = o3d.utility.Vector3dVector(cv_img.reshape(-1, 3) / 255.0)

def refresh_view(vis):
    global current_cam_idx, is_pcd_bg_added, show_image, is_mesh_added, show_mesh
    img_obj = cam_list[current_cam_idx]
    cam = rec.cameras[img_obj.camera_id]
    
    update_image_plane(img_obj, cam)
    
    if show_image and not is_pcd_bg_added:
        vis.add_geometry(pcd_bg, reset_bounding_box=False); is_pcd_bg_added = True
    elif not show_image and is_pcd_bg_added:
        vis.remove_geometry(pcd_bg, reset_bounding_box=False); is_pcd_bg_added = False
    if show_image and is_pcd_bg_added: vis.update_geometry(pcd_bg)
        
    if show_mesh and not is_mesh_added:
        vis.add_geometry(mesh_lotes, reset_bounding_box=False); is_mesh_added = True
    elif not show_mesh and is_mesh_added:
        vis.remove_geometry(mesh_lotes, reset_bounding_box=False); is_mesh_added = False
    
    ctr = vis.get_view_control()
    param = o3d.camera.PinholeCameraParameters()
    param.intrinsic = o3d.camera.PinholeCameraIntrinsic(cam.width, cam.height, cam.params[0], cam.params[1], cam.params[2], cam.params[3])
    
    T_ecef_to_cam = np.eye(4)
    T_ecef_to_cam[:3, :4] = img_obj.cam_from_world().matrix()
    param.extrinsic = T_ecef_to_cam @ T_local_to_ecef
    
    ctr.convert_from_pinhole_camera_parameters(param, allow_arbitrary=True)
    ctr.set_constant_z_near(0.1)
    ctr.set_constant_z_far(5000.0)
    return False

def move_cad(dx, dy, vis):
    global offset_x, offset_y
    offset_x += dx; offset_y += dy
    line_set.translate((dx, dy, 0))
    mesh_lotes.translate((dx, dy, 0))
    vis.update_geometry(line_set)
    if is_mesh_added: vis.update_geometry(mesh_lotes)
    save_offset()
    print(f"\033[92m[ALINEACIÓN]\033[0m Offset Guardado: X {offset_x:+.2f} m, Y {offset_y:+.2f} m")
    return False

def key_next(vis):
    global current_cam_idx; current_cam_idx = (current_cam_idx + 1) % len(cam_list)
    print(f"\033[92m[CAMERA]\033[0m Viendo: {cam_list[current_cam_idx].name}"); refresh_view(vis)
def key_prev(vis):
    global current_cam_idx; current_cam_idx = (current_cam_idx - 1) % len(cam_list)
    print(f"\033[92m[CAMERA]\033[0m Viendo: {cam_list[current_cam_idx].name}"); refresh_view(vis)
def key_snap(vis): refresh_view(vis)
def key_toggle_img(vis):
    global show_image; show_image = not show_image; refresh_view(vis)
def key_toggle_mesh(vis):
    global show_mesh; show_mesh = not show_mesh; refresh_view(vis)
    print(f"\033[93m[TOGGLE]\033[0m Malla Sólida: {'ENCENDIDA' if show_mesh else 'APAGADA'}")

def key_w(vis): return move_cad(0, step_size, vis)
def key_s(vis): return move_cad(0, -step_size, vis)
def key_d(vis): return move_cad(step_size, 0, vis)
def key_a(vis): return move_cad(-step_size, 0, vis)
def key_plus(vis):
    global step_size; step_size *= 2.0; print(f"Velocidad: {step_size:.2f} m"); return False
def key_minus(vis):
    global step_size; step_size /= 2.0; print(f"Velocidad: {step_size:.2f} m"); return False

print("\033[96m[INFO]\033[0m Abriendo Visor...")
print("  - 'N'/'B' : Cambiar Cámara")
print("  - 'C'     : Encuadrar (Snap)")
print("  - 'I'     : Mostrar Fondo Fotográfico")
print("  - 'M'     : Mostrar Planos Sólidos (Malla verde)")
print("  - W/A/S/D : Mover Catastro en VIVO")
print("  - '+' / '-' : Cambiar velocidad de movimiento")

vis = o3d.visualization.VisualizerWithKeyCallback()
vis.create_window(window_name="Debugger (Offset en Vivo)", width=1280, height=720)
vis.get_render_option().background_color = np.asarray([0.1, 0.1, 0.1])
vis.add_geometry(pcd_local)
vis.add_geometry(line_set)

vis.register_key_callback(ord('N'), key_next)
vis.register_key_callback(ord('B'), key_prev)
vis.register_key_callback(ord('C'), key_snap)
vis.register_key_callback(ord('I'), key_toggle_img)
vis.register_key_callback(ord('M'), key_toggle_mesh)
vis.register_key_callback(ord('W'), key_w)
vis.register_key_callback(ord('S'), key_s)
vis.register_key_callback(ord('A'), key_a)
vis.register_key_callback(ord('D'), key_d)
vis.register_key_callback(ord('='), key_plus)
vis.register_key_callback(ord('+'), key_plus)
vis.register_key_callback(ord('-'), key_minus)

refresh_view(vis)
vis.run()
vis.destroy_window()
