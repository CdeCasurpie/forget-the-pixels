import os
import cv2
import struct
import numpy as np
import open3d as o3d
import pycolmap
import warnings
from scipy.spatial import Delaunay
import copy

warnings.filterwarnings("ignore")

print("\033[96m[INFO]\033[0m Iniciando Mesher Multi-Vista (Grafo con Mapeo UV y Z-Stretch Cull)...")

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(DIR_BASE, "data")
# (Usamos nube sparse interna)

SPARSE_DIR = os.path.join(DATA_DIR, "sparse")
PATH_IMG = os.path.join(DATA_DIR, "images")

print("[INFO] Cargando reconstruccion Sparse y Visibilidad desde pycolmap...")
rec = pycolmap.Reconstruction(SPARSE_DIR)

dense_points = []
dense_colors = []
image_to_points = {}

for pt3d_id, pt in rec.points3D.items():
    idx = len(dense_points)
    dense_points.append(pt.xyz)
    dense_colors.append(pt.color / 255.0)
    for track_el in pt.track.elements:
        img_id = track_el.image_id
        if img_id not in image_to_points:
            image_to_points[img_id] = []
        image_to_points[img_id].append(idx)

dense_points = np.array(dense_points)
dense_colors = np.array(dense_colors)

OFFSET = np.mean(dense_points, axis=0)
dense_points -= OFFSET

pcd_local = o3d.geometry.PointCloud()
pcd_local.points = o3d.utility.Vector3dVector(dense_points)
pcd_local.colors = o3d.utility.Vector3dVector(dense_colors)

cam_list = [img for img in rec.images.values() if img.image_id in image_to_points and len(image_to_points[img.image_id]) > 0]
cam_list = sorted(cam_list, key=lambda x: x.name)
current_cam_idx = 0

show_image = False
show_pcd = True
is_pcd_bg_added = False
is_pcd_local_added = True
camera_locked = True
pcd_bg = o3d.geometry.PointCloud()

# Variables para Malla Global
show_global = False
is_global_added = False
global_faces_set = set()
global_triangles = []
global_uvs = []
global_mat_ids = []
global_textures = []
cam_to_mat_idx = {}
global_mesh = o3d.geometry.TriangleMesh()

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
    fx, fy = cam.params[0] * scale, cam.params[0] * scale  # Fuerza fx=fy para evadir colapso de COLMAP
    cx, cy = cam.params[2] * scale, cam.params[3] * scale
    
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    
    pts3d, _, _ = extract_visible_points(img_obj)
    if len(pts3d) > 0:
        T_shifted = get_shifted_camera_matrix(img_obj)
        R = T_shifted[:3, :3]
        t = T_shifted[:3, 3].reshape(3, 1)
        pts_cam = (R @ pts3d.T) + t
        median_z = np.median(pts_cam[2, :])
        Z_dist = max(10.0, median_z * 1.5)
    else:
        Z_dist = 50.0
        
    X, Y = (u - cx) * Z_dist / fx, (v - cy) * Z_dist / fy
    Z = np.full_like(X, Z_dist)
    pts_cam_bg = np.stack((X.flatten(), Y.flatten(), Z.flatten()), axis=1)
    
    T_cam_to_shifted = np.linalg.inv(get_shifted_camera_matrix(img_obj))
    pts_world = (T_cam_to_shifted[:3, :3] @ pts_cam_bg.T).T + T_cam_to_shifted[:3, 3]
    
    pcd_bg.points = o3d.utility.Vector3dVector(pts_world)
    pcd_bg.colors = o3d.utility.Vector3dVector(cv_img.reshape(-1, 3) / 255.0)
    return True

def extract_visible_points(img_obj):
    idx = image_to_points[img_obj.image_id]
    return dense_points[idx], dense_colors[idx], idx

