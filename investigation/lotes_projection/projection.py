import numpy as np
from models import Camera, CadastralLot

class ZBufferProjector:
    """ Motor matemático para proyectar el mundo 3D (ENU) a las cámaras 2D. """
    
    @staticmethod
    def project_lot_to_camera(lot: CadastralLot, camera: Camera):
        """
        Proyecta los vértices 3D del lote a la cámara.
        Retorna (line_strips_2d, bbox_2d, is_visible)
        line_strips_2d = [ [[u1,v1], [u2,v2], ...], ... ]
        bbox_2d = [xmin, ymin, xmax, ymax]
        """
        # 1. Transformar de Mundo (ENU) a Cámara local
        X_world = lot.vertices_3d
        X_cam = (camera.R @ X_world.T).T + camera.t
        
        # 2. Distance Culling (Ignorar lotes a más de 120 metros del dron)
        distances = np.linalg.norm(X_cam, axis=1)
        if np.min(distances) > 120.0:
            return None, None, False

        # 3. Near-Plane Culling estricto
        # Si algún vértice del lote está detrás o cruzando la lente de la cámara (Z < 0.5m),
        # la división por Z causa que las líneas se proyecten hacia el infinito, ensuciando la pantalla.
        if np.any(X_cam[:, 2] < 0.5):
            return None, None, False
            
        # 4. Proyección Perspectiva
        Z = X_cam[:, 2]
        x_proj = X_cam[:, 0] / Z
        y_proj = X_cam[:, 1] / Z
        
        u = camera.K[0,0] * x_proj + camera.K[0,2]
        v = camera.K[1,1] * y_proj + camera.K[1,2]
        
        # 5. Frustum Culling 2D (Verificar si el lote cae dentro de la foto)
        xmin_proj, xmax_proj = np.min(u), np.max(u)
        ymin_proj, ymax_proj = np.min(v), np.max(v)
        
        # Recortar el Bounding Box a los límites exactos de la imagen de 1920x1080
        xmin = max(0, int(xmin_proj))
        ymin = max(0, int(ymin_proj))
        xmax = min(camera.width, int(xmax_proj))
        ymax = min(camera.height, int(ymax_proj))
        
        # Si el recuadro resultante no tiene área, el lote está 100% fuera de la vista
        if xmin >= xmax or ymin >= ymax:
            return None, None, False
            
        # Construir los LineStrips 2D (la misma topología que en 3D)
        num_coords = len(u) // 2
        bottom_ring = []
        top_ring = []
        
        for i in range(num_coords):
            bottom_ring.append([u[2*i], v[2*i]])
            top_ring.append([u[2*i+1], v[2*i+1]])
            
        strips_2d = [bottom_ring, top_ring]
        for i in range(num_coords - 1):
            strips_2d.append([bottom_ring[i], top_ring[i]])
            
        return strips_2d, [xmin, ymin, xmax, ymax], True
