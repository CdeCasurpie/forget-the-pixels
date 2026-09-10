import numpy as np
from shapely.geometry import Polygon
import pyproj

class Camera:
    """ Representa una cámara fotográfica (COLMAP o nativa) en el espacio local ENU. """
    def __init__(self, camera_id: int, image_name: str, K: np.ndarray, R: np.ndarray, t: np.ndarray, width: int, height: int, is_360: bool = False):
        self.camera_id = camera_id
        self.image_name = image_name
        self.K = K          # Intrínsecas (3x3)
        self.R = R          # Rotación (3x3) de World a Camera
        self.t = t          # Traslación (3,) de World a Camera
        self.width = width
        self.height = height
        self.is_360 = is_360
        
        # Calcular el centro óptico en coordenadas del mundo (ENU)
        # C = -R^T * t
        self.optical_center = -self.R.T @ self.t

class CadastralLot:
    """ Representa un lote catastral extruido en 3D en el espacio local ENU. """
    def __init__(self, lot_id: str, polygon_2d: Polygon, z_min: float, z_max: float):
        self.lot_id = lot_id
        self.polygon_2d = polygon_2d
        self.z_min = z_min
        self.z_max = z_max
        self.vertices_3d = self._generate_3d_bounding_box()

    def _generate_3d_bounding_box(self) -> np.ndarray:
        """ 
        Genera los vértices 3D (piso y techo) del polígono. 
        Para una caja simple, tomamos el bounding box 2D del polígono, 
        pero para mayor precisión, tomamos la envolvente convexa o el polígono exacto.
        Usaremos el Minimum Rotated Rectangle (Bounding Box orientado) para mantener pocos vértices.
        """
        # Obtenemos los vértices reales del polígono para una proyección 100% exacta
        if self.polygon_2d.geom_type == 'Polygon':
            coords = list(self.polygon_2d.exterior.coords)
        elif self.polygon_2d.geom_type == 'MultiPolygon':
            coords = []
            for geom in self.polygon_2d.geoms:
                coords.extend(list(geom.exterior.coords))
        else:
            minx, miny, maxx, maxy = self.polygon_2d.bounds
            coords = [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy), (minx, miny)]
            
        # Extruir a 3D (Cota inferior y superior)
        vertices = []
        for x, y in coords:
            vertices.append([x, y, self.z_min])
            vertices.append([x, y, self.z_max])
            
        return np.array(vertices, dtype=np.float32)