def refresh_view(vis):
    global is_pcd_bg_added, is_pcd_local_added, is_global_added
    
    if not cam_list: return False
    img_obj = cam_list[current_cam_idx]
    cam = rec.cameras[img_obj.camera_id]
    
    has_image = update_image_plane(img_obj, cam)
    if show_image and has_image and not is_pcd_bg_added:
        vis.add_geometry(pcd_bg, reset_bounding_box=False); is_pcd_bg_added = True
    elif (not show_image or not has_image) and is_pcd_bg_added:
        vis.remove_geometry(pcd_bg, reset_bounding_box=False); is_pcd_bg_added = False
    if is_pcd_bg_added: vis.update_geometry(pcd_bg)
        
    if show_pcd and not show_global:
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

    if show_global:
        if len(global_triangles) > 0:
            if not is_global_added:
                vis.add_geometry(global_mesh, reset_bounding_box=False)
                is_global_added = True
            else:
                vis.update_geometry(global_mesh)
        else:
            if is_global_added:
                vis.remove_geometry(global_mesh, reset_bounding_box=False)
                is_global_added = False
    else:
        if is_global_added:
            vis.remove_geometry(global_mesh, reset_bounding_box=False)
            is_global_added = False
    
    if camera_locked:
        ctr = vis.get_view_control()
        param = o3d.camera.PinholeCameraParameters()
        if hasattr(cam, 'calibration_matrix'):
            # Forzamos params[0] (fx) en vez de params[1] (fy) por si COLMAP lo colapso
            param.intrinsic = o3d.camera.PinholeCameraIntrinsic(cam.width, cam.height, cam.params[0], cam.params[0], cam.params[2], cam.params[3])
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
    return False

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
    extrinsic = np.copy(param.extrinsic)
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
    print("\033[96m[CENTRO]\033[0m Órbita anclada al punto central de tu pantalla (Raycast).")
    return False

def key_toggle_img(vis):
    global show_image; show_image = not show_image; refresh_view(vis)

def key_toggle_pcd(vis):
    global show_pcd; show_pcd = not show_pcd; refresh_view(vis)

def key_toggle_global(vis):
    global show_global
    show_global = not show_global
    print(f"\033[93m[GLOBAL]\033[0m Viendo Malla Global: {show_global}")
    refresh_view(vis)

def key_merge(vis):
    global show_global, global_mesh
    img_obj = cam_list[current_cam_idx]
    cam = rec.cameras[img_obj.camera_id]
    
    pts3d, cols, pt_indices = extract_visible_points(img_obj)
    if len(pts3d) < 3: return False
    
    T_shifted = get_shifted_camera_matrix(img_obj)
    R, t = T_shifted[:3, :3], T_shifted[:3, 3].reshape(3, 1)
    pts_cam = (R @ pts3d.T) + t
    z_vals = pts_cam[2, :] # Profundidad de los puntos respecto a la camara
    
    if hasattr(cam, 'calibration_matrix'): 
        K = cam.calibration_matrix()
        K[1,1] = K[0,0] # Forzar fx=fy para evadir deformacion extrema
    else: 
        K = np.eye(3); K[0,0] = cam.params[0]; K[1,1] = cam.params[0]; K[0,2] = cam.params[1]; K[1,2] = cam.params[2]
        
    pts_2d = (K @ pts_cam); pts_2d = (pts_2d[:2, :] / pts_2d[2, :]).T
    
    try: tri = Delaunay(pts_2d)
    except: return False
    
    # Texturas (Materiales)
    img_path = os.path.join(PATH_IMG, img_obj.name)
    img_rgb = cv2.cvtColor(cv2.imread(img_path), cv2.COLOR_BGR2RGB)
    H_img, W_img = img_rgb.shape[:2]
    
    if img_obj.image_id not in cam_to_mat_idx:
        mat_idx = len(global_textures)
        cam_to_mat_idx[img_obj.image_id] = mat_idx
        global_textures.append(o3d.geometry.Image(img_rgb))
    else:
        mat_idx = cam_to_mat_idx[img_obj.image_id]
        
    u = np.clip(pts_2d[:, 0] / W_img, 0.0, 1.0)
    v = np.clip(pts_2d[:, 1] / H_img, 0.0, 1.0)
    uvs = np.column_stack((u, v))
    
    # Filtros Dinamicos de Ruido (Aristas y Estiramiento Z)
    edges = np.vstack([tri.simplices[:, [0,1]], tri.simplices[:, [1,2]], tri.simplices[:, [2,0]]])
    dists = np.linalg.norm(pts3d[edges[:, 0]] - pts3d[edges[:, 1]], axis=1)
    MAX_EDGE = np.percentile(dists, 90) * 1.5 
    
    # Filtro Z-Stretch (Lo que pidió el usuario: no dibujar triangulos rotos estirados en Z)
    z_diffs = np.abs(z_vals[edges[:, 0]] - z_vals[edges[:, 1]])
    MAX_Z_STRETCH = np.percentile(z_diffs, 85) * 1.5 
    
    new_tris = 0
    for simplex in tri.simplices:
        i, j, k = simplex
        
        # Filtro de longitud 3D
        if np.linalg.norm(pts3d[i]-pts3d[j]) > MAX_EDGE or \
           np.linalg.norm(pts3d[j]-pts3d[k]) > MAX_EDGE or \
           np.linalg.norm(pts3d[k]-pts3d[i]) > MAX_EDGE:
            continue
            
        # Filtro de Z-Stretch (profundidad maxima respecto a la camara)
        z_face = z_vals[simplex]
        if np.max(z_face) - np.min(z_face) > MAX_Z_STRETCH:
            continue
            
        # Ordenamos los indices globales solo para verificar unicidad
        face_sorted = tuple(sorted((pt_indices[i], pt_indices[j], pt_indices[k])))
        
        if face_sorted not in global_faces_set:
            global_faces_set.add(face_sorted)
            
            # Guardamos el triangulo con su Winding original de Delaunay
            global_triangles.append([pt_indices[i], pt_indices[j], pt_indices[k]])
            
            # Asignar Textura y UVs
            global_uvs.append(uvs[i])
            global_uvs.append(uvs[j])
            global_uvs.append(uvs[k])
            global_mat_ids.append(mat_idx)
            
            new_tris += 1
            
    print(f"\033[93m[MERGE]\033[0m {new_tris} triángulos nuevos texturizados (Filtrado Z-Stretch activo). Total: {len(global_triangles)}")
    
    # Reconstruir geometria
    if len(global_triangles) > 0:
        global_mesh.vertices = o3d.utility.Vector3dVector(dense_points)
        global_mesh.triangles = o3d.utility.Vector3iVector(np.array(global_triangles, dtype=np.int32))
        global_mesh.triangle_uvs = o3d.utility.Vector2dVector(np.array(global_uvs))
        global_mesh.triangle_material_ids = o3d.utility.IntVector(np.array(global_mat_ids, dtype=np.int32))
        global_mesh.textures = global_textures
        global_mesh.vertex_colors = o3d.utility.Vector3dVector([]) 
        # NOTA: Evitamos remove_unreferenced_vertices para no romper la correspondencia exacta de UVs y Texturas.
    
    show_global = True
    # Forzar actualización en el visualizador
    if is_global_added:
        vis.remove_geometry(global_mesh, reset_bounding_box=False)
        vis.add_geometry(global_mesh, reset_bounding_box=False)
        
    refresh_view(vis)
    return False

