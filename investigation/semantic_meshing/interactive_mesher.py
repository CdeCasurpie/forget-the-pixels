import os
import cv2
import struct
import numpy as np
import open3d as o3d
import pycolmap
import warnings
from skimage.segmentation import felzenszwalb
from scipy.spatial import Delaunay

warnings.filterwarnings("ignore")

print("\033[96m[INFO]\033[0m Iniciando Semantic Mesher (Modo Órbita e Inspector)...")

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

# ================= VARIABLES DE ESTADO =================
show_image = False
show_pcd = True
show_mesh = True
is_pcd_bg_added = False
is_pcd_local_added = True
is_mesh_added = False

camera_locked = True
inspect_mode = False
inspect_idx = 0

pcd_bg = o3d.geometry.PointCloud()
mesh_semantic = o3d.geometry.TriangleMesh()

cache_segments = {}
cache_meshes = {}
cache_inspector_mesh = None # Guarda temporalmente la malla de 1 solo segmento

pts_2d_cache = None
pts_3d_cache = None
cols_cache = None
seg_ids_cache = None
unique_segs_cache = None
# =======================================================

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
    
    if img_obj.image_id in cache_segments:
        seg_vis = cv2.applyColorMap((cache_segments[img_obj.image_id] * 5).astype(np.uint8), cv2.COLORMAP_JET)
        seg_vis = cv2.cvtColor(seg_vis, cv2.COLOR_BGR2RGB)
        
        if inspect_mode and unique_segs_cache is not None:
            active_seg_id = unique_segs_cache[inspect_idx]
            mask = (cache_segments[img_obj.image_id] == active_seg_id)
            highlight = np.zeros_like(cv_img)
            highlight[mask] = [0, 255, 0]
            seg_vis = cv2.addWeighted(seg_vis, 0.7, highlight, 0.3, 0)
            
        cv_img = cv2.addWeighted(cv_img, 0.5, seg_vis, 0.5, 0)
    
    scale = 0.25
    cv_img = cv2.resize(cv_img, (0,0), fx=scale, fy=scale)
    H, W, _ = cv_img.shape
    fx, fy = cam.params[0] * scale, cam.params[1] * scale
    cx, cy = cam.params[2] * scale, cam.params[3] * scale
    
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    Z_dist = 250.0 
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
    
    # === IMAGEN ===
    has_image = update_image_plane(img_obj, cam)
    if show_image and has_image and not is_pcd_bg_added:
        vis.add_geometry(pcd_bg, reset_bounding_box=False); is_pcd_bg_added = True
    elif (not show_image or not has_image) and is_pcd_bg_added:
        vis.remove_geometry(pcd_bg, reset_bounding_box=False); is_pcd_bg_added = False
    if is_pcd_bg_added: vis.update_geometry(pcd_bg)
        
    # === NUBES (INSPECTOR) ===
    if show_pcd:
        if inspect_mode and pts_3d_cache is not None and seg_ids_cache is not None:
            active_seg = unique_segs_cache[inspect_idx]
            mask = (seg_ids_cache == active_seg)
            pts, cols = pts_3d_cache[mask], cols_cache[mask]
        else:
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

    # === MALLAS ===
    if show_mesh:
        verts, tris, colors = None, None, None
        
        # Logica: Si estamos inspeccionando, mostramos la malla temporal (si existe). 
        # Si no, mostramos la malla completa de la cámara (si existe).
        if inspect_mode and cache_inspector_mesh is not None:
            verts, tris, colors = cache_inspector_mesh
        elif not inspect_mode and img_obj.image_id in cache_meshes:
            verts, tris, colors = cache_meshes[img_obj.image_id]
            
        if verts is not None and len(verts) > 0:
            mesh_semantic.vertices = o3d.utility.Vector3dVector(verts)
            mesh_semantic.triangles = o3d.utility.Vector3iVector(tris)
            mesh_semantic.vertex_colors = o3d.utility.Vector3dVector(colors)
            if not is_mesh_added:
                vis.add_geometry(mesh_semantic, reset_bounding_box=False); is_mesh_added = True
            else:
                vis.update_geometry(mesh_semantic)
        else:
            if is_mesh_added:
                vis.remove_geometry(mesh_semantic, reset_bounding_box=False); is_mesh_added = False
    else:
        if is_mesh_added:
            vis.remove_geometry(mesh_semantic, reset_bounding_box=False); is_mesh_added = False
    
    # === CONTROL DE CÁMARA ===
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
    global current_cam_idx, camera_locked, inspect_mode; 
    current_cam_idx = (current_cam_idx + 1) % len(cam_list); camera_locked = True; inspect_mode = False
    print(f"\033[92m[CAMERA]\033[0m Viendo: {cam_list[current_cam_idx].name}"); refresh_view(vis)

