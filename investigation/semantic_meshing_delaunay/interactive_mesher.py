import os
import cv2
import struct
import numpy as np
import open3d as o3d
import pycolmap
import warnings
from scipy.spatial import Delaunay

warnings.filterwarnings("ignore")

print("\033[96m[INFO]\033[0m Iniciando Mesher Global (Delaunay 2D + Texturas UV)...")

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(DIR_BASE, "data")
PLY_PATH = os.path.join(DATA_DIR, "fused_lightglue.ply")
VIS_PATH = os.path.join(DATA_DIR, "fused_lightglue.ply.vis")
SPARSE_DIR = os.path.join(DATA_DIR, "sparse")
PATH_IMG = os.path.join(DATA_DIR, "images")

print("[INFO] Cargando nube densa...")
pcd_full = o3d.io.read_point_cloud(PLY_PATH)
dense_points = np.asarray(pcd_full.points)
dense_colors = np.asarray(pcd_full.colors)

OFFSET = np.mean(dense_points, axis=0)
dense_points -= OFFSET

pcd_local = o3d.geometry.PointCloud()
pcd_local.points = o3d.utility.Vector3dVector(dense_points)
pcd_local.colors = o3d.utility.Vector3dVector(dense_colors)

print("[INFO] Parseando archivo de visibilidad (.vis)...")
image_to_points = {}
if os.path.exists(VIS_PATH):
    with open(VIS_PATH, "rb") as f:
        num_points = struct.unpack("<Q", f.read(8))[0]
        for pt_idx in range(num_points):
            num_visible_images = struct.unpack("<I", f.read(4))[0]
            image_ids = struct.unpack("<" + "I"*num_visible_images, f.read(4*num_visible_images))
            for img_id in image_ids:
                if img_id not in image_to_points:
                    image_to_points[img_id] = []
                image_to_points[img_id].append(pt_idx)

print("[INFO] Cargando modelo COLMAP...")
rec = pycolmap.Reconstruction(SPARSE_DIR)

cam_list = [img for img in rec.images.values() if img.image_id in image_to_points and len(image_to_points[img.image_id]) > 0]
cam_list = sorted(cam_list, key=lambda x: x.name)
current_cam_idx = 0

show_image = False
show_pcd = True
show_mesh = True
is_pcd_bg_added = False
is_pcd_local_added = True
is_mesh_added = False

camera_locked = True
pcd_bg = o3d.geometry.PointCloud()
mesh_semantic = o3d.geometry.TriangleMesh()

cache_meshes = {}

def get_shifted_camera_matrix(img_obj):
    T_world_to_cam = np.eye(4)
    if hasattr(img_obj, 'cam_from_world'):
        T_world_to_cam[:3, :4] = img_obj.cam_from_world().matrix()
    else:
        T_world_to_cam[:3, :3] = img_obj.rotmat()
        T_world_to_cam[:3, 3] = img_obj.tvec
        
    R = T_world_to_cam[:3, :3]
    t = T_world_to_cam[:3, 3]
    T_shifted_to_cam = np.eye(4)
    T_shifted_to_cam[:3, :3] = R
    T_shifted_to_cam[:3, 3] = (R @ OFFSET) + t
    return T_shifted_to_cam

def update_image_plane(img_obj, cam):
    global pcd_bg
    img_path = os.path.join(PATH_IMG, img_obj.name)
    if not os.path.exists(img_path): return False
    cv_img = cv2.imread(img_path)
    if cv_img is None: return False
    
    cv_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    
    scale = 0.25
    cv_img = cv2.resize(cv_img, (0,0), fx=scale, fy=scale)
    H, W, _ = cv_img.shape
    fx, fy = cam.params[0] * scale, cam.params[1] * scale
    cx, cy = cam.params[2] * scale, cam.params[3] * scale
    
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    pts3d, _, _ = extract_visible_points(img_obj)
    if len(pts3d) > 0:
        T_shifted_to_cam = get_shifted_camera_matrix(img_obj)
        R = T_shifted_to_cam[:3, :3]
        t = T_shifted_to_cam[:3, 3].reshape(3, 1)
        pts_cam = (R @ pts3d.T) + t
        median_z = np.median(pts_cam[2, :])
        Z_dist = max(10.0, median_z * 1.5)
    else:
        Z_dist = 50.0
    X, Y = (u - cx) * Z_dist / fx, (v - cy) * Z_dist / fy
    Z = np.full_like(X, Z_dist)
    pts_cam = np.stack((X.flatten(), Y.flatten(), Z.flatten()), axis=1)
    
    T_shifted_to_cam = get_shifted_camera_matrix(img_obj)
    T_cam_to_shifted = np.linalg.inv(T_shifted_to_cam)
    pts_world = (T_cam_to_shifted[:3, :3] @ pts_cam.T).T + T_cam_to_shifted[:3, 3]
    
    pcd_bg.points = o3d.utility.Vector3dVector(pts_world)
    pcd_bg.colors = o3d.utility.Vector3dVector(cv_img.reshape(-1, 3) / 255.0)
    return True

