"""Offline experiment runners; observations always refer to original pixels."""
import argparse
from dataclasses import replace
import json
from pathlib import Path

import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pyproj import Transformer, Geod
from shapely.geometry import Polygon, Point
from shapely.affinity import translate
from shapely.ops import nearest_points

from datasets import read_reconstruction_input
from domain import Alignment2D, LotGeometry
from facade_observations import detect_roof_boundary
from structural_estimation import aligned_footprint, fit_height, predicted_row, regularize_height_to_floors
from geometry_projection.spherical import draw_edges
from geometry_projection.reprojection import project_prism_to_panorama
from geometry_projection.cylindrical import extract_full_vertical_strip
from procedural_modeling import build_building_specification, write_building_specification

ROOT = Path(__file__).resolve().parents[2]


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def detect(package_path, correction_path, output, strip_width=9):
    if strip_width < 1 or strip_width % 2 == 0:
        raise ValueError('strip_width must be positive and odd')
    package = read_reconstruction_input(package_path)
    correction = json.loads(correction_path.read_text())
    if correction['crs'] != package.lot.crs or correction['target_objectid'] != package.lot.objectid:
        raise ValueError('Alignment and lot must match')
    polygon = aligned_footprint(Polygon(package.lot.footprint_xy), correction['east_m'], correction['north_m'])
    to_xy = Transformer.from_crs('EPSG:4326', package.lot.crs, always_xy=True)
    to_geo = Transformer.from_crs(package.lot.crs, 'EPSG:4326', always_xy=True)
    geod = Geod(ellps='WGS84')
    observations = []
    fig, axes = plt.subplots(len(package.views), 2, figsize=(13, 5*len(package.views)), squeeze=False)
    for i, view in enumerate(package.views):
        view_data = {
            'pano_id': view.pano_id, 'image_path': str(view.image_path),
            'lat': view.pose.latitude, 'lon': view.pose.longitude,
            'heading_deg': view.pose.heading_deg, 'pitch_deg': view.pose.pitch_deg,
            'roll_deg': view.pose.roll_deg, 'date': view.capture_date,
            'capture_year': view.capture_year, 'relative_yaw_deg': view.relative_yaw_deg,
            'target_bearing_deg': view.target_bearing_deg,
            'camera_to_lot_m': view.camera_to_lot_m,
        }
        bgr = cv2.imread(view_data['image_path'])
        if bgr is None:
            raise FileNotFoundError(view_data['image_path'])
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        camera_point = Point(*to_xy.transform(view_data['lon'], view_data['lat']))
        if polygon.covers(camera_point):
            raise ValueError('Camera inside aligned target footprint')
        target = nearest_points(camera_point, polygon.boundary)[1]
        lon, lat = to_geo.transform(target.x, target.y)
        bearing, _, distance = geod.inv(view_data['lon'], view_data['lat'], lon, lat)
        yaw = (bearing-view_data['heading_deg']+180)%360-180
        x = (.5+yaw/360)*w % w
        base_y = int(np.clip(predicted_row(0, distance, h, correction['camera_height_m']), 1, h-1))
        cols = (int(round(x))+np.arange(-(strip_width//2), strip_width//2+1)) % w
        strip = rgb[:base_y+1, cols]
        roof = detect_roof_boundary(strip)
        cut, separation = roof['cut_y'], roof['separation']
        height = correction['camera_height_m'] + distance*np.tan((.5-cut/h)*np.pi)
        usable = bool(separation >= .2 and 0 < cut < h/2 and 1 <= height <= 150)
        obs = {**view_data, 'target_xy': [target.x, target.y], 'distance_m': distance,
               'yaw_deg': yaw, 'column_x': x, 'base_y': base_y, 'cut_y': cut,
               'image_height': h, 'image_width': w, 'separation': separation,
               'individual_height_m': float(height), 'usable': usable,
               'binary_intervals_half_open': {'sky': [0, cut], 'structure': [cut, base_y+1]},
               'usability_policy': 'separation>=0.2, above horizon, inferred height in [1,150]m'}
        observations.append(obs)
        crop = extract_full_vertical_strip(rgb, yaw, 90, 600, h)
        axes[i, 0].imshow(crop)
        axes[i, 0].axvline(300, color='yellow', lw=1)
        axes[i, 0].plot(300, cut, 'rx', ms=12)
        axes[i, 0].axhline(cut, color='red', lw=.8)
        axes[i, 0].set_title(f'Camera {i+1}: cut={cut}px; inferred={height:.1f}m; usable={usable}')
        axes[i, 1].imshow(strip, aspect='auto')
        axes[i, 1].axhline(cut, color='red')
        axes[i, 1].set_title(f'Strip {len(cols)}px | color separation={separation:.3f}')
    output.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output/'comparison.png', dpi=120)
    plt.close(fig)
    report = {'schema_version': 2, 'objectid': package.lot.objectid, 'crs': package.lot.crs,
              'method': {'name': 'ordered_two_region_lab_sse', 'lab_weights': [.2, 1, 1],
                         'strip_width_px': strip_width, 'min_segment_px': 8},
              'aligned_polygon': list(map(list, polygon.exterior.coords)),
              'alignment': correction, 'input': str(package_path.resolve()),
              'pose_policy': 'upright panorama; provider pitch/roll recorded but not applied',
              'observations': observations}
    save_json(output/'observations.json', report)
    return report


def optimize(path, output):
    report = json.loads(path.read_text())
    usable = [o for o in report['observations'] if o['usable']]
    camera_height = report['alignment']['camera_height_m']
    fit = fit_height(usable, camera_height)
    fit['procedural_regularization'] = regularize_height_to_floors(fit['height_m'])
    if len(usable) >= 3:
        fit['leave_one_out_heights_m'] = [fit_height(usable[:i]+usable[i+1:], camera_height)['height_m'] for i in range(len(usable))]
    polygon = Polygon(report['aligned_polygon'])
    fig, axes = plt.subplots(1, len(report['observations']), figsize=(6*len(report['observations']), 9), squeeze=False)
    for i, obs in enumerate(report['observations']):
        bgr = cv2.imread(obs['image_path'])
        if bgr is None:
            raise FileNotFoundError(obs['image_path'])
        h, w = bgr.shape[:2]
        curves = project_prism_to_panorama(
            polygon, fit['height_m'], crs=report['crs'], latitude=obs['lat'], longitude=obs['lon'],
            heading_deg=obs['heading_deg'], image_width=w, image_height=h, camera_height_m=camera_height,
        )
        draw_edges(bgr, curves, (0, 255, 0), 2)
        crop = extract_full_vertical_strip(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), obs['yaw_deg'], 90, 600, h)
        ax = axes[0, i]
        ax.imshow(crop)
        ax.plot(300, obs['cut_y'], 'rx', ms=12, label='Detected roof')
        pred = float(predicted_row(fit['height_m'], obs['distance_m'], h, camera_height))
        ax.plot(300, pred, 'co', ms=5, label='Fitted roof')
        ax.set_title(f'Camera {i+1} | H={fit["height_m"]:.2f}m\nDetection={obs["individual_height_m"]:.2f}m; residual={pred-obs["cut_y"]:+.1f}px')
        ax.legend()
    output.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output/'comparison.png', dpi=120)
    plt.close(fig)
    height_payload = {**fit, 'schema_version': 2, 'objectid': report['objectid'],
              'observations_file': str(path.resolve()), 'camera_height_m': camera_height,
              'used_pano_ids': [o['pano_id'] for o in usable],
              'assumptions': ['flat shared ground', 'vertical extrusion of aligned cadastral footprint',
                              'color boundary is roof of target; requires visual verification'],
              'validation': 'estimate, not measured ground truth',
              'quality': 'needs_geometric_review' if fit['rmse_normalized_px'] > 5 or fit['at_bound'] else 'consistent_reprojection',
              'quality_threshold_normalized_px': 5.}
    save_json(output/'height_fit.json', height_payload)
    original_input = read_reconstruction_input(Path(report['input']))
    aligned_input = replace(
        original_input,
        lot=LotGeometry(original_input.lot.objectid, original_input.lot.crs,
                        tuple(map(tuple, report['aligned_polygon'])), original_input.lot.source_row,
                        original_input.lot.attributes),
        alignment=Alignment2D(report['alignment']['east_m'], report['alignment']['north_m'],
                              camera_height, source='step6_visual_alignment'),
    )
    specification = build_building_specification(aligned_input, height_payload)
    write_building_specification(specification, output/'building_specification.json')
    print(json.dumps(fit, indent=2))


def main(stage):
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=ROOT/'steps/step7_multiview_input/outputs/lot_1134979.json' if stage == 8 else ROOT/'steps/step8_roof_boundary/outputs/observations.json')
    parser.add_argument('--output', type=Path, default=ROOT/('steps/step8_roof_boundary/outputs' if stage == 8 else 'steps/step9_height_fit/outputs'))
    parser.add_argument('--alignment', type=Path, default=ROOT/'steps/step6_reprojection_sanity/outputs/alignment.json')
    args = parser.parse_args()
    if stage == 8:
        report = detect(args.input, args.alignment, args.output)
        print([(o['pano_id'], round(o['individual_height_m'], 2), o['usable']) for o in report['observations']])
    else:
        optimize(args.input, args.output)
