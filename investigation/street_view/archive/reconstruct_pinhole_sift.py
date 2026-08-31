"""
Pipeline de Reconstrucción 3D desde Google Street View
======================================================
Paso 1: Cargar panoramas 360° con metadata (GPS, heading)
Paso 2: Extraer K imágenes pinhole horizontales de cada panorama (360° lateral, sin cielo/suelo)
Paso 3: Ejecutar Depth Anything V2 en cada imagen pinhole → mapa de profundidad relativo
Paso 4: Extraer SIFT de cada pinhole, match entre panoramas cercanos, triangular 2D→3D
Paso 5: Calibrar escala del depth map con los puntos triangulados
Paso 6: Generar nube densa muestreando cada depth map calibrado a resolución B×B
Paso 7: Exportar un ÚNICO PLY: nube densa + cámaras (puntos rojos) + trayectoria (líneas rojas)
"""

import os
import glob
import json
import numpy as np
import cv2
import open3d as o3d
from PIL import Image
import torch
from transformers import pipeline as hf_pipeline
import pyproj

# ============================================================
# CONFIGURACIÓN
# ============================================================
NUM_VIEWS = 8               # Vistas pinhole por panorama (cada 45°)
FOV_DEG = 90                # Field of view de cada vista
VIEW_W, VIEW_H = 640, 480   # Resolución de cada pinhole
B = 4                       # Densidad: 1 punto cada B píxeles
CAMERA_HEIGHT = 2.5          # Altura del carro de Google (metros)
MAX_DEPTH_M = 80             # Profundidad máxima a reconstruir (metros)
MIN_DEPTH_M = 1.0            # Profundidad mínima (metros)
MATCH_RADIUS_M = 30          # Radio para buscar pares de panoramas para SIFT

# ============================================================
# GEOMETRÍA: Extracción Pinhole desde Equirectangular
# ============================================================

def make_K(fov_deg, W, H):
    """Matriz intrínseca para cámara pinhole con FOV dado."""
    f = (W / 2.0) / np.tan(np.radians(fov_deg / 2.0))
    return np.array([[f, 0, W / 2.0],
                     [0, f, H / 2.0],
                     [0, 0, 1.0]])


def eq2persp(equi_img, fov_deg, yaw_deg, W, H):
    """
    Extrae una imagen perspectiva (pinhole) de una equirectangular.
    yaw_deg: rotación horizontal respecto al centro del panorama.
             0 = mirando al frente (heading), 90 = derecha, etc.
    Pitch fijo = 0 (horizontal, sin cielo ni suelo).
    """
    f = (W / 2.0) / np.tan(np.radians(fov_deg / 2.0))
    K_inv = np.linalg.inv(np.array([[f, 0, W/2.], [0, f, H/2.], [0, 0, 1.]]))

    u, v = np.meshgrid(np.arange(W), np.arange(H))
    ones = np.ones_like(u)
    rays = K_inv @ np.stack((u, v, ones), axis=-1).reshape(-1, 3).T  # 3×N

    # Rotar por yaw (alrededor del eje Y de la cámara, que es "abajo")
    ry = np.radians(yaw_deg)
    Ry = np.array([[np.cos(ry),  0, np.sin(ry)],
                   [0,           1, 0          ],
                   [-np.sin(ry), 0, np.cos(ry)]])
    rays = Ry @ rays

    # Esféricas: lon = atan2(x, z), lat = asin(-y / norm)
    norm = np.linalg.norm(rays, axis=0)
    lon = np.arctan2(rays[0], rays[2])
    lat = np.arcsin(np.clip(-rays[1] / norm, -1, 1))

    h_eq, w_eq = equi_img.shape[:2]
    map_x = ((lon / (2 * np.pi) + 0.5) * w_eq).reshape(H, W).astype(np.float32)
    map_y = ((0.5 - lat / np.pi) * h_eq).reshape(H, W).astype(np.float32)

    return cv2.remap(equi_img, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)


# ============================================================
# GEOMETRÍA: Matrices de Cámara
# ============================================================

def make_R_cw(heading_deg, yaw_offset_deg):
    """
    Rotación Cámara → Mundo (UTM).

    Convención cámara: x=derecha, y=abajo, z=adelante (OpenCV).
    Convención mundo:  X=Este,    Y=Norte, Z=Arriba  (UTM).

    heading_deg:    dirección del centro del panorama (grados horarios desde Norte).
    yaw_offset_deg: ángulo de la vista pinhole dentro del panorama.

    La dirección absoluta de esta cámara = heading + yaw_offset grados desde el Norte.
    """
    alpha = np.radians(heading_deg + yaw_offset_deg)
    c, s = np.cos(alpha), np.sin(alpha)
    # Columnas: [x_cam_en_mundo | y_cam_en_mundo | z_cam_en_mundo]
    #   z_cam (adelante) → (sin α, cos α, 0)  = dirección de la calle
    #   x_cam (derecha)  → (cos α, -sin α, 0) = perpendicular
    #   y_cam (abajo)    → (0, 0, -1)          = gravedad invertida
    return np.array([[ c, 0,  s],
                     [-s, 0,  c],
                     [ 0, -1, 0]], dtype=np.float64)


