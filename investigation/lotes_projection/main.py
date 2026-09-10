import os
import argparse
import sys

# Parche para que Rerun encuentre su ejecutable dentro del venv aunque no esté activo globalmente
os.environ["PATH"] = os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", "")

from loaders import CRSManager, DataLoader
from projection import ZBufferProjector
from visualizer import PipelineLogger

def main():
    print("\033[96m[INFO]\033[0m Iniciando Geo-Proyector (Fase 1: Auditoría Local)")
    
    DIR_BASE = os.path.dirname(os.path.abspath(__file__))
    
    # Rutas apuntando al experimento original de Lotes (Dron)
    PATH_NUBE_COLMAP = os.path.join(DIR_BASE, "../Lotes/nube_sparse/0_aligned")
    PATH_SHP = os.path.join(DIR_BASE, "../Lotes/shp_files/BARRANCO_LM_geogpsperu_SuyoPomalia.shp")
    PATH_IMAGES = os.path.join(DIR_BASE, "../Lotes/images")
    PATH_OFFSET = os.path.join(DIR_BASE, "../Lotes/offset_config.json")
    
    if not os.path.exists(PATH_NUBE_COLMAP):
        print(f"\033[91m[ERROR]\033[0m No se encontró el modelo COLMAP en: {PATH_NUBE_COLMAP}")
        return
        
    # Inicializamos Módulos
    crs = CRSManager()
    loader = DataLoader(crs_manager=crs, offset_json_path=PATH_OFFSET)
    
    # 1. Cargar Datos
    print("-> Cargando modelo 3D y Cámaras (Esto puede tardar un par de segundos)...")
    cameras, pts_enu, colors = loader.load_colmap_model(PATH_NUBE_COLMAP)
    print(f"-> Cámaras cargadas: {len(cameras)}")
    
    print("-> Cargando Catastro y Calculando Extrusiones...")
    lots = loader.load_cadastre(PATH_SHP, pts_enu)
    print(f"-> Lotes catastrales cargados y extruidos: {len(lots)}")
    
    # 2. Iniciar Visualizador
    logger = PipelineLogger()
    
    # Log estático (Nube y Lotes)
    logger.log_geometry(pts_enu, colors, lots)
    
    # 3. Simular la Línea de Tiempo (Pipeline Orquestador Temporal)
    print("-> Calculando proyecciones 3D->2D y enviando a Rerun.io...")
    for step_idx, cam in enumerate(cameras):
        img_path = os.path.join(PATH_IMAGES, cam.image_name)
        
        # Opcional: Solo procesar cámaras que apunten al frente (view0, view1)
        # para hacer el debug visual más rápido si hay muchas fotos (ej. > 100)
        # if not ('view0' in cam.image_name or 'view1' in cam.image_name):
        #    continue
            
        visible_lots = []
        for lot in lots:
            strips_2d, bbox, is_visible = ZBufferProjector.project_lot_to_camera(lot, cam)
            if is_visible:
                visible_lots.append((strips_2d, bbox, lot.lot_id))
                
        # Enviar el frame al visualizador
        logger.log_camera_step(step_idx, cam, img_path, visible_lots)
        print(f"  Frame {step_idx} ({cam.image_name}): {len(visible_lots)} lotes visibles proyectados.")
        
    print("\n\033[92m[ÉXITO]\033[0m ¡Proyecciones terminadas!")
    print("Revisa la ventana de Rerun. Usa el deslizador inferior (Time Panel) para navegar entre fotos.")
    
    # Mantener el script vivo si Rerun está abierto
    input("\nPresiona ENTER para cerrar Rerun y finalizar...")

if __name__ == "__main__":
    main()