def extract_visible_points(img_obj):
    idx = image_to_points[img_obj.image_id]
    return dense_points[idx], dense_colors[idx], idx

def refresh_view(vis):
    global is_pcd_bg_added, is_pcd_local_added, is_mesh_added
    
    if not cam_list: return False
    img_obj = cam_list[current_cam_idx]
    cam = rec.cameras[img_obj.camera_id]
    
    has_image = update_image_plane(img_obj, cam)
    if show_image and has_image and not is_pcd_bg_added:
        vis.add_geometry(pcd_bg, reset_bounding_box=False); is_pcd_bg_added = True
    elif (not show_image or not has_image) and is_pcd_bg_added:
        vis.remove_geometry(pcd_bg, reset_bounding_box=False); is_pcd_bg_added = False
    if is_pcd_bg_added: vis.update_geometry(pcd_bg)
        
    if show_pcd:
        pts, cols, _ = extract_visible_points(img_obj)
        if len(pts) > 0:
            pcd_local.points = o3d.utility.Vector3dVector(pts)
            pcd_local.colors = o3d.utility.Vector3dVector(cols)
            if not is_pcd_local_added:
                vis.add_geometry(pcd_local, reset_bounding_box=False); is_pcd_local_added = True
            else:
                vis.update_geometry(pcd_local)
        else:
            if is_pcd_local_added:
                vis.remove_geometry(pcd_local, reset_bounding_box=False); is_pcd_local_added = False
    else:
        if is_pcd_local_added:
            vis.remove_geometry(pcd_local, reset_bounding_box=False); is_pcd_local_added = False

    if show_mesh:
        if img_obj.image_id in cache_meshes:
            data = cache_meshes[img_obj.image_id]
            
            # Remover para actualizar limpiamente las texturas
            if is_mesh_added:
                vis.remove_geometry(mesh_semantic, reset_bounding_box=False)
            
            mesh_semantic.vertices = o3d.utility.Vector3dVector(data['verts'])
            mesh_semantic.triangles = o3d.utility.Vector3iVector(data['tris'])
            
            # Texturizado UV
            mesh_semantic.vertex_colors = o3d.utility.Vector3dVector([]) # Limpiar colores
            mesh_semantic.triangle_uvs = o3d.utility.Vector2dVector(data['uvs'])
            mesh_semantic.textures = [o3d.geometry.Image(data['texture'])]
            mesh_semantic.triangle_material_ids = o3d.utility.IntVector(np.zeros(len(data['tris']), dtype=np.int32))
            
            vis.add_geometry(mesh_semantic, reset_bounding_box=False)
            is_mesh_added = True
        else:
            if is_mesh_added:
                vis.remove_geometry(mesh_semantic, reset_bounding_box=False); is_mesh_added = False
    else:
        if is_mesh_added:
            vis.remove_geometry(mesh_semantic, reset_bounding_box=False); is_mesh_added = False
    
    if camera_locked:
        ctr = vis.get_view_control()
        param = o3d.camera.PinholeCameraParameters()
        if hasattr(cam, 'calibration_matrix'):
            param.intrinsic = o3d.camera.PinholeCameraIntrinsic(cam.width, cam.height, cam.params[0], cam.params[1], cam.params[2], cam.params[3])
        else:
            param.intrinsic = o3d.camera.PinholeCameraIntrinsic(cam.width, cam.height, cam.params[0], cam.params[0], cam.params[1], cam.params[2])
        
        param.extrinsic = get_shifted_camera_matrix(img_obj)
        
        ctr.convert_from_pinhole_camera_parameters(param, allow_arbitrary=True)
        ctr.set_constant_z_near(0.1)
        ctr.set_constant_z_far(5000.0)
    
    return False