def make_P(K, R_cw, t_world):
    """Matriz de proyección 3×4: punto_mundo → pixel."""
    R_wc = R_cw.T
    t_cam = -R_wc @ t_world
    return K @ np.hstack((R_wc, t_cam.reshape(3, 1)))


# ============================================================
# PIPELINE PRINCIPAL
# ============================================================

def main():
    print("=" * 70)
    print("  PIPELINE DE RECONSTRUCCIÓN 3D — GOOGLE STREET VIEW + DEPTH ANYTHING")
    print("=" * 70)

    # --- Cargar metadata ---
    meta_path = "imagenes_gsv_ampliado/metadata.json"
    if not os.path.exists(meta_path):
        print(f"ERROR: No se encontró {meta_path}. Ejecuta primero download_gsv_large.py")
        return
    with open(meta_path) as f:
        metadata = json.load(f)

    images = sorted(glob.glob("imagenes_gsv_ampliado/*.jpg"))
    print(f"  Panoramas encontrados: {len(images)}")

    # --- Coordenadas UTM (metros reales, Zona 18S Lima) ---
    tx = pyproj.Transformer.from_crs("epsg:4326", "epsg:32718", always_xy=True)

    panos = []
    for fpath in images:
        key = os.path.basename(fpath).replace(".jpg", "")
        m = metadata[key]
        ux, uy = tx.transform(m["lon"], m["lat"])
        panos.append(dict(file=fpath, key=key,
                          utm=np.array([ux, uy, CAMERA_HEIGHT]),
                          heading=m["heading"]))

    # Centrar en el origen
    center = np.mean([p["utm"] for p in panos], axis=0)
    for p in panos:
        p["utm"] = p["utm"] - center

    # --- Modelo de Profundidad ---
    print("\n[PASO 0] Cargando Depth Anything V2 …")
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    depth_pipe = hf_pipeline(
        task="depth-estimation",
        model="depth-anything/Depth-Anything-V2-Small-hf",
        device=0 if dev == "cuda" else -1,
    )

    K_pin = make_K(FOV_DEG, VIEW_W, VIEW_H)
    yaw_offsets = [i * (360.0 / NUM_VIEWS) for i in range(NUM_VIEWS)]

    # ==================================================================
    # PASO 1-3: Extraer vistas pinhole + estimar profundidad relativa
    # ==================================================================
    print(f"\n[PASO 1-3] Extrayendo {NUM_VIEWS} vistas por panorama + Depth Anything …")

    views = []   # lista de dicts, un elemento por vista pinhole

    for pi, pano in enumerate(panos):
        equi = cv2.imread(pano["file"])
        equi_rgb = cv2.cvtColor(equi, cv2.COLOR_BGR2RGB)

        for vi, yaw_off in enumerate(yaw_offsets):
            pin_rgb = eq2persp(equi_rgb, FOV_DEG, yaw_off, VIEW_W, VIEW_H)
            pin_gray = cv2.cvtColor(pin_rgb, cv2.COLOR_RGB2GRAY)

            # Depth Anything → tensor relativo (alto = lejos)
            result = depth_pipe(Image.fromarray(pin_rgb))
            dpt = result["predicted_depth"]
            if isinstance(dpt, torch.Tensor):
                dpt = dpt.squeeze().cpu().numpy()
            dpt = dpt.astype(np.float64)
            if dpt.shape[:2] != (VIEW_H, VIEW_W):
                dpt = cv2.resize(dpt, (VIEW_W, VIEW_H), interpolation=cv2.INTER_LINEAR)

            R_cw = make_R_cw(pano["heading"], yaw_off)
            P    = make_P(K_pin, R_cw, pano["utm"])

            views.append(dict(
                pano_idx=pi, view_idx=vi,
                abs_yaw=(pano["heading"] + yaw_off) % 360,
                R_cw=R_cw, t_world=pano["utm"].copy(), P=P,
                rgb=pin_rgb, gray=pin_gray,
                depth_raw=dpt, scale=None,
            ))

        print(f"  Panorama {pi+1}/{len(panos)} procesado")

    # ==================================================================
    # PASO 4: SIFT matching entre panoramas conectados + triangulación
    # ==================================================================
    print(f"\n[PASO 4] Matching SIFT entre panoramas cercanos y triangulación …")

    sift = cv2.SIFT_create(nfeatures=3000)
    bf   = cv2.BFMatcher(cv2.NORM_L2)

    # Extraer descriptores SIFT
    for v in views:
        kp, des = sift.detectAndCompute(v["gray"], None)
        v["kp"]  = kp
        v["des"] = des

    # Acumular pares (true_depth, raw_depth) por vista para calibración
    calib = {i: [] for i in range(len(views))}
    total_triangulated = 0

    for pi in range(len(panos)):
        for pj in range(pi + 1, len(panos)):
            baseline = np.linalg.norm(panos[pi]["utm"] - panos[pj]["utm"])
            if baseline < 1.0 or baseline > MATCH_RADIUS_M:
                continue   # muy cerca (degenera) o muy lejos (sin overlap)

            # Para cada vista de pi, encontrar la vista de pj más alineada
            for vi in range(NUM_VIEWS):
                idx_i = pi * NUM_VIEWS + vi
                vw_i  = views[idx_i]
                if vw_i["des"] is None or len(vw_i["des"]) < 15:
                    continue

                # Vista de pj con dirección más cercana
                best_vj, best_diff = None, 999
                for vj in range(NUM_VIEWS):
                    idx_j = pj * NUM_VIEWS + vj
                    diff  = abs(((vw_i["abs_yaw"] - views[idx_j]["abs_yaw"]) + 180) % 360 - 180)
                    if diff < best_diff:
                        best_diff = diff
                        best_vj   = vj
                if best_diff > 50:
                    continue

                idx_j = pj * NUM_VIEWS + best_vj
                vw_j  = views[idx_j]
                if vw_j["des"] is None or len(vw_j["des"]) < 15:
                    continue

                # kNN matching + ratio test de Lowe
                matches = bf.knnMatch(vw_i["des"], vw_j["des"], k=2)
                good = [m for m, n in matches if len([m, n]) == 2 and m.distance < 0.75 * n.distance]
                if len(good) < 12:
                    continue

                pts_i = np.float64([vw_i["kp"][m.queryIdx].pt for m in good])
                pts_j = np.float64([vw_j["kp"][m.trainIdx].pt for m in good])

                # RANSAC con la fundamental (robusto a outliers)
                _, mask = cv2.findFundamentalMat(pts_i, pts_j, cv2.FM_RANSAC, 2.0, 0.999)
                if mask is None:
                    continue
                inliers = mask.ravel().astype(bool)
                pts_i = pts_i[inliers]
                pts_j = pts_j[inliers]
                if len(pts_i) < 8:
                    continue

                # Triangular con las matrices de proyección conocidas
                pts4D = cv2.triangulatePoints(vw_i["P"], vw_j["P"], pts_i.T, pts_j.T)
                pts3D = (pts4D[:3] / pts4D[3]).T   # N × 3

                R_wc_i = vw_i["R_cw"].T
                R_wc_j = vw_j["R_cw"].T

                for k in range(len(pts3D)):
                    pt = pts3D[k]

                    # Profundidad verdadera en cámara i
                    pc_i = R_wc_i @ (pt - vw_i["t_world"])
                    if MIN_DEPTH_M < pc_i[2] < MAX_DEPTH_M:
                        u, v = int(round(pts_i[k, 0])), int(round(pts_i[k, 1]))
                        if 0 <= u < VIEW_W and 0 <= v < VIEW_H:
                            calib[idx_i].append((vw_i["depth_raw"][v, u], pc_i[2]))

                    # Profundidad verdadera en cámara j
                    pc_j = R_wc_j @ (pt - vw_j["t_world"])
                    if MIN_DEPTH_M < pc_j[2] < MAX_DEPTH_M:
                        u, v = int(round(pts_j[k, 0])), int(round(pts_j[k, 1]))
                        if 0 <= u < VIEW_W and 0 <= v < VIEW_H:
                            calib[idx_j].append((vw_j["depth_raw"][v, u], pc_j[2]))

                total_triangulated += len(pts3D)

    print(f"  Puntos triangulados totales: {total_triangulated}")

    # ==================================================================
    # PASO 5: Calibrar escala de cada depth map
    # ==================================================================
    print(f"\n[PASO 5] Calibrando escala depth → metros …")

    all_scales = []
    for i, v in enumerate(views):
        pairs = calib[i]
        if len(pairs) < 3:
            continue
        d_raw  = np.array([p[0] for p in pairs])
        d_true = np.array([p[1] for p in pairs])
        good   = d_raw > 0.01
        if good.sum() < 3:
            continue
        ratios = d_true[good] / d_raw[good]
        v["scale"] = float(np.median(ratios))
        all_scales.append(v["scale"])

    if all_scales:
        fallback = float(np.median(all_scales))
        print(f"  Escala mediana global: {fallback:.4f}  (rango {min(all_scales):.4f} – {max(all_scales):.4f})")
    else:
        # Heurística: distancia típica entre panos / depth típico
        dists = [np.linalg.norm(panos[i]["utm"] - panos[i+1]["utm"])
                 for i in range(len(panos)-1)]
        fallback = float(np.median(dists)) / 3.0
        print(f"  SIFT no dio suficientes pares. Escala heurística: {fallback:.4f}")

    for v in views:
        if v["scale"] is None:
            v["scale"] = fallback

    # ==================================================================
    # PASO 6: Nube densa — muestrear cada depth map calibrado
    # ==================================================================
    print(f"\n[PASO 6] Generando nube densa (B={B}, {VIEW_W//B}×{VIEW_H//B} pts/vista) …")

    K_inv = np.linalg.inv(K_pin)
    all_pts = []
    all_col = []

    for v in views:
        Z_metric = v["scale"] * v["depth_raw"]

        uu, vv = np.meshgrid(np.arange(0, VIEW_W, B), np.arange(0, VIEW_H, B))
        uu_f = uu.ravel()
        vv_f = vv.ravel()
        Z = Z_metric[vv_f, uu_f]

        ok = (Z > MIN_DEPTH_M) & (Z < MAX_DEPTH_M)
        uu_ok, vv_ok, Z_ok = uu_f[ok], vv_f[ok], Z[ok]

        # Backproject: p_cam = Z * K⁻¹ [u, v, 1]ᵀ
        X_cam = (uu_ok - K_pin[0, 2]) * Z_ok / K_pin[0, 0]
        Y_cam = (vv_ok - K_pin[1, 2]) * Z_ok / K_pin[1, 1]
        pts_cam = np.stack((X_cam, Y_cam, Z_ok), axis=-1)   # N × 3

        # Cámara → Mundo
        pts_world = (v["R_cw"] @ pts_cam.T).T + v["t_world"]

        colors = v["rgb"][vv_ok, uu_ok] / 255.0

        all_pts.append(pts_world)
        all_col.append(colors)

    all_pts = np.vstack(all_pts)
    all_col = np.vstack(all_col)
    print(f"  Puntos de escena: {len(all_pts):,}")

    # ==================================================================
    # PASO 7: Agregar cámaras rojas + trayectoria roja → PLY ÚNICO
    # ==================================================================
    print(f"\n[PASO 7] Agregando cámaras y trayectoria al PLY …")

    cam_pts, cam_col = [], []
    for p in panos:
        # Esfera de 200 puntos rojos para que la cámara sea visible
        for _ in range(300):
            cam_pts.append(p["utm"] + np.random.randn(3) * 0.4)
            cam_col.append([1.0, 0.0, 0.0])
    cam_pts = np.array(cam_pts)
    cam_col = np.array(cam_col)

    # Líneas rojas: puntos densos entre cámaras consecutivas
    traj_pts, traj_col = [], []
    # Ordenar panos por cercanía geográfica para trazar la ruta real
    # Usar el orden original del BFS (que sigue las calles)
    for i in range(len(panos) - 1):
        a, b = panos[i]["utm"], panos[i + 1]["utm"]
        d = np.linalg.norm(b - a)
        n = max(int(d / 0.15), 5)   # Un punto cada 15 cm
        for t in np.linspace(0, 1, n):
            traj_pts.append(a + t * (b - a))
            traj_col.append([1.0, 0.0, 0.0])
    traj_pts = np.array(traj_pts) if traj_pts else np.empty((0, 3))
    traj_col = np.array(traj_col) if traj_col else np.empty((0, 3))

    # Combinar TODO en un solo PLY
    final_pts = np.vstack([all_pts, cam_pts, traj_pts])
    final_col = np.vstack([all_col, cam_col, traj_col])

    # Limpiar outliers extremos de la nube densa
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(final_pts)
    pcd.colors = o3d.utility.Vector3dVector(final_col)
    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.5)

    out = "reconstruccion_barranco.ply"
    o3d.io.write_point_cloud(out, pcd)

    n_scene = len(all_pts)
    n_cam   = len(cam_pts)
    n_traj  = len(traj_pts)
    print(f"\n{'=' * 70}")
    print(f"  ¡FINALIZADO!  →  {out}")
    print(f"  Puntos escena     : {n_scene:>10,}")
    print(f"  Puntos cámara     : {n_cam:>10,}")
    print(f"  Puntos trayectoria: {n_traj:>10,}")
    print(f"  TOTAL             : {n_scene + n_cam + n_traj:>10,}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
