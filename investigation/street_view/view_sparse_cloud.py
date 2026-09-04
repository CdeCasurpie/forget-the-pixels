import os
import sys
import numpy as np
import open3d as o3d
import pycolmap

def main():
    if len(sys.argv) > 1:
        sparse_path = sys.argv[1]
    else:
        sparse_path = "/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/sparse_custom"
    
    print(f"Cargando reconstrucción COLMAP desde: {sparse_path}")
    rec = pycolmap.Reconstruction(sparse_path)
    
    pts = []
    cols = []
    for pt3d_id, pt in rec.points3D.items():
        pts.append(pt.xyz)
        cols.append(pt.color / 255.0)
        
    pts = np.array(pts)
    cols = np.array(cols)
    
    print(f"Nube cargada con {len(pts)} puntos (Tie Points).")
    
    # Calcular la mediana de los puntos
    median_xyz = np.median(pts, axis=0)
    print(f"Mediana calculada (X, Y, Z): {median_xyz}")
    
    # Restar la mediana a todos los puntos para centrar la nube en el origen
    # Esto elimina el Z-fighting al renderizar coordenadas GPS enormes
    pts_centered = pts - median_xyz
    
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts_centered)
    pcd.colors = o3d.utility.Vector3dVector(cols)
    
    print("Abriendo visor Open3D...")
    print("Controles: Click Izq + Arrastrar (Rotar), Rueda (Zoom), Shift + Click Izq (Pan)")
    o3d.visualization.draw_geometries([pcd])

if __name__ == "__main__":
    main()
