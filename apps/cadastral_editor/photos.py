"""Camera catalog and height-independent cached projections shared with app B."""
from functools import lru_cache
import json
from pathlib import Path
import threading

import cv2
import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import Point
from packages.barranco_imaging.angular import view_spec, project_image, draw_prism


class Photos:
    def __init__(self, data, repository, fast=False):
        self.data = Path(data)
        self.fast = fast
        metadata = self.data / 'poses_barranco/metadata.json'
        raw = json.loads(metadata.read_text())['panoramas'] if metadata.exists() else {}
        self.meta = {pid: m for pid, m in raw.items() if
            all(m.get(k) is not None for k in ('lon', 'lat', 'heading_deg', 'pitch_deg', 'roll_deg'))
            and (self.data/'fotos_barranco'/f'{pid}.jpg').exists()}
        self.ids = list(self.meta)
        transformer = Transformer.from_crs(4326, 32718, always_xy=True)
        self.xy = np.array([transformer.transform(self.meta[p]['lon'], self.meta[p]['lat']) for p in self.ids]).reshape(-1, 2)
        self.tree = cKDTree(self.xy)
        self.positions = dict(zip(self.ids, self.xy))
        # Same photo/frame requests share a lock; unrelated photos may run in parallel.
        self.locks = [threading.Lock() for _ in range(32)]
        self.workers = threading.Semaphore(2)

    def candidates(self, polygon, radius=90, limit=None, offset=0):
        center = np.array(polygon.centroid.coords[0])
        reach = max(np.linalg.norm(np.array(polygon.exterior.coords)-center, axis=1))
        results = []
        for i in self.tree.query_ball_point(center, reach+radius):
            distance = polygon.distance(Point(self.xy[i]))
            if 1 < distance <= radius:
                p = self.ids[i]
                results.append((distance, p))
        results.sort()
        selected = results[offset:] if limit is None else results[offset:offset+limit]
        return [{**self.describe(p, polygon), 'distance_m': round(distance, 1)} for distance,p in selected]

    @lru_cache(maxsize=2)
    def _source(self, pid):
        # Reduced JPEG decoding is sufficient for a 960px preview and avoids decoding
        # full panoramas on each lot. A keeps its existing full-resolution behavior.
        return cv2.imread(str(self.data/'fotos_barranco'/f'{pid}.jpg'),
                          cv2.IMREAD_REDUCED_COLOR_2 if self.fast else cv2.IMREAD_COLOR)

    def describe(self, pid, polygon):
        if pid not in self.meta:
            raise ValueError('Panorama desconocido o sin pose')
        m = self.meta[pid]
        return dict(id=pid, date=m.get('date'), camera_xy=self.positions[pid].tolist(),
            camera_lonlat=[m['lon'], m['lat']], pose={k: m[k] for k in ('heading_deg', 'pitch_deg', 'roll_deg')},
            image_path=f'fotos_barranco/{pid}.jpg', projection=view_spec(polygon, self.positions[pid]))

    @lru_cache(maxsize=64)
    def _base(self, pid, geometry_json):
        from shapely.geometry import shape
        if pid not in self.meta:
            raise ValueError('Panorama desconocido o sin pose')
        polygon = shape(json.loads(geometry_json))
        with self.workers:
            image = self._source(pid) if self.fast else cv2.imread(str(self.data/'fotos_barranco'/f'{pid}.jpg'))
            if image is None:
                raise ValueError('No se pudo leer el panorama')
            image = project_image(image, self.meta[pid], view_spec(polygon, self.positions[pid]))
            ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            raise ValueError('No se pudo proyectar la imagen')
        return encoded.tobytes()

    def base(self, pid, geometry_json):
        with self.locks[hash((pid, geometry_json)) % len(self.locks)]:
            return self._base(pid, geometry_json)

    def render(self, pid, geometry_json, height):
        from shapely.geometry import shape
        image = cv2.imdecode(np.frombuffer(self.base(pid, geometry_json), dtype=np.uint8), cv2.IMREAD_COLOR)
        image = draw_prism(image, view_spec(shape(json.loads(geometry_json)), self.positions[pid]), height)
        ok, encoded = cv2.imencode('.jpg', image)
        if not ok:
            raise ValueError('No se pudo dibujar el prisma')
        return encoded.tobytes()
