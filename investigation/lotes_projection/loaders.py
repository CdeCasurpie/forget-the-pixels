import os
import json
import numpy as np
import geopandas as gpd
import pycolmap
import pyproj
from typing import List, Tuple
from models import Camera, CadastralLot

class CRSManager:
    """ Maneja las transformaciones entre ECEF, UTM y ENU local para evitar Jittering. """
    def __init__(self):
        # Transformadores
        self.transformer_ecef_to_utm = pyproj.Transformer.from_crs("EPSG:4978", "EPSG:32718", always_xy=True)
        self.transformer_utm_to_lla = pyproj.Transformer.from_crs("EPSG:32718", "EPSG:4326", always_xy=True)
        
        self.local_origin_utm = None
        self.z_ground_utm = 0.0
        self.R_ecef_to_enu = np.eye(3)

    def set_local_origin(self, origin_x: float, origin_y: float, z_ground: float):
        self.local_origin_utm = np.array([origin_x, origin_y, z_ground])
        self.z_ground_utm = z_ground
        
        # Calcular matriz de rotación ECEF a ENU en este punto
        lon, lat, _ = self.transformer_utm_to_lla.transform(origin_x, origin_y, z_ground)
        lat_rad, lon_rad = np.radians(lat), np.radians(lon)
        
        # Matriz estándar de rotación ECEF -> ENU
        self.R_ecef_to_enu = np.array([
            [-np.sin(lon_rad), np.cos(lon_rad), 0],
            [-np.sin(lat_rad)*np.cos(lon_rad), -np.sin(lat_rad)*np.sin(lon_rad), np.cos(lat_rad)],
            [np.cos(lat_rad)*np.cos(lon_rad), np.cos(lat_rad)*np.sin(lon_rad), np.sin(lat_rad)]
        ])

    def ecef_to_enu(self, pts_ecef: np.ndarray) -> np.ndarray:
        """ Convierte Nube ECEF a ENU (Rotación y Traslación) """
        # 1. Pasar a UTM
        x_u, y_u, z_u = self.transformer_ecef_to_utm.transform(pts_ecef[:, 0], pts_ecef[:, 1], pts_ecef[:, 2])
        pts_utm = np.column_stack((x_u, y_u, z_u))
        # 2. Restar el origen para tener ENU local
        return pts_utm - self.local_origin_utm
        
    def ecef_pose_to_enu(self, R_ecef: np.ndarray, t_ecef: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """ Convierte poses de COLMAP (World-to-Camera) de ECEF a ENU """
        # Centro óptico en ECEF
        C_ecef = -R_ecef.T @ t_ecef
        x_u, y_u, z_u = self.transformer_ecef_to_utm.transform(C_ecef[0], C_ecef[1], C_ecef[2])
        C_utm = np.array([x_u, y_u, z_u])
        C_enu = C_utm - self.local_origin_utm
        
        # Rotar la cámara del sistema ECEF al sistema ENU
        # R_ecef es (World_ecef -> Cam). Queremos (World_enu -> Cam).
        # X_enu = R_ecef_to_enu * X_ecef -> X_ecef = R_ecef_to_enu.T * X_enu
        # X_cam = R_ecef * X_ecef = R_ecef * R_ecef_to_enu.T * X_enu
        R_enu = R_ecef @ self.R_ecef_to_enu.T
        
        # Nueva traslación: t = -R * C
        t_enu = -R_enu @ C_enu
        return R_enu, t_enu

class DataLoader:
    def __init__(self, crs_manager: CRSManager, offset_json_path: str = None):
        self.crs = crs_manager
        self.offset = {'x': 0.0, 'y': 0.0, 'angle': 0.0}
        if offset_json_path and os.path.exists(offset_json_path):
            with open(offset_json_path, 'r') as f:
                self.offset.update(json.load(f))

    def load_colmap_model(self, model_path: str) -> Tuple[List[Camera], np.ndarray, np.ndarray]:
        rec = pycolmap.Reconstruction(model_path)
        
        pts_ecef = []
        colors = []
        for p3d in rec.points3D.values():
            pts_ecef.append(p3d.xyz)
            colors.append(p3d.color)
        pts_ecef = np.array(pts_ecef)
        colors = np.array(colors) / 255.0
        
        x_u, y_u, z_u = self.crs.transformer_ecef_to_utm.transform(pts_ecef[:, 0], pts_ecef[:, 1], pts_ecef[:, 2])
        pts_utm = np.column_stack((x_u, y_u, z_u))
        
        centro_x, centro_y = np.median(pts_utm[:, 0]), np.median(pts_utm[:, 1])
        z_ground = np.percentile(pts_utm[:, 2], 5)
        self.crs.set_local_origin(centro_x, centro_y, z_ground)
        
        pts_enu = self.crs.ecef_to_enu(pts_ecef)
        
        cameras_enu = []
        for image_id, image in rec.images.items():
            cam = rec.cameras[image.camera_id]
            if hasattr(cam, 'calibration_matrix'):
                K = cam.calibration_matrix()
            else:
                # Fallback to manual extraction if calibration_matrix is missing
                if cam.model_name in ["PINHOLE", "OPENCV"]:
                    fx, fy, cx, cy = cam.params[:4]
                    K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]])
                elif cam.model_name in ["SIMPLE_PINHOLE", "SIMPLE_RADIAL", "RADIAL"]:
                    f, cx, cy = cam.params[:3]
                    K = np.array([[f, 0, cx], [0, f, cy], [0, 0, 1]])
                else:
                    K = np.eye(3)
            if callable(image.cam_from_world):
                pose = image.cam_from_world()
            else:
                pose = image.cam_from_world
                
            R_ecef = pose.rotation.matrix()
            t_ecef = pose.translation
            R_enu, t_enu = self.crs.ecef_pose_to_enu(R_ecef, t_ecef)
            
            cameras_enu.append(Camera(
                camera_id=image_id,
                image_name=image.name,
                K=K,
                R=R_enu,
                t=t_enu,
                width=cam.width,
                height=cam.height
            ))
            
        return cameras_enu, pts_enu, colors

    def load_cadastre(self, shp_path: str, pts_enu: np.ndarray) -> List[CadastralLot]:
        gdf = gpd.read_file(shp_path).to_crs("EPSG:32718")
        ox, oy, ang = self.offset['x'], self.offset['y'], self.offset['angle']
        orig_utm = self.crs.local_origin_utm
        
        if ang != 0.0:
            gdf.geometry = gdf.geometry.rotate(ang, origin=(orig_utm[0], orig_utm[1]))
        if ox != 0.0 or oy != 0.0:
            gdf.geometry = gdf.geometry.translate(xoff=ox, yoff=oy)
            
        gdf.geometry = gdf.geometry.translate(xoff=-orig_utm[0], yoff=-orig_utm[1])
        
        lots = []
        for idx, row in gdf.iterrows():
            poly = row.geometry
            if poly is None: continue
            
            minx, miny, maxx, maxy = poly.bounds
            mask = (pts_enu[:, 0] >= minx) & (pts_enu[:, 0] <= maxx) & \
                   (pts_enu[:, 1] >= miny) & (pts_enu[:, 1] <= maxy)
            pts_in_box = pts_enu[mask]
            
            z_max = 3.0
            if len(pts_in_box) > 10:
                z_max = max(3.0, np.percentile(pts_in_box[:, 2], 90))
                
            lots.append(CadastralLot(str(idx), poly, 0.0, z_max))
            
        return lots
