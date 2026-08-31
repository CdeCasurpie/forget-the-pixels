import os
import glob
import json
import numpy as np
import cv2
import open3d as o3d
import torch
import pyproj
from PIL import Image
from transformers import pipeline

from modules.geometry import extract_pinhole_from_equi, unproject_rgbd_to_3d

# ============================================================
# CONFIGURACIÓN
# ============================================================
NUM_VIEWS = 4               # 0 (Frente), 90 (Derecha), 180 (Atrás), 270 (Izquierda)
FOV_DEG = 90
VIEW_W, VIEW_H = 640, 640
B = 4                       # Densidad de submuestreo (1 punto cada B pixeles)
CAMERA_HEIGHT = 2.5
MAX_DEPTH_M = 40.0          # Recortar puntos muy lejanos
MIN_DEPTH_M = 1.0
SKY_THRESHOLD = 20.0        # Descartar disparidad (0-255) < 20 (Cielo)
MATCH_RADIUS_M = 25.0       # Radio para buscar panoramas vecinos con SIFT

def make_intrinsic(fov_deg, W, H):
    f = (W / 2.0) / np.tan(np.radians(fov_deg) / 2.0)
    return np.array([[f, 0, W/2.0], [0, f, H/2.0], [0, 0, 1.0]])

def make_R_cw(heading_deg, yaw_offset_deg):
    alpha = np.radians(heading_deg + yaw_offset_deg)
    c, s = np.cos(alpha), np.sin(alpha)
    return np.array([[ c, 0,  s],
                     [-s, 0,  c],
                     [ 0, -1, 0]], dtype=np.float64)

def make_P(K, R_cw, t_world):
    R_wc = R_cw.T
    t_cam = -R_wc @ t_world
    return K @ np.hstack((R_wc, t_cam.reshape(3, 1)))

