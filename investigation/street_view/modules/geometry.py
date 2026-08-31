import numpy as np
import cv2

def make_intrinsic_matrix(fov_deg, W, H):
    """
    Crea la matriz intrínseca K para una cámara Pinhole.
    """
    f = (W / 2.0) / np.tan(np.radians(fov_deg) / 2.0)
    K = np.array([
        [f, 0, W / 2.0],
        [0, f, H / 2.0],
        [0, 0, 1.0]
    ])
    return K

def extract_pinhole_from_equi(equi_img, fov_deg, yaw_deg, pitch_deg, W, H):
    """
    Extrae una imagen perspectiva (pinhole) desde una imagen equirectangular.
    yaw_deg: Rotación horizontal (0 = frente, 90 = derecha, etc.)
    pitch_deg: Inclinación vertical (0 = horizonte, positivo = arriba)
    """
    K = make_intrinsic_matrix(fov_deg, W, H)
    K_inv = np.linalg.inv(K)

    # Coordenadas de los píxeles de la imagen pinhole
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    ones = np.ones_like(u)
    
    # Rayos en el espacio de la cámara
    rays_cam = K_inv @ np.stack((u, v, ones), axis=-1).reshape(-1, 3).T # 3 x N

    # Rotaciones
    # rx: rotación alrededor del eje X (Pitch)
    rx = np.radians(pitch_deg)
    Rx = np.array([
        [1, 0, 0],
        [0, np.cos(rx), -np.sin(rx)],
        [0, np.sin(rx), np.cos(rx)]
    ])
    
    # ry: rotación alrededor del eje Y (Yaw)
    ry = np.radians(yaw_deg)
    Ry = np.array([
        [np.cos(ry), 0, np.sin(ry)],
        [0, 1, 0],
        [-np.sin(ry), 0, np.cos(ry)]
    ])
    
    R = Ry @ Rx
    rays_world = R @ rays_cam # 3 x N

    # Convertir a coordenadas esféricas para mapear en la equirectangular
    norm = np.linalg.norm(rays_world, axis=0)
    lon = np.arctan2(rays_world[0], rays_world[2]) # Longitud
    lat = np.arcsin(np.clip(-rays_world[1] / norm, -1.0, 1.0)) # Latitud

    h_eq, w_eq = equi_img.shape[:2]
    
    # Mapeo a píxeles de la imagen original
    map_x = ((lon / (2 * np.pi) + 0.5) * w_eq).reshape(H, W).astype(np.float32)
    map_y = ((0.5 - lat / np.pi) * h_eq).reshape(H, W).astype(np.float32)

    pinhole_img = cv2.remap(equi_img, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    
    return pinhole_img, K, R

def unproject_rgbd_to_3d(rgb, depth, K, R_cam_to_world):
    """
    Convierte una imagen RGB y su Depth map a una nube de puntos 3D.
    R_cam_to_world: Matriz de rotación que ubica la cámara en el espacio global del panorama.
    """
    H, W = depth.shape
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    
    # Filtrar píxeles donde no hay profundidad
    mask = depth > 0
    u_mask = u[mask]
    v_mask = v[mask]
    z_mask = depth[mask]
    colors = rgb[mask] / 255.0

    # Desproyectar (Z * K_inv * [u, v, 1])
    cx = K[0, 2]
    cy = K[1, 2]
    fx = K[0, 0]
    fy = K[1, 1]
    
    x_cam = (u_mask - cx) * z_mask / fx
    y_cam = (v_mask - cy) * z_mask / fy
    pts_cam = np.stack((x_cam, y_cam, z_mask), axis=-1) # N x 3

    # Rotar puntos al sistema de coordenadas global del panorama
    pts_world = pts_cam @ R_cam_to_world.T
    
    return pts_world, colors