def key_next(vis):
    global current_cam_idx, camera_locked; 
    current_cam_idx = (current_cam_idx + 1) % len(cam_list); camera_locked = True
    print(f"\033[92m[CAMERA]\033[0m Viendo: {cam_list[current_cam_idx].name}"); refresh_view(vis)

def key_prev(vis):
    global current_cam_idx, camera_locked; 
    current_cam_idx = (current_cam_idx - 1) % len(cam_list); camera_locked = True
    print(f"\033[92m[CAMERA]\033[0m Viendo: {cam_list[current_cam_idx].name}"); refresh_view(vis)

def key_orbit(vis):
    global camera_locked
    camera_locked = False
    print("\033[95m[ORBITA]\033[0m Modo Órbita Libre. Manteniendo la cámara en la posición exacta del Dron.")
def key_toggle_img(vis):
    global show_image; show_image = not show_image; refresh_view(vis)

def key_toggle_pcd(vis):
    global show_pcd; show_pcd = not show_pcd; refresh_view(vis)

def key_toggle_mesh(vis):
    global show_mesh; show_mesh = not show_mesh; refresh_view(vis)

def key_w(vis):
    global camera_locked
    if camera_locked: return False
    ctr = vis.get_view_control()
    param = ctr.convert_to_pinhole_camera_parameters()
    ex = np.copy(param.extrinsic)
    R, t = ex[:3, :3], ex[:3, 3]
    forward = np.linalg.inv(R) @ np.array([0, 0, 1])
    E = -np.linalg.inv(R) @ t
    E_new = E + 5.0 * forward
    ex[:3, 3] = -R @ E_new
    param.extrinsic = ex
    ctr.convert_from_pinhole_camera_parameters(param, allow_arbitrary=True)
    return False

def key_s(vis):
    global camera_locked
    if camera_locked: return False
    ctr = vis.get_view_control()
    param = ctr.convert_to_pinhole_camera_parameters()
    ex = np.copy(param.extrinsic)
    R, t = ex[:3, :3], ex[:3, 3]
    forward = np.linalg.inv(R) @ np.array([0, 0, 1])
    E = -np.linalg.inv(R) @ t
    E_new = E - 5.0 * forward
    ex[:3, 3] = -R @ E_new
    param.extrinsic = ex
    ctr.convert_from_pinhole_camera_parameters(param, allow_arbitrary=True)
    return False

def key_center_ray(vis):
    global camera_locked
    if camera_locked:
        print("\033[93m[AVISO]\033[0m Desbloquea la cámara con F primero para centrar la vista libre.")
        return False
    ctr = vis.get_view_control()
    param = ctr.convert_to_pinhole_camera_parameters()
    extrinsic = param.extrinsic
    R = extrinsic[:3, :3]
    t = extrinsic[:3, 3]
    E = -np.linalg.inv(R) @ t
    forward = np.linalg.inv(R) @ np.array([0, 0, 1])
    forward = forward / np.linalg.norm(forward)
    pts3d = np.asarray(pcd_local.points)
    if len(pts3d) == 0: return False
    vecs = pts3d - E
    t_vals = vecs @ forward
    valid = t_vals > 0
    if not np.any(valid): return False
    vecs_valid = vecs[valid]
    t_valid = t_vals[valid]
    pts_valid = pts3d[valid]
    ortho_dists = np.linalg.norm(vecs_valid - t_valid.reshape(-1, 1) * forward, axis=1)
    best_idx = np.argmin(ortho_dists)
    L = pts_valid[best_idx]
    ctr.set_lookat(L)
    print("\033[96m[CENTRO]\033[0m Órbita anclada al punto central de tu pantalla (Rayo Cast).")
    return False

