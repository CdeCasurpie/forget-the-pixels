import open3d as o3d
import numpy as np
import os

def main():
    ply_path = "/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/semantic_meshing_gsv/data/gsv_global.ply"
    if not os.path.exists(ply_path):
        print(f"Error: No se encontro el archivo {ply_path}.")
        print("Ejecuta 'python build_gsv_cloud.py' primero.")
        return

    print("Cargando Nube Global de Google Street View (Nativo 3D)...")
    pcd = o3d.io.read_point_cloud(ply_path)
    print(f"Nube cargada con {len(np.asarray(pcd.points))} puntos.")

    print("Abriendo visualizador...")
    print("Controles:")
    print(" - Click Izquierdo + Arrastrar: Rotar")
    print(" - Rueda del Mouse: Zoom")
    print(" - Shift + Arrastrar: Pan")
    
    vis = o3d.visualization.Visualizer()
    vis.create_window(window_name="Google Street View - Escáner 3D Nativo", width=1280, height=720)
    vis.add_geometry(pcd)
    
    opt = vis.get_render_option()
    opt.background_color = np.asarray([0.1, 0.1, 0.1])
    opt.point_size = 2.0
    
    vis.run()
    vis.destroy_window()

if __name__ == "__main__":
    main()