def key_prev(vis):
    global current_cam_idx, camera_locked, inspect_mode; 
    current_cam_idx = (current_cam_idx - 1) % len(cam_list); camera_locked = True; inspect_mode = False
    print(f"\033[92m[CAMERA]\033[0m Viendo: {cam_list[current_cam_idx].name}"); refresh_view(vis)

def key_orbit(vis):
    global camera_locked
    camera_locked = False
    vis.reset_view_point(True)
    print("\033[95m[ORBITA]\033[0m Modo Órbita Libre Activo. (Presiona N o B para regresar al Dron)")

def key_toggle_img(vis):
    global show_image; show_image = not show_image; refresh_view(vis)

def key_toggle_pcd(vis):
    global show_pcd; show_pcd = not show_pcd; refresh_view(vis)

def key_toggle_mesh(vis):
    global show_mesh; show_mesh = not show_mesh; refresh_view(vis)

def key_segment(vis):
    global pts_2d_cache, pts_3d_cache, cols_cache, seg_ids_cache, unique_segs_cache, show_image, inspect_mode, cache_inspector_mesh
    img_obj = cam_list[current_cam_idx]
    cam = rec.cameras[img_obj.camera_id]
    
    print(f"\033[94m[SEGMENTACIÓN]\033[0m Procesando {img_obj.name}...")
    pts3d, cols, _ = extract_visible_points(img_obj)
    
    T_shifted_to_cam = get_shifted_camera_matrix(img_obj)
    R = T_shifted_to_cam[:3, :3]
    t = T_shifted_to_cam[:3, 3].reshape(3, 1)
    pts_cam = (R @ pts3d.T) + t
    
    if hasattr(cam, 'calibration_matrix'): K = cam.calibration_matrix()
    else: K = np.eye(3); K[0,0] = cam.params[0]; K[1,1] = cam.params[0]; K[0,2] = cam.params[1]; K[1,2] = cam.params[2]
        
    pts_px = (K @ pts_cam)
    pts_px = pts_px[:2, :] / pts_px[2, :]
    pts_px = pts_px.T
    
    pts_2d_cache = pts_px
    pts_3d_cache = pts3d
    cols_cache = cols
    
    img_path = os.path.join(PATH_IMG, img_obj.name)
    img_rgb = cv2.imread(img_path)
    img_rgb = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2RGB)
    
    segments = felzenszwalb(img_rgb, scale=150, sigma=0.5, min_size=800)
    print(f"\033[94m[SEGMENTACIÓN]\033[0m {len(np.unique(segments))} segmentos detectados.")
    cache_segments[img_obj.image_id] = segments
    
    pts_2d_int = pts_2d_cache.astype(int)
    pts_2d_int[:, 0] = np.clip(pts_2d_int[:, 0], 0, segments.shape[1]-1)
    pts_2d_int[:, 1] = np.clip(pts_2d_int[:, 1], 0, segments.shape[0]-1)
    seg_ids_cache = segments[pts_2d_int[:, 1], pts_2d_int[:, 0]]
    unique_segs_cache = np.unique(seg_ids_cache)
    
    inspect_mode = False
    cache_inspector_mesh = None # Limpiamos la caché del inspector
    show_image = True
    refresh_view(vis)
    return False

def key_inspector_next(vis):
    global inspect_mode, inspect_idx, cache_inspector_mesh
    if unique_segs_cache is None: return
    inspect_mode = True
    cache_inspector_mesh = None # Se limpia al cambiar de segmento
    inspect_idx = (inspect_idx + 1) % len(unique_segs_cache)
    print(f"\033[96m[INSPECTOR]\033[0m Viendo Segmento {unique_segs_cache[inspect_idx]}")
    refresh_view(vis)

def key_inspector_prev(vis):
    global inspect_mode, inspect_idx, cache_inspector_mesh
    if unique_segs_cache is None: return
    inspect_mode = True
    cache_inspector_mesh = None # Se limpia al cambiar de segmento
    inspect_idx = (inspect_idx - 1) % len(unique_segs_cache)
    print(f"\033[96m[INSPECTOR]\033[0m Viendo Segmento {unique_segs_cache[inspect_idx]}")
    refresh_view(vis)