print("\033[96m[INFO]\033[0m Abriendo Visor...")
print(" --- NAVEGACIÓN ---")
print("  - 'N' / 'B' : Cambiar Cámara")
print("  - 'F'       : Órbita Libre")
print("  - 'C'       : Centrar Órbita en el punto bajo la mira (Raycast)")
print("  - 'W' / 'S' : Caminar Hacia Adelante / Atrás (Supera el límite de zoom)")
print(" --- VISIBILIDAD ---")
print("  - 'H'       : Mostrar/Ocultar Nube Local")
print("  - 'I'       : Mostrar/Ocultar Foto Fondo")
print("  - 'G'       : Ver Malla Global Texturizada / Ver Nube Local")
print(" --- ALGORITMO ---")
print("  - 'M'       : Extraer Malla (Filtro Z-Stretch) + Texturizar + Unir a Global")

vis = o3d.visualization.VisualizerWithKeyCallback()
vis.create_window(window_name="Semantic Mesher (Multi-Vista Texturizado)", width=1280, height=720)
vis.get_render_option().background_color = np.asarray([0.1, 0.1, 0.1])
vis.get_render_option().mesh_show_back_face = True
vis.add_geometry(pcd_local)

vis.register_key_callback(ord('N'), key_next)
vis.register_key_callback(ord('B'), key_prev)
vis.register_key_callback(ord('F'), key_orbit)
vis.register_key_callback(ord('W'), key_w)
vis.register_key_callback(ord('S'), key_s)
vis.register_key_callback(ord('C'), key_center_ray)
vis.register_key_callback(ord('I'), key_toggle_img)
vis.register_key_callback(ord('H'), key_toggle_pcd)
vis.register_key_callback(ord('G'), key_toggle_global)
vis.register_key_callback(ord('M'), key_merge)

refresh_view(vis)
vis.run()
vis.destroy_window()
