import numpy as np
from models import Camera, CadastralLot

class ZBufferProjector:
    """ Motor matemático para proyectar el mundo 3D (ENU) a las cámaras 2D. """
    
    @staticmethod
    def project_lot_to_camera(lot: CadastralLot, camera: Camera):
        """
        Proyecta los vértices 3D del lote a la cámara.
        Retorna (faces_2d, bbox_2d, is_visible)
        faces_2d = [ {"depth": float, "pts": [[u,v], ...]} ]
        """
        # 1. Transformar de Mundo (ENU) a Cámara local
        X_world = lot.vertices_3d
        X_cam = (camera.R @ X_world.T).T + camera.t
        
        distances = np.linalg.norm(X_cam, axis=1)
        if np.min(distances) > 120.0:
            return None, None, False

        # Near-Plane Culling
        if np.any(X_cam[:, 2] < 0.5):
            return None, None, False
            
        Z = X_cam[:, 2]
        x_proj = X_cam[:, 0] / Z
        y_proj = X_cam[:, 1] / Z
        
        u = camera.K[0,0] * x_proj + camera.K[0,2]
        v = camera.K[1,1] * y_proj + camera.K[1,2]
        
        xmin_proj, xmax_proj = np.min(u), np.max(u)
        ymin_proj, ymax_proj = np.min(v), np.max(v)
        
        xmin = max(0, int(xmin_proj))
        ymin = max(0, int(ymin_proj))
        xmax = min(camera.width, int(xmax_proj))
        ymax = min(camera.height, int(ymax_proj))
        
        if xmin >= xmax or ymin >= ymax:
            return None, None, False
            
        num_coords = len(u) // 2
        
        bottom_ring = []
        top_ring = []
        for i in range(num_coords):
            bottom_ring.append([u[2*i], v[2*i]])
            top_ring.append([u[2*i+1], v[2*i+1]])
            
        faces_2d = []
        
        # Paredes (Quads)
        for i in range(num_coords - 1):
            p1 = [u[2*i], v[2*i]]
            p2 = [u[2*i+1], v[2*i+1]]
            p3 = [u[2*(i+1)+1], v[2*(i+1)+1]]
            p4 = [u[2*(i+1)], v[2*(i+1)]]
            
            # Profundidad promedio de la pared
            avg_z = (Z[2*i] + Z[2*i+1] + Z[2*(i+1)+1] + Z[2*(i+1)]) / 4.0
            
            faces_2d.append({
                "depth": avg_z,
                "pts": [p1, p2, p3, p4]
            })
            
        # Techo (Top ring)
        avg_z_top = np.mean([Z[2*i+1] for i in range(num_coords)])
        faces_2d.append({
            "depth": avg_z_top,
            "pts": top_ring
        })
        
        # Piso (Bottom ring)
        avg_z_bottom = np.mean([Z[2*i] for i in range(num_coords)])
        faces_2d.append({
            "depth": avg_z_bottom,
            "pts": bottom_ring
        })
            
        return faces_2d, [xmin, ymin, xmax, ymax], True
