"""Render one aligned comparison with several visible cadastral lots."""
import argparse
import json
from pathlib import Path
import sys

import cv2
import geopandas as gpd
import numpy as np
from pyproj import Geod, Transformer
from shapely.affinity import translate
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from camera_selection import score_edges
from geometry_projection.spherical import PanoramaCamera, prism_edges, strip_pixels, draw_edges

CRS = 'EPSG:32718'
COLORS = [(255, 0, 255), (0, 170, 85), (0, 140, 255), (255, 130, 20), (180, 50, 200), (40, 200, 220), (220, 80, 40), (80, 180, 80)]


def choose_lots(gdf, cameras, top_k, max_distance):
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
            edges = score_edges(gdf, index, polygon, point, spatial_index)
            visible = [edge for edge in edges if edge['visible']]
            if visible:
                candidate = (distance, -len(visible), str(camera['pano_id']))
                if best is None or candidate < best[0]:
                    best = (candidate, camera, visible)
        if best:
            candidates.append({'index': int(index), 'objectid': int(row.objectid), 'geometry': polygon,
                               'distance_m': best[0][0], 'reference_camera': best[1]['pano_id'],
                               'visible_edges': len(best[2])})
    candidates.sort(key=lambda item: (item['distance_m'], -item['visible_edges']))
    return candidates[:top_k]


def project_lot(lot, entry, source_size, strip_size, shift, height, camera_height, horizontal_fov, to_geo, geod):
    footprint = translate(lot['geometry'], xoff=shift[0], yoff=shift[1])
    camera = PanoramaCamera((0., 0., camera_height), entry['heading_deg'])
    panorama_curves, strip_curves = [], []
    for _, points in prism_edges(footprint, height):
        lon, lat = to_geo.transform(points[:, 0], points[:, 1])
        azimuth, _, distance = geod.inv(np.full(len(lon), entry['lon']), np.full(len(lat), entry['lat']), lon, lat)
        azimuth = np.radians(azimuth)
        enu = np.column_stack((distance * np.sin(azimuth), distance * np.cos(azimuth), points[:, 2]))
        panorama_pixels = camera.pixels(enu, *source_size)
        strip_curves.append(strip_pixels(
            panorama_pixels, source_size, strip_size, entry['relative_yaw_deg'],
            horizontal_fov,
        ))
        panorama_curves.append(panorama_pixels)
    return panorama_curves, strip_curves


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'steps/step5_cylindrical_facade/outputs/lot_-12.135895_-77.019184/projection_metadata.json')
    parser.add_argument('--shapefile', type=Path, default=ROOT.parent / 'Lotes/shp_files/BARRANCO_LM_geogpsperu_SuyoPomalia.shp')
    parser.add_argument('--correction', type=Path, default=Path(__file__).resolve().parent / 'outputs/alignment.json')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent / 'outputs/comparison.png')
    parser.add_argument('--top-k', type=int, choices=range(5, 9), default=8)
    parser.add_argument('--max-distance', type=float, default=100.)
    parser.add_argument('--height', type=float, default=10.)
    args = parser.parse_args()
    if not args.correction.is_file():
        raise FileNotFoundError(args.correction)
    correction = json.loads(args.correction.read_text())
    if correction.get('crs') != CRS:
        raise ValueError('La corrección debe estar en EPSG:32718')
    data = json.loads(args.manifest.read_text())
    lots = gpd.read_file(args.shapefile).to_crs(CRS)
    transformer = Transformer.from_crs('EPSG:4326', CRS, always_xy=True)
    cameras = []
    for entry in data['cameras']:
        x, y = transformer.transform(float(entry['lon']), float(entry['lat']))
        cameras.append({**entry, 'camera_x': x, 'camera_y': y})
    selected = choose_lots(lots, cameras, args.top_k, args.max_distance)
    if len(selected) < args.top_k:
        raise RuntimeError(f'Solo se encontraron {len(selected)} lotes visibles')
    to_geo = Transformer.from_crs(CRS, 'EPSG:4326', always_xy=True)
    geod = Geod(ellps='WGS84')
    panorama_panels, strip_panels = [], []
    for camera_number, entry in enumerate(cameras, 1):
        panorama = cv2.imread(str(args.manifest.parent / entry['raw_image']))
        strip = cv2.imread(str(args.manifest.parent / entry['cylindrical_view']))
        if panorama is None or strip is None:
            raise ValueError(f'No se pudo leer {entry["pano_id"]}')
        ph, pw = panorama.shape[:2]
        sh, sw = strip.shape[:2]
        panorama_overlay, strip_overlay = panorama.copy(), strip.copy()
        for lot_number, lot in enumerate(selected):
            pano_curves, strip_curves = project_lot(lot, entry, (pw, ph), (sw, sh),
                                                     (correction['east_m'], correction['north_m']),
                                                     args.height, correction.get('camera_height_m', 2.5),
                                                     float(data['horizontal_fov_deg']), to_geo, geod)
            color = COLORS[lot_number % len(COLORS)]
            draw_edges(panorama_overlay, pano_curves, color, 2)
            draw_edges(strip_overlay, strip_curves, color, 2)
        for image, title, target in ((panorama_overlay, f'CAM {camera_number} | panorama', panorama_panels),
                                     (strip_overlay, f'CAM {camera_number} | cilindrica', strip_panels)):
            image = cv2.resize(image, (720, round(720 * image.shape[0] / image.shape[1])))
            cv2.rectangle(image, (0, 0), (image.shape[1], 34), (0, 0, 0), -1)
            cv2.putText(image, title, (12, 23), cv2.FONT_HERSHEY_SIMPLEX, .7, (255, 255, 255), 2, cv2.LINE_AA)
            target.append(image)
    panel_width = max(image.shape[1] for image in panorama_panels + strip_panels)
    panorama_height = max(image.shape[0] for image in panorama_panels)
    strip_height = max(image.shape[0] for image in strip_panels)
    legend_height = 72
    canvas = np.zeros((legend_height + panorama_height + strip_height,
                       len(cameras) * panel_width, 3), dtype=np.uint8)
    cv2.putText(canvas, f'Alineado | E {correction["east_m"]:+.3f} m, N {correction["north_m"]:+.3f} m | altura {args.height:.1f} m',
                (12, 25), cv2.FONT_HERSHEY_SIMPLEX, .62, (255, 255, 255), 2, cv2.LINE_AA)
    cursor = 12
    for lot_number, lot in enumerate(selected):
        label = str(lot['objectid'])
        color = COLORS[lot_number % len(COLORS)]
        cv2.rectangle(canvas, (cursor, 43), (cursor + 12, 55), color, -1)
        cv2.putText(canvas, label, (cursor + 16, 54), cv2.FONT_HERSHEY_SIMPLEX, .38, color, 1, cv2.LINE_AA)
        cursor += 16 + cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, .38, 1)[0][0]
    for index, image in enumerate(panorama_panels):
        x = index * panel_width
        y = legend_height
        canvas[y:y + image.shape[0], x:x + image.shape[1]] = image
    for index, image in enumerate(strip_panels):
        x = index * panel_width
        y = legend_height + panorama_height
        canvas[y:y + image.shape[0], x:x + image.shape[1]] = image
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), canvas):
        raise OSError(args.output)
    print(f'Lotes seleccionados: {[lot["objectid"] for lot in selected]}')
    print(f'Cámaras: {len(cameras)}; comparación: {args.output}')


if __name__ == '__main__':
    main()
