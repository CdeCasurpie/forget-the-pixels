import open3d as o3d
import numpy as np
import pyproj
import pycolmap
import os
import cv2

print("\033[96m[INFO]\033[0m Iniciando Visualizador de Puntos por Cámara...")

DIR_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Lotes"))
PATH_COLMAP = os.path.join(DIR_BASE, "nube_sparse", "0_aligned")
PATH_IMG = os.path.join(DIR_BASE, "images")

# 1. Cargar Reconstrucción
print("\033[96m[INFO]\033[0m Cargando modelo de COLMAP...")
rec = pycolmap.Reconstruction(PATH_COLMAP)
cam_list = list(rec.images.values())
cam_list.sort(key=lambda x: x.name)

# 2. Calcular centro local
transformer = pyproj.Transformer.from_crs("EPSG:4978", "EPSG:32718", always_xy=True)
transformer_back = pyproj.Transformer.from_crs("EPSG:32718", "EPSG:4978", always_xy=True)

all_pts_ecef = np.array([p.xyz for p in rec.points3D.values()])
x_u, y_u, z_u = transformer.transform(all_pts_ecef[:,0], all_pts_ecef[:,1], all_pts_ecef[:,2])
points_utm = np.column_stack((x_u, y_u, z_u))
centro_local = np.mean(points_utm, axis=0)

# Base ortogonal UTM a ECEF
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

# 3. Variables de estado
current_cam_idx = 0
show_image = True

pcd_current = o3d.geometry.PointCloud()
pcd_bg = o3d.geometry.PointCloud()
is_pcd_bg_added = False

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
    fx, fy = cam.params[0]*scale, cam.params[1]*scale
    cx, cy = cam.params[2]*scale, cam.params[3]*scale
    
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    Z_dist = 200.0
    X, Y = (u - cx)*Z_dist/fx, (v - cy)*Z_dist/fy
    Z = np.full_like(X, Z_dist)
    pts_cam = np.stack((X.flatten(), Y.flatten(), Z.flatten()), axis=1)
    
    T_ecef_to_cam = np.eye(4)
    T_ecef_to_cam[:3, :4] = img_obj.cam_from_world().matrix()
    T_cam_cv_to_local = np.linalg.inv(T_ecef_to_cam @ T_local_to_ecef)
    pts_world = (T_cam_cv_to_local[:3, :3] @ pts_cam.T).T + T_cam_cv_to_local[:3, 3]
    
    pcd_bg.points = o3d.utility.Vector3dVector(pts_world)
    pcd_bg.colors = o3d.utility.Vector3dVector(cv_img.reshape(-1, 3) / 255.0)

def refresh_view(vis):
    global current_cam_idx, is_pcd_bg_added, show_image
    img_obj = cam_list[current_cam_idx]
    cam = rec.cameras[img_obj.camera_id]
    
    # --- EXTRAER SOLO LOS PUNTOS DE ESTA CÁMARA ---
    pts_ecef = []
    colors = []
    for p2d in img_obj.points2D:
        if p2d.has_point3D():
            p3d = rec.points3D[p2d.point3D_id]
            pts_ecef.append(p3d.xyz)
            colors.append(p3d.color / 255.0)
            
    if len(pts_ecef) > 0:
        pts_ecef = np.array(pts_ecef)
        x_u, y_u, z_u = transformer.transform(pts_ecef[:,0], pts_ecef[:,1], pts_ecef[:,2])
        pts_local = np.column_stack((x_u, y_u, z_u)) - centro_local
        pcd_current.points = o3d.utility.Vector3dVector(pts_local)
        pcd_current.colors = o3d.utility.Vector3dVector(colors)
    else:
        pcd_current.points = o3d.utility.Vector3dVector()
        pcd_current.colors = o3d.utility.Vector3dVector()
    vis.update_geometry(pcd_current)
    # ----------------------------------------------
    
    update_image_plane(img_obj, cam)
    
    if show_image and not is_pcd_bg_added:
        vis.add_geometry(pcd_bg, reset_bounding_box=False); is_pcd_bg_added = True
    elif not show_image and is_pcd_bg_added:
        vis.remove_geometry(pcd_bg, reset_bounding_box=False); is_pcd_bg_added = False
    
    if show_image and is_pcd_bg_added:
        vis.update_geometry(pcd_bg)
    
    ctr = vis.get_view_control()
    param = o3d.camera.PinholeCameraParameters()
    param.intrinsic = o3d.camera.PinholeCameraIntrinsic(cam.width, cam.height, cam.params[0], cam.params[1], cam.params[2], cam.params[3])
    
    T_ecef_to_cam = np.eye(4)
    T_ecef_to_cam[:3, :4] = img_obj.cam_from_world().matrix()
    param.extrinsic = T_ecef_to_cam @ T_local_to_ecef
    
    ctr.convert_from_pinhole_camera_parameters(param, allow_arbitrary=True)
    ctr.set_constant_z_near(0.1)
    ctr.set_constant_z_far(5000.0)
    
    # Hacer los puntos más grandes para que se vean bien sobre la foto
    vis.get_render_option().point_size = 5.0
    
    return False

