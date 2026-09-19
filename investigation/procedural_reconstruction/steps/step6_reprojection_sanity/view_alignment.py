"""Interactive shared UTM translation of one lot across all Step 5 cameras."""
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from geometry_projection.spherical import PanoramaCamera, prism_edges, strip_pixels


class AlignmentViewer:
    def __init__(self, args):
        self.args = args
        self.data = json.loads(args.manifest.read_text())
        if self.data.get('projection') != 'full_vertical_angular_cylindrical_strip':
            raise ValueError('Expected Step 5 manifest')
        lots = gpd.read_file(args.shapefile).to_crs(32718)
        match = lots[lots.objectid.astype(int) == int(self.data['target_objectid'])]
        if len(match) != 1 or not self.data['cameras']:
            raise ValueError('Expected one target lot and at least one camera')
        self.footprint = match.iloc[0].geometry
        self.dx, self.dy = 0., 0.
        self.height, self.step = args.height, args.step
        self.saved = ''
        if args.correction.is_file():
            correction = json.loads(args.correction.read_text())
            if correction['target_objectid'] != self.data['target_objectid'] or correction['crs'] != 'EPSG:32718':
                raise ValueError('Correction belongs to a different lot or CRS')
            self.dx, self.dy = correction['east_m'], correction['north_m']
            self.height = correction['height_m']
            args.camera_height = correction['camera_height_m']
        if not np.isfinite([self.dx, self.dy, self.height, self.step, args.camera_height]).all() or min(self.height, self.step, args.camera_height) <= 0:
            raise ValueError('Finite parameters and positive heights/step required')
        self.transform = Transformer.from_crs(32718, 4326, always_xy=True)
        self.geod = Geod(ellps='WGS84')
        # Disable default arrow navigation/save shortcuts: these keys edit the model.
        for name in ('back', 'forward', 'save', 'fullscreen'):
            plt.rcParams[f'keymap.{name}'] = []
        n = len(self.data['cameras'])
        self.fig, axes = plt.subplots(int(np.ceil(n/2)), 2, figsize=(14, 9), squeeze=False)
        self.panels = []
        for ax, entry in zip(axes.flat, self.data['cameras']):
            path = args.manifest.parent/entry['cylindrical_view']
            with Image.open(path) as image:
                rgb = np.asarray(image.convert('RGB'))
            with Image.open(args.manifest.parent/entry['raw_image']) as source:
                source_size = source.size
            ax.imshow(rgb)
            ax.set_title(f"Cam {len(self.panels)+1}: {entry['pano_id']}", fontsize=8)
            ax.set_axis_off()
            lines = LineCollection([], colors='#ff00ff', linewidths=1.3)
            ax.add_collection(lines)
            self.panels.append((entry, lines, source_size, (rgb.shape[1], rgb.shape[0])))
        for ax in list(axes.flat)[n:]:
            ax.set_visible(False)
        self.fig.subplots_adjust(top=.85, bottom=.08, wspace=.02, hspace=.12)
        self.title = self.fig.suptitle('')
        self.fig.text(.5, .02, 'Flechas: Este/Norte | [ / ]: paso ÷2/×2 | +/-: altura 1m | r: reset XY | s: guardar', ha='center', fontsize=10)
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        self.refresh()

    def refresh(self):
        model = prism_edges(self.footprint, self.height)
        for entry, lines, source_size, size in self.panels:
            camera = PanoramaCamera((0., 0., self.args.camera_height), entry['heading_deg'])
            segments = []
            for _, original in model:
                points = original.copy()
                points[:, :2] += [self.dx, self.dy]
                lon, lat = self.transform.transform(points[:, 0], points[:, 1])
                az, _, distance = self.geod.inv(np.full(len(lon), entry['lon']), np.full(len(lat), entry['lat']), lon, lat)
                az = np.radians(az)
                enu = np.column_stack((distance*np.sin(az), distance*np.cos(az), points[:, 2]))
                uv = strip_pixels(camera.pixels(enu, *source_size), source_size, size,
                                  entry['relative_yaw_deg'], self.data['horizontal_fov_deg'])
                pairs = np.stack((uv[:-1], uv[1:]), axis=1)
                segments.extend(pairs[np.abs(np.diff(uv[:, 0])) < size[0]/2])
            lines.set_segments(segments)
        self.title.set_text(f'Desplazamiento del lote UTM: Este {self.dx:+.3f} m | Norte {self.dy:+.3f} m\n'
                            f'Paso {self.step:.3f} m | Edificio {self.height:.1f} m | Cámara {self.args.camera_height:g} m\n{self.saved}')
        self.fig.canvas.draw_idle()

    def on_key(self, event):
        key = event.key
        directions = {'left': (-1, 0), 'right': (1, 0), 'up': (0, 1), 'down': (0, -1)}
        if key in directions:
            x, y = directions[key]
            self.dx += x*self.step
            self.dy += y*self.step
        elif key == '[':
            self.step = max(.001, self.step/2)
        elif key == ']':
            self.step = min(10., self.step*2)
        elif key in ('+', '='):
            self.height += 1
        elif key == '-':
            self.height = max(1., self.height-1)
        elif key == 'r':
            self.dx = self.dy = 0.
        elif key == 's':
            self.args.correction.parent.mkdir(parents=True, exist_ok=True)
            payload = {'schema_version': 1, 'target_objectid': self.data['target_objectid'],
                       'crs': 'EPSG:32718', 'east_m': self.dx, 'north_m': self.dy,
                       'height_m': self.height, 'camera_height_m': self.args.camera_height,
                       'scope': 'this_lot_shared_across_cameras', 'manifest': str(self.args.manifest.resolve())}
            self.args.correction.write_text(json.dumps(payload, indent=2, allow_nan=False))
            self.saved = f'Guardado: {self.args.correction.name}'
            print(self.args.correction.resolve(), flush=True)
            self.refresh()
            return
        else:
            return
        self.saved = 'Ajuste sin guardar'
        self.refresh()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT/'steps/step5_cylindrical_facade/outputs/lot_-12.135895_-77.019184/projection_metadata.json')
    parser.add_argument('--shapefile', type=Path, default=ROOT.parent/'Lotes/shp_files/BARRANCO_LM_geogpsperu_SuyoPomalia.shp')
    parser.add_argument('--correction', type=Path, default=Path(__file__).resolve().parent/'outputs/alignment.json')
    parser.add_argument('--height', type=float, default=20.)
    parser.add_argument('--camera-height', type=float, default=2.5)
    parser.add_argument('--step', type=float, default=.1)
    parser.add_argument('--preview', type=Path, help='Render initial state without GUI')
    args = parser.parse_args()
    viewer = AlignmentViewer(args)
    if args.preview:
        viewer.fig.savefig(args.preview, dpi=120)
        plt.close(viewer.fig)
    else:
        plt.show()


if __name__ == '__main__':
    main()
