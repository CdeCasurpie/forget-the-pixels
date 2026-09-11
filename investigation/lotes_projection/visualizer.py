import rerun as rr
import numpy as np
import cv2
import os
from models import Camera, CadastralLot

class PipelineLogger:
    """ Singleton wrapper para enviar telemetría a Rerun.io """
    
    def __init__(self, application_name="Geo-Proyector Lotes"):
        # Inicializa Rerun y abre el visualizador localmente
        rr.init(application_name, spawn=True)
        # Configurar el sistema de coordenadas 3D de Rerun (Z Up, Right-Handed)
        rr.log("world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)

    def log_geometry(self, pts_enu: np.ndarray, colors: np.ndarray, lots: list[CadastralLot]):
        """ Loguea la nube de puntos y las cajas 3D de los lotes como datos estáticos """
        print("[Rerun] Logueando Nube de Puntos (3D)...")
        rr.log("world/point_cloud", rr.Points3D(positions=pts_enu, colors=colors), static=True)
        
        print("[Rerun] Logueando Lotes Catastrales (polígonos 3D exactos)...")
        strips = []
        labels = []
        
        for lot in lots:
            if lot.polygon_2d.geom_type == 'Polygon':
                polys = [lot.polygon_2d]
            elif lot.polygon_2d.geom_type == 'MultiPolygon':
                polys = list(lot.polygon_2d.geoms)
            else:
                continue
                
            for p in polys:
                coords = list(p.exterior.coords)
                # Anillo inferior
                bottom = [[c[0], c[1], lot.z_min] for c in coords]
                # Anillo superior
                top = [[c[0], c[1], lot.z_max] for c in coords]
                
                strips.append(bottom)
                strips.append(top)
                
                # Postes verticales
                for i in range(len(coords) - 1):
                    strips.append([bottom[i], top[i]])
                    
        if strips:
            rr.log("world/lots", 
                   rr.LineStrips3D(strips, colors=[0, 255, 0, 150]), 
                   static=True)

    def log_camera_step(self, step_idx: int, cam: Camera, image_path: str, projected_lots: list):
        """ Loguea una cámara en un instante de tiempo específico (slider) """
        rr.set_time("frame", sequence=step_idx)
        
        # Le decimos a Rerun que la cámara de COLMAP mira hacia adelante (Right-Down-Forward)
        rr.log("world/camera", rr.ViewCoordinates.RDF, static=True)
        
        # 1. Loguear la posición de la cámara en el mundo 3D
        rr.log("world/camera", 
               rr.Transform3D(translation=cam.optical_center, mat3x3=cam.R.T))
               
        # 2. Loguear los parámetros del Pinhole (intrínsecas K)
        rr.log("world/camera/image", 
               rr.Pinhole(resolution=[cam.width, cam.height], image_from_camera=cam.K))
               
        # 3. Loguear la Imagen Real
        if os.path.exists(image_path):
            img = cv2.imread(image_path)
            if img is not None:
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                rr.log("world/camera/image", rr.Image(img_rgb))
        
        # 4. Loguear los Bounding Boxes y Siluetas proyectadas en 2D
        if projected_lots:
            box_mins = []
            box_sizes = []
            labels = []
            all_faces = []
            
            for faces_2d, bbox, lot_id in projected_lots:
                all_faces.extend(faces_2d)
                xmin, ymin, xmax, ymax = bbox
                box_mins.append([xmin, ymin])
                box_sizes.append([xmax - xmin, ymax - ymin])
                labels.append(f"Lote {lot_id}")
                
            # Painter's Algorithm: Ordenar de más lejos a más cerca
            all_faces.sort(key=lambda f: f['depth'], reverse=True)
            
            # Crear Overlay RGBA (Solid rendering con bordes rojos y fondo negro semi-transparente)
            overlay = np.zeros((cam.height, cam.width, 4), dtype=np.uint8)
            for face in all_faces:
                pts = np.array(face['pts'], np.int32).reshape((-1, 1, 2))
                # Relleno negro/gris oscuro semi-transparente para ocluir lo de atrás
                cv2.fillPoly(overlay, [pts], (20, 20, 20, 230))
                # Borde Rojo vivo
                cv2.polylines(overlay, [pts], isClosed=True, color=(255, 0, 0, 255), thickness=3)
                
            # Dibujar en Rerun
            rr.log("world/camera/image/solid_overlay", rr.Image(overlay))
            rr.log("world/camera/image/sam_boxes", rr.Boxes2D(mins=box_mins, sizes=box_sizes, labels=labels, colors=[255, 255, 0, 50]))
        else:
            rr.log("world/camera/image/solid_overlay", rr.Clear.flat())
            rr.log("world/camera/image/sam_boxes", rr.Clear.flat())
