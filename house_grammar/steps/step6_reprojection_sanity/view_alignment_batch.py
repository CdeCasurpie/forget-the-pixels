"""Compare the five closest cadastral lots visible from the Step 5 cameras."""
import argparse
import json
from pathlib import Path
import sys

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np
from PIL import Image
from pyproj import Geod, Transformer
from shapely.geometry import Point
from shapely.affinity import translate

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from vision.cameras import score_edges
from vision.projection.spherical import PanoramaCamera, prism_edges, strip_pixels

CRS = 'EPSG:32718'
COLORS = ['#ff00ff', '#00aa55', '#ff8c00', '#1683ff', '#9b35c9']


def choose_lots(gdf, cameras, top_k, max_distance):
    """Choose unique lots by minimum camera distance, requiring one visible edge."""
    spatial_index = gdf.sindex
    candidates = []
    for index, row in gdf.iterrows():
        polygon = row.geometry
        if polygon.geom_type != 'Polygon' or not polygon.is_valid:
            continue
        best = None
        for camera in cameras:
            point = Point(camera['camera_x'], camera['camera_y'])
            if polygon.covers(point):
                continue
            distance = point.distance(polygon)
            if distance > max_distance:
                continue
            if best is not None and distance > best[0][0]:
                continue
            edges = score_edges(gdf, index, polygon, point, spatial_index)
            visible = [edge for edge in edges if edge['visible']]
            if visible:
                candidate = (distance, -len(visible), str(camera['pano_id']))
                if best is None or candidate < best[0]:
                    best = (candidate, camera, visible)
        if best:
            candidates.append({'index': int(index), 'objectid': int(row.objectid),
                               'geometry': polygon, 'distance_m': best[0][0],
                               'reference_camera': best[1]['pano_id'],
                               'visible_edges': len(best[2])})
    candidates.sort(key=lambda item: (item['distance_m'], -item['visible_edges']))
    return candidates[:top_k]