def main():
    print("======================================================================")
    print("  RECONSTRUCCIÓN GLOBAL 360 SEAMLESS + ESCALA SIFT POR PANORAMA")
    print("======================================================================")

    # 1. Cargar metadatos
    meta_path = "data/imagenes_gsv_ampliado/metadata.json"
    with open(meta_path) as f:
        metadata = json.load(f)

    images = sorted(glob.glob("data/imagenes_gsv_ampliado/*.jpg"))
    print(f"-> Panoramas encontrados: {len(images)}")

    tx = pyproj.Transformer.from_crs("epsg:4326", "epsg:32718", always_xy=True)
    panos = []
    for fpath in images:
        key = os.path.basename(fpath).replace(".jpg", "")
        m = metadata[key]
        ux, uy = tx.transform(m["lon"], m["lat"])
        panos.append({"file": fpath, "key": key, "utm": np.array([ux, uy, CAMERA_HEIGHT]), "heading": m["heading"]})

    # Centrar coordenadas en el origen
    center = np.mean([p["utm"] for p in panos], axis=0)
    for p in panos:
        p["utm"] = p["utm"] - center

    # 2. Inicializar Modelos
    dev = 0 if torch.cuda.is_available() else -1
    depth_pipe = pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device=dev)
    
    sift = cv2.SIFT_create(nfeatures=2000)
    bf = cv2.BFMatcher(cv2.NORM_L2)

    K_pin = make_intrinsic(FOV_DEG, VIEW_W, VIEW_H)
    yaws = [i * (360 // NUM_VIEWS) for i in range(NUM_VIEWS)]

    views = [] # Todas las vistas de todas las cámaras
    
    # ==================================================================
    # PASO A: Depth 360 Seamless + Extracción Pinhole + SIFT Keypoints
    # ==================================================================
    print("\n[PASO A] Estimación Depth 360 y Extracción Pinhole ...")
    for pi, pano in enumerate(panos):
        equi_rgb = cv2.cvtColor(cv2.imread(pano["file"]), cv2.COLOR_BGR2RGB)
        
        # Depth global para no tener cortes
        equi_depth = np.array(depth_pipe(Image.fromarray(equi_rgb))["depth"], dtype=np.float32)

        for vi, yaw in enumerate(yaws):
            pin_rgb, _, R_pano = extract_pinhole_from_equi(equi_rgb, FOV_DEG, yaw, 0, VIEW_W, VIEW_H)
            pin_dep, _, _      = extract_pinhole_from_equi(equi_depth, FOV_DEG, yaw, 0, VIEW_W, VIEW_H)
            
            # Keypoints SIFT en grises
            gray = cv2.cvtColor(pin_rgb, cv2.COLOR_RGB2GRAY)
            kp, des = sift.detectAndCompute(gray, None)

            # Matrices globales UTM
            R_cw = make_R_cw(pano["heading"], yaw)
            P = make_P(K_pin, R_cw, pano["utm"])

            views.append({
                "pano_idx": pi, "view_idx": vi, "abs_yaw": (pano["heading"] + yaw) % 360,
                "R_cw": R_cw, "t_world": pano["utm"].copy(), "P": P,
                "rgb": pin_rgb, "depth_0_255": pin_dep, "kp": kp, "des": des,
                "Z_relative": 1000.0 / (pin_dep + 1.0)
            })
        print(f"  Panorama {pi+1}/{len(panos)} procesado.")

    # ==================================================================
    # PASO B: Triangulación SIFT para Calibrar Escala de CADA PANORAMA
    # ==================================================================
    print("\n[PASO B] Triangulación SIFT entre panoramas vecinos ...")
    
    calib = {i: [] for i in range(len(panos))} # Guardaremos (True_Z, Rel_Z) para cada panorama

    for pi in range(len(panos)):
        for pj in range(pi + 1, len(panos)):
            baseline = np.linalg.norm(panos[pi]["utm"] - panos[pj]["utm"])
            if baseline < 2.0 or baseline > MATCH_RADIUS_M:
                continue

            for vi in range(NUM_VIEWS):
                idx_i = pi * NUM_VIEWS + vi
                vw_i = views[idx_i]
                if vw_i["des"] is None or len(vw_i["des"]) < 10: continue

                # Buscar la vista vj de pj que mire en dirección opuesta/cercana
                best_vj, best_diff = None, 999
                for vj in range(NUM_VIEWS):
                    idx_j = pj * NUM_VIEWS + vj
                    diff = abs(((vw_i["abs_yaw"] - views[idx_j]["abs_yaw"]) + 180) % 360 - 180)
                    if diff < best_diff:
                        best_diff = diff
                        best_vj = vj
                if best_diff > 60: continue

                idx_j = pj * NUM_VIEWS + best_vj
                vw_j = views[idx_j]
                if vw_j["des"] is None or len(vw_j["des"]) < 10: continue

                # Match
                matches = bf.knnMatch(vw_i["des"], vw_j["des"], k=2)
                good = [m for m, n in matches if m.distance < 0.75 * n.distance]
                if len(good) < 15: continue

                pts_i = np.float64([vw_i["kp"][m.queryIdx].pt for m in good])
                pts_j = np.float64([vw_j["kp"][m.trainIdx].pt for m in good])

                _, mask = cv2.findFundamentalMat(pts_i, pts_j, cv2.FM_RANSAC, 1.0, 0.99)
                if mask is None: continue
                inliers = mask.ravel().astype(bool)
                pts_i, pts_j = pts_i[inliers], pts_j[inliers]
                if len(pts_i) < 10: continue

                # Triangulación 3D
                pts4D = cv2.triangulatePoints(vw_i["P"], vw_j["P"], pts_i.T, pts_j.T)
                pts3D = (pts4D[:3] / pts4D[3]).T

                R_wc_i = vw_i["R_cw"].T
                R_wc_j = vw_j["R_cw"].T

                for k in range(len(pts3D)):
                    pt = pts3D[k]
                    # Check para Pano i
                    pc_i = R_wc_i @ (pt - vw_i["t_world"])
                    if 1.0 < pc_i[2] < 50.0:
                        u, v = int(round(pts_i[k, 0])), int(round(pts_i[k, 1]))
                        if 0 <= u < VIEW_W and 0 <= v < VIEW_H:
                            calib[pi].append((pc_i[2], vw_i["Z_relative"][v, u]))
                            
                    # Check para Pano j
                    pc_j = R_wc_j @ (pt - vw_j["t_world"])
                    if 1.0 < pc_j[2] < 50.0:
                        u, v = int(round(pts_j[k, 0])), int(round(pts_j[k, 1]))
                        if 0 <= u < VIEW_W and 0 <= v < VIEW_H:
                            calib[pj].append((pc_j[2], vw_j["Z_relative"][v, u]))

    # Calcular escalas robustas por panorama
    pano_scales = np.ones(len(panos))
    valid_scales = []
    
    for pi in range(len(panos)):
        pairs = calib[pi]
        if len(pairs) > 5:
            d_true = np.array([p[0] for p in pairs])
            d_rel  = np.array([p[1] for p in pairs])
            ratios = d_true / d_rel
            pano_scales[pi] = np.median(ratios)
            valid_scales.append(pano_scales[pi])
            print(f"  Escala Pano {pi}: {pano_scales[pi]:.4f} (basado en {len(pairs)} pts)")
        else:
            print(f"  Escala Pano {pi}: Insuficientes puntos SIFT.")
            
    # Asignar escala mediana a los que fallaron
    global_median = np.median(valid_scales) if valid_scales else 1.0
    for pi in range(len(panos)):
        if len(calib[pi]) <= 5:
            pano_scales[pi] = global_median
            print(f"  -> Fix Pano {pi} usando mediana global: {global_median:.4f}")

    # ==================================================================
    # PASO C: Desproyección a Nube Densa Global
    # ==================================================================
    print("\n[PASO C] Generando nube densa global combinada ...")
    
    all_pts_3d = []
    all_col_3d = []
    K_inv = np.linalg.inv(K_pin)

    for vw in views:
        pi = vw["pano_idx"]
        scale = pano_scales[pi]
        
        # Aplicar escala verdadera y filtro de cielo
        Z_metric = vw["Z_relative"] * scale
        mask_sky = vw["depth_0_255"] < SKY_THRESHOLD
        Z_metric[mask_sky] = 0
        
        uu, vv = np.meshgrid(np.arange(0, VIEW_W, B), np.arange(0, VIEW_H, B))
        uu_f, vv_f = uu.ravel(), vv.ravel()
        Z = Z_metric[vv_f, uu_f]
        
        ok = (Z > MIN_DEPTH_M) & (Z < MAX_DEPTH_M)
        uu_ok, vv_ok, Z_ok = uu_f[ok], vv_f[ok], Z[ok]
        
        X_cam = (uu_ok - K_pin[0, 2]) * Z_ok / K_pin[0, 0]
        Y_cam = (vv_ok - K_pin[1, 2]) * Z_ok / K_pin[1, 1]
        pts_cam = np.stack((X_cam, Y_cam, Z_ok), axis=-1)
        
        pts_world = (vw["R_cw"] @ pts_cam.T).T + vw["t_world"]
        colors = vw["rgb"][vv_ok, uu_ok] / 255.0
        
        all_pts_3d.append(pts_world)
        all_col_3d.append(colors)

    # Combinar TODO
    final_pts = np.vstack(all_pts_3d)
    final_col = np.vstack(all_col_3d)
    
    # Agregar cámaras y lineas
    cam_pts, cam_col, traj_pts, traj_col = [], [], [], []
    for p in panos:
        for _ in range(150):
            cam_pts.append(p["utm"] + np.random.randn(3) * 0.3)
            cam_col.append([1.0, 0.0, 0.0])
            
    for i in range(len(panos) - 1):
        a, b = panos[i]["utm"], panos[i+1]["utm"]
        for t in np.linspace(0, 1, int(np.linalg.norm(b-a)*10)):
            traj_pts.append(a + t*(b-a))
            traj_col.append([1.0, 0.0, 0.0])

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(np.vstack([final_pts, cam_pts, traj_pts]))
    pcd.colors = o3d.utility.Vector3dVector(np.vstack([final_col, cam_col, traj_col]))
    
    out = "outputs/pointclouds/reconstruccion_full_graph.ply"
    o3d.io.write_point_cloud(out, pcd)
    print(f"\n¡EXITO! Archivo final guardado en {out} con {len(pcd.points):,} puntos.")

if __name__ == "__main__":
    main()
