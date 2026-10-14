"""Visualize cached detections and cumulative masks. No processing is rerun."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from run_stage2 import draw_matches

STEP = Path(__file__).resolve().parent


def load_npz(path):
    with np.load(path, allow_pickle=False) as data:
        return {k: data[k].copy() for k in data.files}


def save(path, image):
    if not cv2.imwrite(str(path), image):
        raise OSError(path)


def points_image(image, uv, label):
    canvas = image.copy()
    for u, v in uv:
        center = (round(float(u)) % image.shape[1], round(float(v)))
        cv2.circle(canvas, center, 4, (0, 0, 0), -1)
        cv2.circle(canvas, center, 3, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(canvas, label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 5)
    cv2.putText(canvas, label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
    return canvas


def coverage(uv, image):
    height, width = image.shape[:2]
    cells = np.floor((uv+0.5)/[width, height]*[20, 10]).astype(int)
    cells[:, 0] %= 20
    cells[:, 1] = np.clip(cells[:, 1], 0, 9)
    occupied = len(np.unique(cells, axis=0))
    return dict(grid=[20, 10], occupied_cells=occupied, occupied_percent=100*occupied/200,
                bbox_uv=[uv.min(axis=0).tolist(), uv.max(axis=0).tolist()] if len(uv) else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pair', nargs=2, default=['P16', 'P17'])
    args = parser.parse_args()
    a, b = args.pair; pair = f'{a}_{b}'
    source = STEP/'output_cycle_dense_sparse'
    poses = json.loads((source/'camera_poses.json').read_text())['cameras']
    cached_stats = json.loads((source/'stats.json').read_text())
    assert cached_stats['thresholds'] == dict(epipolar_px=4., min_parallax_deg=2., max_ray_gap_m=1.)
    matches = load_npz(source/'matches'/f'{pair}_matches.npz')
    tri = load_npz(source/'triangulated'/f'{pair}_triangulated.npz')
    assert matches['ratio_threshold'].item() == 0.7
    images, features = [], []
    for side, camera in zip(('a', 'b'), (a, b)):
        pid = poses[camera]['pano_id']
        assert matches[f'pano_id_{side}'].item() == pid
        feat = load_npz(source/'features'/f'{camera}_{pid}.npz')
        image = cv2.imread(str(STEP.parent.parent/'data/fotos_barranco'/f'{pid}.jpg'))
        if image is None:
            raise FileNotFoundError(pid)
        assert list(image.shape[1::-1]) == feat['image_wh'].tolist()
        np.testing.assert_array_equal(matches[f'uv_{side}'], tri[f'pixel_{side}'])
        np.testing.assert_array_equal(matches[f'uv_{side}'], feat['keypoints_uv'][matches[f'indices_{side}']])
        images.append(image); features.append(feat)
    count = len(matches['indices_a'])
    stages = [('lowe', np.ones(count, bool)), ('epipolar', tri['passed_epipolar']),
              ('depth', tri['passed_depth']), ('parallax', tri['passed_parallax']),
              ('final', tri['final_points'])]
    for (_, prev), (_, current) in zip(stages, stages[1:]):
        assert not np.any(current & ~prev)
    output = STEP/'output_pair_diagnostic'/pair
    output.mkdir(parents=True, exist_ok=True)
    for number, side, image, feat in zip((1, 2), ('A', 'B'), images, features):
        uv = feat['keypoints_uv']
        save(output/f'{number:02d}_keypoints_{side}.jpg', points_image(image, uv, f'{side}: {len(uv)} PR+SIFT keypoints'))
    coverage_stats = {}
    for number, (stage, mask) in enumerate(stages, 3):
        ua, ub = matches['uv_a'][mask], matches['uv_b'][mask]
        label = f'{pair} - {stage}: {len(ua)} matches'
        save(output/f'{number:02d}_matches_{stage}.jpg', draw_matches(*images, ua, ub, label))
        if len(ua) > 150:
            # Deterministic uniform sampling of accepted-match indices, display only.
            subset = np.linspace(0, len(ua)-1, 150, dtype=int)
            save(output/f'{number:02d}_matches_{stage}_sample150.jpg',
                 draw_matches(*images, ua[subset], ub[subset], label+' (150 shown)'))
        coverage_stats[stage] = {}
        for side, image, uv in zip(('A', 'B'), images, (ua, ub)):
            save(output/f'coverage_{stage}_{side}.jpg', points_image(image, uv, label+f' - {side}'))
            coverage_stats[stage][side] = coverage(uv, image)
    stats = cached_stats['pairs'][pair].copy()
    stats.update(pair=pair, matches_input=count, passed_lowe=count,
                 passed_epipolar=int(tri['passed_epipolar'].sum()),
                 passed_positive_depth=int(tri['passed_depth'].sum()),
                 passed_parallax=int(tri['passed_parallax'].sum()),
                 passed_ray_gap=int(tri['passed_ray_gap'].sum()),
                 final_points=int(tri['final_points'].sum()),
                 keypoints_A=len(features[0]['keypoints_uv']), keypoints_B=len(features[1]['keypoints_uv']),
                 coverage=coverage_stats, median_population=cached_stats.get('median_population'),
                 matches_input_definition='Stage 5 input = accepted Lowe 0.7 matches; no rematching',
                 visual_sampling='At most 150 uniformly spaced match indices; statistics use all matches')
    (output/'diagnostic_stats.json').write_text(json.dumps(stats, indent=2, allow_nan=False)+'\n')
    print(pair, ' -> '.join(str(stats[k]) for k in ('passed_lowe', 'passed_epipolar', 'passed_positive_depth', 'passed_parallax', 'passed_ray_gap')))
    print(output)


if __name__ == '__main__':
    main()
