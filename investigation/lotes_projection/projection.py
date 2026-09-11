import numpy as np
from models import Camera, CadastralLot
from shapely.geometry import Polygon as ShapelyPolygon

class ZBufferProjector:
    """ Motor matemático para proyectar el mundo 3D (ENU) a las cámaras 2D. """
    
    @staticmethod
    def project_lot_to_camera(lot: CadastralLot, camera: Camera):
        """
        Proyecta los vértices 3D del lote a la cámara.
        Retorna (faces, bbox_2d, is_visible)
        faces = [ {"depth": float, "pts": [...], "type": str, "normal_world": array, "centroid_world": array} ]
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
        coords_3d = lot.vertices_3d
        
        bottom_ring = []
        top_ring = []
        for i in range(num_coords):
            bottom_ring.append([u[2*i], v[2*i]])
            top_ring.append([u[2*i+1], v[2*i+1]])
            
        faces = []
        
        # Paredes (Quads)
        for i in range(num_coords - 1):
            ib, it = 2*i, 2*i+1
            jb, jt = 2*(i+1), 2*(i+1)+1
            
            p1 = [u[ib], v[ib]]
            p2 = [u[it], v[it]]
            p3 = [u[jt], v[jt]]
            p4 = [u[jb], v[jb]]
            
            avg_z = (Z[ib] + Z[it] + Z[jt] + Z[jb]) / 4.0
            
            # Normal de la pared en coordenadas mundo (ENU)
            edge_h = coords_3d[jb] - coords_3d[ib]
            edge_v = coords_3d[it] - coords_3d[ib]
            normal = np.cross(edge_h, edge_v)
            norm_len = np.linalg.norm(normal)
            if norm_len > 1e-9:
                normal = normal / norm_len
            
            centroid = (coords_3d[ib] + coords_3d[it] + coords_3d[jt] + coords_3d[jb]) / 4.0
            
            faces.append({
                "depth": avg_z,
                "pts": [p1, p2, p3, p4],
                "type": "wall",
                "normal_world": normal,
                "centroid_world": centroid,
            })
            
        # Techo (Top ring)
        avg_z_top = np.mean([Z[2*i+1] for i in range(num_coords)])
        faces.append({
            "depth": avg_z_top,
            "pts": top_ring,
            "type": "roof",
            "normal_world": np.array([0, 0, 1.0]),
            "centroid_world": np.mean(coords_3d[1::2], axis=0),
        })
        
        # Piso (Bottom ring)
        avg_z_bottom = np.mean([Z[2*i] for i in range(num_coords)])
        faces.append({
            "depth": avg_z_bottom,
            "pts": bottom_ring,
            "type": "floor",
            "normal_world": np.array([0, 0, -1.0]),
            "centroid_world": np.mean(coords_3d[0::2], axis=0),
        })
            
        return faces, [xmin, ymin, xmax, ymax], True

    @staticmethod
    def compute_lot_score(faces, camera, other_faces=None):
        """
        Score = Σ |dot_xy(normal, cam_forward)| para paredes visibles.
        Para paredes: solo componente XY (ignora Z, el dron siempre está arriba).
        Para techo: dot 3D completo.
        Piso: ignorado.
        Sin factor de distancia.
        
        Oclusión: si >50% de la cara 2D está tapada por caras más cercanas de otros lotes, score=0.
        """
        cam_forward = camera.R[2, :]
        
        # Occluders 2D
        occluder_polys = []
        if other_faces:
            for of in other_faces:
                try:
                    p = ShapelyPolygon(of["pts"])
                    if p.is_valid and p.area > 10:
                        occluder_polys.append((p, of["depth"], p.bounds))
                except:
                    pass
        
        score_total = 0.0
        face_scores = []
        
        for face in faces:
            if face["type"] == "floor":
                face_scores.append(0.0)
                continue
            
            normal = face["normal_world"]
            
            if face["type"] == "wall":
                # Proyectar al plano XY (ignorar Z)
                n_xy = normal[:2]
                c_xy = cam_forward[:2]
                n_len = np.linalg.norm(n_xy)
                c_len = np.linalg.norm(c_xy)
                if n_len > 1e-9 and c_len > 1e-9:
                    dot = abs(np.dot(n_xy / n_len, c_xy / c_len))
                else:
                    dot = 0.0
            else:
                # Techo: dot 3D completo
                dot = abs(np.dot(normal, cam_forward))
            
            score_face = dot
            
            # Oclusión 2D
            if occluder_polys and score_face > 0.001:
                try:
                    fp = ShapelyPolygon(face["pts"])
                    if fp.is_valid and fp.area > 10:
                        area_orig = fp.area
                        minx, miny, maxx, maxy = fp.bounds
                        visible = fp
                        for op, od, ob in occluder_polys:
                            if od < face["depth"]:
                                if not (ob[2] < minx or ob[0] > maxx or ob[3] < miny or ob[1] > maxy):
                                    visible = visible.difference(op)
                                    if visible.area < area_orig * 0.5:
                                        break
                        ratio = visible.area / area_orig if area_orig > 0 else 0
                        if ratio < 0.5:
                            score_face = 0.0
                        else:
                            score_face *= ratio
                except:
                    pass
            
            face_scores.append(score_face)
            score_total += score_face
        
        return score_total, face_scores
