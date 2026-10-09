"""Previews from user segmentations: mask raster, masked cutout, overlay, lot guide.

Reads per-lot segmentation.json (polygons) + views.json. Writes into each lot
folder, alongside the labelled JPGs:
  <camera>_mask.png      binary mask (255=building) at JPG resolution
  <camera>_masked.jpg    original with background zeroed (focus on building)
  <camera>_overlay.jpg   original + green mask overlay (what was labelled)
  <camera>_lot.jpg       original + yellow cadastral prism (guide only)

Absent views are skipped. The cadastral prism uses data/cadastral_offset.json
and the nominal height stored in views.json; it never enters the mask.
"""
import json
import sys
from pathlib import Path

import cv2
import geopandas as gpd
import numpy as np
from pyproj import Transformer
from shapely.affinity import translate

STEP = Path(__file__).resolve().parent
ROOT = STEP.parent.parent
sys.path.insert(0, str(STEP))
from label_buildings import box_lines

BASE = STEP / 'edificios_a_probar'


def rasterize(polygons, size):
    ow, oh = size
    mask = np.zeros((oh, ow), dtype=np.uint8)
    for poly in polygons:
        ext = np.rint(np.array(poly['exterior'])).astype(np.int32)
        if len(ext) >= 3:
            cv2.fillPoly(mask, [ext], 1)
            for hole in poly.get('holes', []):
                h = np.rint(np.array(hole)).astype(np.int32)
                if len(h) >= 3:
                    cv2.fillPoly(mask, [h], 0)
    return mask


def main():
    lots = gpd.read_file(ROOT / 'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    geometries = {int(k): g for k, g in zip(lots.objectid, lots.geometry)}
    poses = json.loads((ROOT / 'data/poses_barranco/metadata.json').read_text())['panoramas']
    offset = json.loads((ROOT / 'data/cadastral_offset.json').read_text())
    assert offset['crs'] == 'EPSG:32718'
    project = Transformer.from_crs(4326, 32718, always_xy=True)

    folders = sorted(p for p in BASE.iterdir() if p.is_dir() and (p / 'views.json').exists())
    n_ok = n_absent = n_missing = 0
    for folder in folders:
        lot_id = int(folder.name)
        views = {v['camera_id']: v for v in json.loads((folder / 'views.json').read_text())['views']}
        nominal = json.loads((folder / 'views.json').read_text())['nominal_roof_height_m']
        seg = json.loads((folder / 'segmentation.json').read_text()) if (folder / 'segmentation.json').exists() else {'images': {}}
        polygon = translate(geometries[lot_id], xoff=offset['east_m'], yoff=offset['north_m'])
        for cam_id, entry in seg.get('images', {}).items():
            if entry.get('status') != 'present':
                n_absent += 1
                continue
            view = views.get(cam_id)
            src = folder / entry.get('file', '')
            if view is None or not src.exists():
                n_missing += 1
                continue
            img = cv2.imread(str(src))
            if img is None:
                n_missing += 1
                continue
            oh, ow = img.shape[:2]
            mask = rasterize(entry.get('polygons', []), (ow, oh))
            if not mask.any():
                print(f'{lot_id}/{cam_id}: polygons rasterize empty, skip')
                continue
            # 1. binary mask PNG (exact JPG size)
            cv2.imwrite(str(folder / f'{cam_id}_mask.png'), (mask * 255).astype(np.uint8))
            # 2. masked cutout: background to black
            cutout = img * mask[..., None]
            cv2.imwrite(str(folder / f'{cam_id}_masked.jpg'), cutout, [cv2.IMWRITE_JPEG_QUALITY, 92])
            # 3. overlay: green translucent mask
            overlay = img.copy()
            overlay[mask.astype(bool)] = (0.6 * overlay[mask.astype(bool)].astype(float)
                                          + 0.4 * np.array([20, 245, 90])).astype(np.uint8)
            cv2.imwrite(str(folder / f'{cam_id}_overlay.jpg'), overlay, [cv2.IMWRITE_JPEG_QUALITY, 92])
            # 4. lot guide: yellow prism reprojected with same pinhole as the crop
            meta = poses[cam_id]
            camera_xy = project.transform(meta['lon'], meta['lat'])
            guide = img.copy()
            for a, b in box_lines(polygon, camera_xy, nominal, view['horizontal_fov_deg'], (ow, oh)):
                cv2.line(guide, a, b, (40, 200, 255), 2, cv2.LINE_AA)
            cv2.imwrite(str(folder / f'{cam_id}_lot.jpg'), guide, [cv2.IMWRITE_JPEG_QUALITY, 92])
            # record preview files in segmentation.json entry
            entry['mask_file'] = f'{cam_id}_mask.png'
            entry['masked_file'] = f'{cam_id}_masked.jpg'
            entry['overlay_file'] = f'{cam_id}_overlay.jpg'
            entry['lot_file'] = f'{cam_id}_lot.jpg'
            n_ok += 1
        (folder / 'segmentation.json').write_text(json.dumps(seg, ensure_ascii=False, indent=2) + '\n')
        print(f'{lot_id}: previews updated', flush=True)
    print(f'Done: {n_ok} present, {n_absent} absent, {n_missing} missing JPG')


if __name__ == '__main__':
    main()
