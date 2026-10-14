"""Match existing Stage 1 descriptors: exact L2 nearest neighbors + Lowe 0.7.

Matching is directional A -> B, without cross-check or additional filters.
The pre-ratio count is one nearest-neighbor candidate per query with two
available neighbors (not the combined count of both neighbors).
"""

import json
from pathlib import Path

import cv2
import numpy as np


STEP = Path(__file__).resolve().parent
ROOT = STEP.parent.parent
PAIRS = [('C0', 'C1'), ('C1', 'C2'), ('C2', 'C3'),
         ('C0', 'C2'), ('C1', 'C3')]
LOWE_RATIO = 0.7


def load_panorama(entry, feature_dir=None):
    pano_id = entry['pano_id']
    path = (feature_dir or STEP / 'output_stage1') / f"{entry['camera']}_{pano_id}.npz"
    with np.load(path, allow_pickle=False) as data:
        uv = data['keypoints_uv'].copy()
        descriptors = np.ascontiguousarray(data['descriptors'], dtype=np.float32)
        wh = data['image_wh'].copy()
        if str(data['pano_id'].item()) != pano_id:
            raise ValueError(f'Panorama ID mismatch: {path}')
    if uv.shape != (len(descriptors), 2) or descriptors.shape != (len(uv), 128):
        raise ValueError(f'Invalid feature shapes: {path}')
    if not np.isfinite(uv).all() or not np.isfinite(descriptors).all():
        raise ValueError(f'Non-finite features: {path}')
    image = cv2.imread(str(ROOT / 'data/fotos_barranco' / f'{pano_id}.jpg'))
    if image is None or tuple(wh) != (image.shape[1], image.shape[0]):
        raise ValueError(f'Missing image or inconsistent dimensions: {pano_id}')
    return uv, descriptors, image


def match_descriptors(desc_a, desc_b):
    matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    neighbors = matcher.knnMatch(desc_a, desc_b, k=2) if len(desc_a) and len(desc_b) >= 2 else []
    candidates = [pair for pair in neighbors if len(pair) == 2]
    # A zero second distance is an ambiguous tie and fails the strict ratio test.
    accepted = [(first, first.distance / second.distance)
                for first, second in candidates
                if first.distance < LOWE_RATIO * second.distance]
    return len(candidates), accepted


def draw_matches(image_a, image_b, uv_a, uv_b, label):
    """All accepted matches, on original-resolution ERP images side by side."""
    height = max(image_a.shape[0], image_b.shape[0])
    offset = image_a.shape[1]
    canvas = np.zeros((height, offset + image_b.shape[1], 3), dtype=np.uint8)
    canvas[:image_a.shape[0], :offset] = image_a
    canvas[:image_b.shape[0], offset:] = image_b
    rng = np.random.default_rng(20)  # Only controls debug line colors.
    for a, b in zip(uv_a, uv_b):
        color = tuple(int(c) for c in rng.integers(64, 256, size=3))
        pa = (round(float(a[0])), round(float(a[1])))
        pb = (offset + round(float(b[0])), round(float(b[1])))
        cv2.line(canvas, pa, pb, color, 1, cv2.LINE_AA)
        cv2.circle(canvas, pa, 3, color, 1)
        cv2.circle(canvas, pb, 3, color, 1)
    cv2.putText(canvas, label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                1, (0, 255, 255), 2, cv2.LINE_AA)
    return canvas


def main(entries=None, pairs=None, feature_dir=None, output=None, progress=print, debug_images=True):
    entries = entries if entries is not None else json.loads((STEP / 'output_stage1/summary.json').read_text())
    entries = {entry['camera']: entry for entry in entries}
    output = output or STEP / 'output_stage2'
    output.mkdir(exist_ok=True)
    stats = []
    for a, b in (pairs if pairs is not None else PAIRS):
        progress(f'Matching {a} -> {b}')
        uv_a, desc_a, image_a = load_panorama(entries[a], feature_dir)
        uv_b, desc_b, image_b = load_panorama(entries[b], feature_dir)
        before, accepted = match_descriptors(desc_a, desc_b)
        indices_a = np.array([match.queryIdx for match, _ in accepted], dtype=np.int32)
        indices_b = np.array([match.trainIdx for match, _ in accepted], dtype=np.int32)
        coords_a, coords_b = uv_a[indices_a], uv_b[indices_b]
        stem = f'{a}_{b}'
        np.savez_compressed(
            output / f'{stem}_matches.npz',
            indices_a=indices_a, indices_b=indices_b,
            uv_a=coords_a, uv_b=coords_b,
            descriptor_distance=np.array([match.distance for match, _ in accepted], dtype=np.float32),
            lowe_ratio=np.array([ratio for _, ratio in accepted], dtype=np.float64),
            pano_id_a=np.array(entries[a]['pano_id']),
            pano_id_b=np.array(entries[b]['pano_id']),
            ratio_threshold=np.array(LOWE_RATIO),
        )
        if debug_images:
            debug = draw_matches(image_a, image_b, coords_a, coords_b,
                                 f'{a} -> {b}: {len(accepted)} matches; Lowe < {LOWE_RATIO}')
            if not cv2.imwrite(str(output / f'{stem}_matches.jpg'), debug):
                raise OSError(f'Could not save debug image: {stem}')
        stats.append({'pair': stem, 'pano_id_a': entries[a]['pano_id'],
                      'pano_id_b': entries[b]['pano_id'],
                      'keypoints_a': len(uv_a), 'keypoints_b': len(uv_b),
                      'matches_before_ratio': before,
                      'matches_after_ratio': len(accepted),
                      'ratio_threshold': LOWE_RATIO, 'direction': 'A -> B',
                      'matcher': 'exact BF L2, k=2, no cross-check'})
        print(f'{stem}: {before} -> {len(accepted)}', flush=True)
    (output / 'stats.json').write_text(json.dumps(stats, indent=2) + '\n')
    return stats


if __name__ == '__main__':
    main()
