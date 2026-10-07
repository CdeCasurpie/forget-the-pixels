"""Run PR+SIFT only. Edit PANO_IDS to choose four different panoramas."""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from pr_sift import extract


# C0..C3: consecutive neighbor_ids links, same capture date (2025-11).
PANO_IDS = [
    'y6wTQXWFtsCBjb-BRPUoCw',
    '8yPLbN6fByAI3eZjzVk7KQ',
    'rvkgvAPcmbaxxwrJ3W6_pQ',
    'qrFborlUPyogCRVf6kXhLA',
]
STEP = Path(__file__).resolve().parent
ROOT = STEP.parent.parent


def save_image(path, image):
    if not cv2.imwrite(str(path), image):
        raise OSError(f'Could not save {path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--n', type=int, default=6)
    args = parser.parse_args()
    if args.n < 1:
        parser.error('--n must be positive')
    if len(PANO_IDS) != 4 or len(set(PANO_IDS)) != 4:
        raise ValueError('Configure exactly four distinct PANO_IDS')
    metadata = json.loads((ROOT / 'data/poses_barranco/metadata.json').read_text())['panoramas']
    for i, pano_id in enumerate(PANO_IDS):
        if pano_id not in metadata:
            raise ValueError(f'Missing metadata: {pano_id}')
        if i and pano_id not in metadata[PANO_IDS[i-1]]['neighbor_ids']:
            raise ValueError(f'C{i-1} and C{i} are not linked neighbors')
        if not (ROOT / 'data/fotos_barranco' / f'{pano_id}.jpg').is_file():
            raise FileNotFoundError(pano_id)
    output = STEP / 'output_stage1'
    output.mkdir(exist_ok=True)
    summary = []
    for i, pano_id in enumerate(PANO_IDS):
        image = cv2.imread(str(ROOT / 'data/fotos_barranco' / f'{pano_id}.jpg'))
        if image is None:
            raise ValueError(f'Unreadable panorama: {pano_id}')
        data, mosaic = extract(image, args.n)
        stem = f'C{i}_{pano_id}'
        np.savez_compressed(output / f'{stem}.npz', **data, pano_id=np.array(pano_id))
        debug = image.copy()
        for u, v in data['keypoints_uv']:
            cv2.circle(debug, (round(float(u)) % image.shape[1], round(float(v))),
                       2, (0, 255, 0), 1)
        save_image(output / f'{stem}_keypoints.jpg', debug)
        save_image(output / f'{stem}_rectifications.jpg', mosaic)
        count = len(data['keypoints_uv'])
        summary.append({'camera': f'C{i}', 'pano_id': pano_id, 'n': args.n,
                        'image_wh': data['image_wh'].tolist(), 'keypoints': count})
        print(f'C{i} {pano_id}: {count} keypoints', flush=True)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')


if __name__ == '__main__':
    main()