def key_inspector_off(vis):
    global inspect_mode, cache_inspector_mesh
    inspect_mode = False
    cache_inspector_mesh = None
    print("\033[96m[INSPECTOR]\033[0m Apagado. Viendo todos los segmentos.")
    refresh_view(vis)

def key_mesh(vis):
    global show_mesh, cache_inspector_mesh
    img_obj = cam_list[current_cam_idx]
    
    if img_obj.image_id not in cache_segments or unique_segs_cache is None:
        print("\033[91m[ERROR]\033[0m Primero segmenta la imagen con 'S'")
        return False
        
    print("\033[95m[MALLA]\033[0m Ejecutando Open3D 3D-RANSAC y Delaunay...")
    
    segs_to_process = [unique_segs_cache[inspect_idx]] if inspect_mode else unique_segs_cache
    
    all_verts, all_tris, all_cols = [], [], []
    offset = 0
    
    for seg_id in segs_to_process:
        idx = np.where(seg_ids_cache == seg_id)[0]
        if len(idx) < 15: continue
            
        pts3d = pts_3d_cache[idx]
        pts2d = pts_2d_cache[idx]
        cols = cols_cache[idx]
        
        temp_pcd = o3d.geometry.PointCloud()
        temp_pcd.points = o3d.utility.Vector3dVector(pts3d)
        
        try:
            plane_model, inliers = temp_pcd.segment_plane(distance_threshold=0.2, ransac_n=3, num_iterations=200)
        except: continue
            
        if len(inliers) < 10: continue
            
        inl_pts3d = pts3d[inliers]
        inl_pts2d = pts2d[inliers]
        inl_cols = cols[inliers]
        
        try: tri = Delaunay(inl_pts2d)
        except: continue
            
        all_verts.extend(inl_pts3d)
        all_cols.extend(inl_cols)
        all_tris.extend(tri.simplices + offset)
        offset += len(inl_pts3d)
        
    if len(all_verts) > 0:
        if inspect_mode:
            cache_inspector_mesh = (np.array(all_verts), np.array(all_tris), np.array(all_cols))
            print(f"\033[95m[MALLA]\033[0m Creada malla LOCAL con {len(all_verts)} vertices.")
        else:
            cache_meshes[img_obj.image_id] = (np.array(all_verts), np.array(all_tris), np.array(all_cols))
            print(f"\033[95m[MALLA]\033[0m Creada malla TOTAL con {len(all_verts)} vertices.")
    else:
        print("\033[91m[MALLA]\033[0m No se pudo generar la malla (muy pocos puntos inliers o falló RANSAC).")
    
    show_mesh = True 
    refresh_view(vis)
    return False

print("\033[96m[INFO]\033[0m Abriendo Visor...")
print(" --- NAVEGACIÓN ---")
print("  - 'N' / 'B' : Cambiar Cámara (Siguiente / Anterior - Vista Bloqueada al Dron)")
print("  - 'F'       : Órbita Libre (Desbloquea la cámara para girar con el ratón)")
print(" --- VISIBILIDAD ---")
print("  - 'H'       : Mostrar/Ocultar Nube")
print("  - 'I'       : Mostrar/Ocultar Foto (proyectada al fondo)")
print("  - 'J'       : Mostrar/Ocultar Malla Semántica")
print(" --- ALGORITMO ---")
print("  - 'S'       : 1. Segmentar Color")
print("  - 'O' / 'P' : 2. Inspector (Ver Segmento Siguiente / Anterior)")
print("  - 'U'       : 3. Apagar Inspector (Ver Todo)")
print("  - 'R'       : 4. Ransac + Malla (Aplica a TODO o SOLO al segmento inspeccionado)")

vis = o3d.visualization.VisualizerWithKeyCallback()
vis.create_window(window_name="Semantic Mesher (Pro)", width=1280, height=720)
vis.get_render_option().background_color = np.asarray([0.1, 0.1, 0.1])
vis.add_geometry(pcd_local)

vis.register_key_callback(ord('N'), key_next)
vis.register_key_callback(ord('B'), key_prev)
vis.register_key_callback(ord('F'), key_orbit)
vis.register_key_callback(ord('I'), key_toggle_img)
vis.register_key_callback(ord('H'), key_toggle_pcd)
vis.register_key_callback(ord('J'), key_toggle_mesh)
vis.register_key_callback(ord('S'), key_segment)
vis.register_key_callback(ord('O'), key_inspector_next)
vis.register_key_callback(ord('P'), key_inspector_prev)
vis.register_key_callback(ord('U'), key_inspector_off)
vis.register_key_callback(ord('R'), key_mesh)

refresh_view(vis)
vis.run()
vis.destroy_window()
