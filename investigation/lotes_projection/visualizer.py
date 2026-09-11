import rerun as rr
import numpy as np
import cv2
import os
from models import Camera, CadastralLot
from projection import ZBufferProjector

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

    @staticmethod
    def _score_to_color(score):
        """Mapea score [0, 1] a color RGB: rojo(0) -> amarillo(0.5) -> verde(1.0)"""
        t = min(max(score, 0.0), 1.0)
        if t < 0.5:
            r = 255
            g = int(255 * (t / 0.5))
            b = 0
        else:
            r = int(255 * (1.0 - (t - 0.5) / 0.5))
            g = 255
            b = 0
        return (r, g, b)

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
        
        # 4. Render sólido + Score Heatmap
        if projected_lots:
            box_mins = []
            box_sizes = []
            labels = []
            
            all_lot_data = []
            all_faces_flat = []
            
            for faces, bbox, lot_id in projected_lots:
                all_lot_data.append((faces, bbox, lot_id))
                all_faces_flat.extend(faces)
            
            # Calcular scores por lote
            lot_scores = {}
            lot_face_scores = {}
            
            for faces, bbox, lot_id in all_lot_data:
                other = [f for f in all_faces_flat if f not in faces]
                score_total, face_scores = ZBufferProjector.compute_lot_score(faces, cam, other)
                lot_scores[lot_id] = score_total
                lot_face_scores[lot_id] = face_scores
                
                xmin, ymin, xmax, ymax = bbox
                box_mins.append([xmin, ymin])
                box_sizes.append([xmax - xmin, ymax - ymin])
                labels.append(f"Lote {lot_id} | {score_total:.2f}")
            
            # Filtrar SAM boxes: solo lotes con score >= umbral
            SCORE_THRESHOLD = 0.5
            good_mins, good_sizes, good_labels = [], [], []
            for i, (faces, bbox, lot_id) in enumerate(all_lot_data):
                if lot_scores[lot_id] >= SCORE_THRESHOLD:
                    good_mins.append(box_mins[i])
                    good_sizes.append(box_sizes[i])
                    good_labels.append(labels[i])
            
            # --- PANEL 1: Render sólido (Painter's Algorithm) ---
            all_render = []
            for faces, bbox, lot_id in all_lot_data:
                for face in faces:
                    all_render.append(face)
            all_render.sort(key=lambda f: f['depth'], reverse=True)
            
            overlay_solid = np.zeros((cam.height, cam.width, 4), dtype=np.uint8)
            for face in all_render:
                pts = np.array(face['pts'], np.int32).reshape((-1, 1, 2))
                cv2.fillPoly(overlay_solid, [pts], (20, 20, 20, 230))
                cv2.polylines(overlay_solid, [pts], isClosed=True, color=(255, 0, 0, 255), thickness=3)
            rr.log("world/camera/image/solid_overlay", rr.Image(overlay_solid))
            
            # --- PANEL 2: Score Heatmap (coloreado por cara, RGBA semi-transparente) ---
            score_render = []
            for faces, bbox, lot_id in all_lot_data:
                fscores = lot_face_scores[lot_id]
                for fi, face in enumerate(faces):
                    score_render.append((face, fscores[fi], lot_id))
            score_render.sort(key=lambda x: x[0]['depth'], reverse=True)
            
            overlay_score = np.zeros((cam.height, cam.width, 4), dtype=np.uint8)
            for face, fscore, lot_id in score_render:
                pts = np.array(face['pts'], np.int32).reshape((-1, 1, 2))
                if fscore < 1e-6:
                    color = (40, 40, 40)
                else:
                    color = self._score_to_color(fscore)
                cv2.fillPoly(overlay_score, [pts], (*color, 128))
                cv2.polylines(overlay_score, [pts], isClosed=True, color=(255, 255, 255, 200), thickness=1)
                # Número de score en cada cara
                fp = np.array(face['pts'])
                cx, cy = int(np.mean(fp[:, 0])), int(np.mean(fp[:, 1]))
                if 0 < cx < cam.width and 0 < cy < cam.height:
                    cv2.putText(overlay_score, f"{fscore:.2f}", (cx-15, cy),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,255,255,255), 1)
            rr.log("world/camera/image/score_heatmap", rr.Image(overlay_score))
            
            # SAM boxes (solo lotes con buen score)
            if good_mins:
                rr.log("world/camera/image/sam_boxes", rr.Boxes2D(
                    mins=good_mins, sizes=good_sizes, labels=good_labels, colors=[255, 255, 0, 50]))
            else:
                rr.log("world/camera/image/sam_boxes", rr.Clear.flat())
        else:
            rr.log("world/camera/image/solid_overlay", rr.Clear.flat())
            rr.log("world/camera/image/score_heatmap", rr.Clear.flat())
            rr.log("world/camera/image/sam_boxes", rr.Clear.flat())