def key_next(vis):
    global current_cam_idx; current_cam_idx = (current_cam_idx + 1) % len(cam_list)
    print(f"\033[92m[CAMERA]\033[0m Viendo: {cam_list[current_cam_idx].name} ({len(np.asarray(pcd_current.points))} pts)"); refresh_view(vis)

def key_prev(vis):
    global current_cam_idx; current_cam_idx = (current_cam_idx - 1) % len(cam_list)
    print(f"\033[92m[CAMERA]\033[0m Viendo: {cam_list[current_cam_idx].name} ({len(np.asarray(pcd_current.points))} pts)"); refresh_view(vis)

def key_snap(vis): refresh_view(vis)

def key_toggle_img(vis):
    global show_image; show_image = not show_image; refresh_view(vis)

print("\033[96m[INFO]\033[0m Abriendo Visor de Puntos de Cámara...")
print("  - 'N' / 'B': Cambiar Cámara")
print("  - 'C'      : Encuadrar (Snap)")
print("  - 'I'      : Mostrar/Ocultar Foto de Fondo")

vis = o3d.visualization.VisualizerWithKeyCallback()
vis.create_window(window_name="Puntos Triangulados por Cámara", width=1280, height=720)
vis.get_render_option().background_color = np.asarray([0.1, 0.1, 0.1])
vis.get_render_option().point_size = 5.0

# LLENAR LOS PUNTOS ANTES DE AÑADIRLOS AL VISOR
img_obj = cam_list[current_cam_idx]
cam = rec.cameras[img_obj.camera_id]
update_image_plane(img_obj, cam)

pts_ecef, colors = [], []
for p2d in img_obj.points2D:
    if p2d.has_point3D():
        p3d = rec.points3D[p2d.point3D_id]
        pts_ecef.append(p3d.xyz)
        colors.append(p3d.color / 255.0)

if len(pts_ecef) > 0:
    pts_ecef = np.array(pts_ecef)
    x_u, y_u, z_u = transformer.transform(pts_ecef[:,0], pts_ecef[:,1], pts_ecef[:,2])
    pts_local = np.column_stack((x_u, y_u, z_u)) - centro_local
    pcd_current.points = o3d.utility.Vector3dVector(pts_local)
    pcd_current.colors = o3d.utility.Vector3dVector(colors)

vis.add_geometry(pcd_current)

vis.register_key_callback(ord('N'), key_next)
vis.register_key_callback(ord('B'), key_prev)
vis.register_key_callback(ord('C'), key_snap)
vis.register_key_callback(ord('I'), key_toggle_img)

refresh_view(vis)
print(f"\033[92m[CAMERA]\033[0m Viendo: {cam_list[current_cam_idx].name} ({len(np.asarray(pcd_current.points))} pts)")
vis.run()
vis.destroy_window()