def key_mesh(vis):
    global show_mesh
    img_obj = cam_list[current_cam_idx]
    cam = rec.cameras[img_obj.camera_id]
    
    print("\033[95m[MALLA]\033[0m Ejecutando Delaunay 2D y Mapeo UV (Texturas)...")
    
    pts3d, cols, _ = extract_visible_points(img_obj)
    if len(pts3d) < 3:
        print("\033[91m[MALLA]\033[0m No hay suficientes puntos.")
        return False
        
    T_shifted_to_cam = get_shifted_camera_matrix(img_obj)
    R = T_shifted_to_cam[:3, :3]
    t = T_shifted_to_cam[:3, 3].reshape(3, 1)
    pts_cam = (R @ pts3d.T) + t
    
    if hasattr(cam, 'calibration_matrix'): K = cam.calibration_matrix()
    else: K = np.eye(3); K[0,0] = cam.params[0]; K[1,1] = cam.params[0]; K[0,2] = cam.params[1]; K[1,2] = cam.params[2]
        
    pts_px = (K @ pts_cam)
    pts_px = pts_px[:2, :] / pts_px[2, :]
    pts_2d = pts_px.T
    
    try:
        tri = Delaunay(pts_2d)
    except Exception as e:
        print(f"\033[91m[ERROR]\033[0m Falló Delaunay: {e}")
        return False
        
    # --- PROCESO DE TEXTURIZADO (UV MAPPING) ---
    img_path = os.path.join(PATH_IMG, img_obj.name)
    img_rgb = cv2.imread(img_path)
    if img_rgb is not None:
        img_rgb = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2RGB)
        H_img, W_img = img_rgb.shape[:2]
        
        # Coordenadas UV: u = x/W, v = 1 - y/H (Open3D espera v=0 abajo)
        u = np.clip(pts_2d[:, 0] / W_img, 0.0, 1.0)
        v = np.clip(pts_2d[:, 1] / H_img, 0.0, 1.0)
        uvs = np.column_stack((u, v))
        
        # Open3D requiere 3 coordenadas UV por cada triángulo (3 * num_triangles, 2)
        tri_uvs = np.zeros((len(tri.simplices) * 3, 2))
        for i, face in enumerate(tri.simplices):
            tri_uvs[i*3 + 0] = uvs[face[0]]
            tri_uvs[i*3 + 1] = uvs[face[1]]
            tri_uvs[i*3 + 2] = uvs[face[2]]
    else:
        tri_uvs = None
        img_rgb = None
    
    cache_meshes[img_obj.image_id] = {
        'verts': pts3d,
        'tris': tri.simplices,
        'cols': cols,
        'uvs': tri_uvs,
        'texture': img_rgb
    }
    
    print(f"\033[95m[MALLA]\033[0m Malla global creada con {len(tri.simplices)} triángulos TEXTURIZADOS.")
    
    show_mesh = True 
    refresh_view(vis)
    return False

print("\033[96m[INFO]\033[0m Abriendo Visor...")
print(" --- NAVEGACIÓN ---")
print("  - 'N' / 'B' : Cambiar Cámara")
print("  - 'F'       : Órbita Libre (centrada en la mediana)")
print(" --- VISIBILIDAD ---")
print("  - 'H'       : Mostrar/Ocultar Nube")
print("  - 'I'       : Mostrar/Ocultar Foto")
print("  - 'J'       : Mostrar/Ocultar Malla Texturizada")
print(" --- ALGORITMO ---")
print("  - 'R'       : Crear Malla Global (Delaunay 2D con Texturas UV)")
print("  - 'C'       : Centrar Órbita en el punto bajo la mira (Raycast)")
print("  - 'W' / 'S' : Caminar Hacia Adelante / Atrás (Supera el límite de zoom)")

vis = o3d.visualization.VisualizerWithKeyCallback()
vis.create_window(window_name="Semantic Mesher (Delaunay Global Texturizado)", width=1280, height=720)
vis.get_render_option().background_color = np.asarray([0.1, 0.1, 0.1])
vis.get_render_option().mesh_show_back_face = True
vis.add_geometry(pcd_local)

vis.register_key_callback(ord('N'), key_next)
vis.register_key_callback(ord('B'), key_prev)
vis.register_key_callback(ord('F'), key_orbit)
vis.register_key_callback(ord('I'), key_toggle_img)
vis.register_key_callback(ord('H'), key_toggle_pcd)
vis.register_key_callback(ord('J'), key_toggle_mesh)
vis.register_key_callback(ord('R'), key_mesh)
vis.register_key_callback(ord('C'), key_center_ray)
vis.register_key_callback(ord('W'), key_w)
vis.register_key_callback(ord('S'), key_s)

refresh_view(vis)
vis.run()
vis.destroy_window()
