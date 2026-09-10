import os
import json
import sys

# Forzar al sistema a encontrar el ejecutable de Rerun dentro del venv310
venv_bin = os.path.dirname(sys.executable)
if venv_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{venv_bin}:{os.environ.get('PATH', '')}"

import rerun as rr
from loaders import CRSManager, DataLoader
from visualizer import PipelineLogger

def main():
    print("\033[96m[INFO]\033[0m Preparando Preview 3D de los Lotes Aprobados...")
    DIR_BASE = os.path.dirname(os.path.abspath(__file__))
    JSON_PATH = os.path.join(DIR_BASE, "crops_metadata.json")
    PATH_NUBE = os.path.join(DIR_BASE, "../Lotes/nube_sparse/0_aligned")
    PATH_SHP = os.path.join(DIR_BASE, "../Lotes/shp_files/BARRANCO_LM_geogpsperu_SuyoPomalia.shp")
    PATH_OFFSET = os.path.join(DIR_BASE, "../Lotes/offset_config.json")
    
    if not os.path.exists(JSON_PATH):
        print("\033[91m[ERROR]\033[0m Falta crops_metadata.json. Ejecuta 'make export-crops' primero.")
        return
        
    # 1. Extraer IDs de lotes válidos
    with open(JSON_PATH, 'r') as f:
        metadata = json.load(f)
        
    valid_lot_ids = set()
    for crops in metadata.values():
        for crop in crops:
            valid_lot_ids.add(str(crop["lot_id"]))
            
    print(f"-> Se encontraron {len(valid_lot_ids)} lotes aprobados listos para visualizar.")
    
    # 2. Cargar Geometría
    crs = CRSManager()
    loader = DataLoader(crs_manager=crs, offset_json_path=PATH_OFFSET)
    
    print("-> Cargando Nube de Puntos (ECEF -> ENU)...")
    _, pts_enu, colors = loader.load_colmap_model(PATH_NUBE)
    
    print("-> Extruyendo el Catastro...")
    all_lots = loader.load_cadastre(PATH_SHP, pts_enu)
    
    # 3. Filtrar
    approved_lots = [lot for lot in all_lots if str(lot.lot_id) in valid_lot_ids]
    
    # 4. Mostrar en Rerun
    print("-> Lanzando Visor Rerun...")
    logger = PipelineLogger("Preview Lotes Aprobados")
    rr.set_time("frame", sequence=0)
    logger.log_geometry(pts_enu, colors, approved_lots)
    
    print("\033[92m[ÉXITO]\033[0m Revisa la ventana de Rerun.")

if __name__ == "__main__":
    main()