class BatchViewer:
    def __init__(self, args):
        self.args = args
        self.data = json.loads(args.manifest.read_text())
        if self.data.get('projection') != 'full_vertical_angular_cylindrical_strip':
            raise ValueError('Expected Step 5 manifest')
        lots = gpd.read_file(args.shapefile).to_crs(CRS)
        transformer = Transformer.from_crs('EPSG:4326', CRS, always_xy=True)
        camera_records = []
        for entry in self.data['cameras']:
            x, y = transformer.transform(float(entry['lon']), float(entry['lat']))
            camera_records.append({**entry, 'camera_x': x, 'camera_y': y})
        self.lots = choose_lots(lots, camera_records, args.top_k, args.max_distance)
        if not self.lots:
            raise RuntimeError('No hay lotes válidos con una arista visible')
        self.cameras = camera_records
        self.dx, self.dy = 0., 0.
        self.height, self.step = args.height, args.step
        self.saved = f'{len(self.lots)} lotes seleccionados'
        if args.correction.is_file():
            correction = json.loads(args.correction.read_text())
            if correction['crs'] != CRS:
                raise ValueError('Correction has another CRS')
            if 'target_objectids' in correction and correction['target_objectids'] != [lot['objectid'] for lot in self.lots]:
                raise ValueError('Correction belongs to another lot set')
            self.dx, self.dy = correction['east_m'], correction['north_m']
            self.height = correction.get('height_m', self.height)
            self.args.camera_height = correction.get('camera_height_m', self.args.camera_height)
        if not np.isfinite([self.dx, self.dy, self.height, self.step, args.camera_height]).all() or min(self.height, self.step, args.camera_height) <= 0:
            raise ValueError('Finite parameters and positive heights/step required')
        self.geod = Geod(ellps='WGS84')
        self.to_geo = Transformer.from_crs(CRS, 'EPSG:4326', always_xy=True)
        for name in ('back', 'forward', 'save', 'fullscreen'):
            plt.rcParams[f'keymap.{name}'] = []
        n = len(self.cameras)
        self.fig, axes = plt.subplots(int(np.ceil(n/2)), 2, figsize=(14, 9), squeeze=False)
        self.panels = []
        for cam_no, (ax, entry) in enumerate(zip(axes.flat, self.cameras), 1):
            with Image.open(args.manifest.parent/entry['cylindrical_view']) as image:
                rgb = np.asarray(image.convert('RGB'))
            with Image.open(args.manifest.parent/entry['raw_image']) as source:
                source_size = source.size
            ax.imshow(rgb)
            ax.set_title(f"Cámara {cam_no}: {entry['pano_id']}", fontsize=8)
            ax.set_axis_off()
            line_sets = []
            for lot_no, lot in enumerate(self.lots):
                line = LineCollection([], colors=COLORS[lot_no % len(COLORS)], linewidths=1.1)
                ax.add_collection(line)
                line_sets.append(line)
            self.panels.append((entry, line_sets, source_size, (rgb.shape[1], rgb.shape[0])))
        for ax in list(axes.flat)[n:]:
            ax.set_visible(False)
        self.fig.subplots_adjust(top=.84, bottom=.09, wspace=.02, hspace=.12)
        self.title = self.fig.suptitle('')
        self.fig.text(.5, .02, 'Flechas: Este/Norte | [ / ]: paso ÷2/×2 | +/-: altura | r: reset | s: guardar', ha='center', fontsize=10)
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        self.refresh()

    def project_lot(self, lot, entry, source_size, strip_size):
        footprint = translate(lot['geometry'], xoff=self.dx, yoff=self.dy)
        camera = PanoramaCamera((0., 0., self.args.camera_height), entry['heading_deg'])
        curves = []
        for _, points in prism_edges(footprint, self.height):
            lon, lat = self.to_geo.transform(points[:, 0], points[:, 1])
            az, _, distance = self.geod.inv(np.full(len(lon), entry['lon']), np.full(len(lat), entry['lat']), lon, lat)
            az = np.radians(az)
            enu = np.column_stack((distance*np.sin(az), distance*np.cos(az), points[:, 2]))
            uv = strip_pixels(camera.pixels(enu, *source_size), source_size, strip_size,
                              entry['relative_yaw_deg'], self.data['horizontal_fov_deg'])
            pairs = np.stack((uv[:-1], uv[1:]), axis=1)
            curves.extend(pairs[np.abs(np.diff(uv[:, 0])) < strip_size[0]/2])
        return curves

    def refresh(self):
        for entry, line_sets, source_size, size in self.panels:
            for line, lot in zip(line_sets, self.lots):
                line.set_segments(self.project_lot(lot, entry, source_size, size))
        ids = ', '.join(str(lot['objectid']) for lot in self.lots)
        self.title.set_text(f'{len(self.lots)} lotes visibles | Este {self.dx:+.3f} m | Norte {self.dy:+.3f} m\n'
                            f'Paso {self.step:.3f} m | Altura común {self.height:.1f} m | IDs: {ids}\n{self.saved}')
        self.fig.canvas.draw_idle()

    def on_key(self, event):
        if event.key in {'left', 'right', 'up', 'down'}:
            dx, dy = {'left': (-1, 0), 'right': (1, 0), 'up': (0, 1), 'down': (0, -1)}[event.key]
            self.dx += dx*self.step
            self.dy += dy*self.step
        elif event.key == '[':
            self.step = max(.001, self.step/2)
        elif event.key == ']':
            self.step = min(10., self.step*2)
        elif event.key in {'+', '='}:
            self.height += 1
        elif event.key == '-':
            self.height = max(1., self.height-1)
        elif event.key == 'r':
            self.dx = self.dy = 0.
        elif event.key == 's':
            payload = {'schema_version': 1, 'target_objectids': [lot['objectid'] for lot in self.lots],
                       'crs': CRS, 'east_m': self.dx, 'north_m': self.dy, 'height_m': self.height,
                       'camera_height_m': self.args.camera_height, 'scope': 'shared_lot_set',
                       'lots': [{k: lot[k] for k in ('objectid', 'distance_m', 'reference_camera', 'visible_edges')} for lot in self.lots]}
            self.args.correction.parent.mkdir(parents=True, exist_ok=True)
            self.args.correction.write_text(json.dumps(payload, indent=2, allow_nan=False))
            self.saved = f'Guardado: {self.args.correction.name}'
        else:
            return
        self.refresh()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT/'steps/step5_cylindrical_facade/outputs/lot_-12.135895_-77.019184/projection_metadata.json')
    parser.add_argument('--shapefile', type=Path, default=ROOT.parent/'Lotes/shp_files/BARRANCO_LM_geogpsperu_SuyoPomalia.shp')
    parser.add_argument('--correction', type=Path, default=Path(__file__).resolve().parent/'outputs/alignment.json')
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--max-distance', type=float, default=100.)
    parser.add_argument('--height', type=float, default=10.)
    parser.add_argument('--camera-height', type=float, default=2.5)
    parser.add_argument('--step', type=float, default=.1)
    parser.add_argument('--preview', type=Path)
    args = parser.parse_args()
    viewer = BatchViewer(args)
    if args.preview:
        viewer.fig.savefig(args.preview, dpi=120)
        plt.close(viewer.fig)
    else:
        plt.show()


if __name__ == '__main__':
    main()
