import os
import json
from loaders import CRSManager, DataLoader
from projection import ZBufferProjector

def get_coverage(box_a, box_b):
    """Calcula qué porcentaje del área del box_a está cubierto por el box_b"""
    xA = max(box_a[0], box_b[0])
    yA = max(box_a[1], box_b[1])
    xB = min(box_a[2], box_b[2])
    yB = min(box_a[3], box_b[3])
    
    interArea = max(0, xB - xA) * max(0, yB - yA)
    if interArea == 0:
        return 0.0
        
    boxAArea = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    return interArea / float(boxAArea)

def main():
    print("\033[96m[INFO]\033[0m Generando metadata de Bounding Boxes (JSON) para SAM...")
    DIR_BASE = os.path.dirname(os.path.abspath(__file__))
    
    PATH_NUBE_COLMAP = os.path.join(DIR_BASE, "../Lotes/nube_sparse/0_aligned")
    PATH_SHP = os.path.join(DIR_BASE, "../Lotes/shp_files/BARRANCO_LM_geogpsperu_SuyoPomalia.shp")
    PATH_OFFSET = os.path.join(DIR_BASE, "../Lotes/offset_config.json")
    OUT_JSON = os.path.join(DIR_BASE, "crops_metadata.json")
    
    crs = CRSManager()
    loader = DataLoader(crs_manager=crs, offset_json_path=PATH_OFFSET)
    
    print("-> Cargando modelo 3D y extruyendo Lotes...")
    cameras, pts_enu, _ = loader.load_colmap_model(PATH_NUBE_COLMAP)
    lots = loader.load_cadastre(PATH_SHP, pts_enu)
    
    best_camera_for_lot = {} # lot_id -> {cam_name, score, bbox}
    
    print("-> Analizando oclusiones y buscando la cámara perfecta para cada lote...")
    import numpy as np
    
    for cam in cameras:
        visible_lots_in_cam = []
        
        for lot in lots:
            _, bbox, is_visible = ZBufferProjector.project_lot_to_camera(lot, cam)
            if not is_visible:
                continue
                
            # Calcular distancia real al centro del lote
            X_world = lot.vertices_3d
            X_cam = (cam.R @ X_world.T).T + cam.t
            distance = np.mean(np.linalg.norm(X_cam, axis=1))
            
            # Filtro 1: Descartar lotes a más de 80m (Muy lejos = poca resolución)
            if distance > 80.0:
                continue
                
            # Filtro 2: Descartar lotes que tocan los bordes de la imagen (están cortados/incompletos)
            # Si un lote toca el borde, significa que la cámara solo captó una rebanada de él.
            MARGIN = 15 # píxeles de margen de seguridad
            if bbox[0] <= MARGIN or bbox[1] <= MARGIN or bbox[2] >= cam.width - MARGIN or bbox[3] >= cam.height - MARGIN:
                continue
                
            # Filtro 3: Descartar bounding boxes muy chicos (menor a ~15,000 px de área)
            area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            if area < 15000:
                continue
                
            visible_lots_in_cam.append({
                "lot": lot,
                "bbox": bbox,
                "distance": distance,
                "area": area
            })
            
        # Ordenar lotes del más cercano al más lejano (Z-buffer lógico)
        visible_lots_in_cam.sort(key=lambda x: x["distance"])
        
        accepted_in_cam = []
        for item in visible_lots_in_cam:
            # Filtro 3: Oclusión (Revisar si un lote MÁS CERCANO tapa a este lote)
            is_occluded = False
            for closer_item in accepted_in_cam:
                coverage = get_coverage(item["bbox"], closer_item["bbox"])
                if coverage > 0.35: # Si >35% del área está cubierta por un edificio delante, lo descartamos
                    is_occluded = True
                    break
                    
            if is_occluded:
                continue
                
            accepted_in_cam.append(item)
            
            # Evaluar si esta cámara es LA MEJOR cámara histórica para este lote
            # Score = Distancia + Penalización por estar en el borde de la imagen
            img_cx, img_cy = cam.width / 2.0, cam.height / 2.0
            box_cx = (item["bbox"][0] + item["bbox"][2]) / 2.0
            box_cy = (item["bbox"][1] + item["bbox"][3]) / 2.0
            offset = np.sqrt((img_cx - box_cx)**2 + (img_cy - box_cy)**2)
            
            score = item["distance"] + (offset * 0.02)
            
            lot_id = item["lot"].lot_id
            if lot_id not in best_camera_for_lot or score < best_camera_for_lot[lot_id]["score"]:
                best_camera_for_lot[lot_id] = {
                    "cam_name": cam.image_name,
                    "score": score,
                    "bbox": item["bbox"]
                }
                
    # Reagrupar en el formato final para SAM: img_name -> list of crops
    metadata = {}
    for lot_id, data in best_camera_for_lot.items():
        img_name = data["cam_name"]
        if img_name not in metadata:
            metadata[img_name] = []
        metadata[img_name].append({
            "lot_id": lot_id,
            "bbox": data["bbox"]
        })
            
    with open(OUT_JSON, 'w') as f:
        json.dump(metadata, f, indent=4)
        
    print(f"\033[92m[ÉXITO]\033[0m Se extrajeron {len(best_camera_for_lot)} lotes únicos perfectos distribuidos en {len(metadata)} imágenes.")
    print(f"-> Archivo listo para Khipu: {OUT_JSON}")

if __name__ == "__main__":
    main()
