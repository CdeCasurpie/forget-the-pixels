"""Single-pair experiment: restrict descriptor search by known-pose epipolar band."""
import argparse
import json
import shutil

import cv2
import numpy as np

from diagnose_pair import STEP, load_npz, save, points_image, coverage
from geometry_stage4 import erp_pixel_to_unit_ray, rays_to_world
from triangulation_stage5 import spherical_epipolar_residual
from run_stage2 import draw_matches
from run_stage5 import main as triangulate
from cycle_pipeline import write_ply


def guided_search(fa, fb, ca, cb, wa, wb, guide_deg):
    """Exact L2 k=2 within a strict angular band; no final-filter threshold here."""
    matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    counts = np.zeros(len(wa), dtype=np.int32)
    accepted = []
    for i, ray in enumerate(wa):
        residual = spherical_epipolar_residual(ca, cb, np.broadcast_to(ray, wb.shape), wb)
        candidates = np.flatnonzero(np.isfinite(residual) & (residual < np.deg2rad(guide_deg)))
        counts[i] = len(candidates)
        if len(candidates) < 2:
            continue
        first, second = matcher.knnMatch(fa['descriptors'][i:i+1], fb['descriptors'][candidates], k=2)[0]
        if first.distance < 0.7*second.distance:
            j = int(candidates[first.trainIdx])
            accepted.append((i, j, first.distance, first.distance/second.distance, residual[j]))
    values = np.array(accepted, dtype=np.float64).reshape(-1, 5)
    return dict(indices_a=values[:, 0].astype(np.int32), indices_b=values[:, 1].astype(np.int32),
                descriptor_distance=values[:, 2], lowe_ratio=values[:, 3],
                epipolar_residual_before_final_filter=values[:, 4], candidate_counts=counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--guide-epipolar-deg', type=float, default=1.5)
    args = parser.parse_args()
    if not 0 < args.guide_epipolar_deg <= 90:
        parser.error('Guide angle must be in (0, 90]')
    pair = 'P16_P17'
    source = STEP/'output_cycle_dense_sparse'
    output = STEP/'output_guided_matching'/pair
    output.mkdir(parents=True, exist_ok=True)
    poses = json.loads((source/'camera_poses.json').read_text())['cameras']
    features, images, world, local = [], [], [], []
    for name in ('P16', 'P17'):
        pose = poses[name]; pid = pose['pano_id']
        feat = load_npz(source/'features'/f'{name}_{pid}.npz')
        image = cv2.imread(str(STEP.parent.parent/'data/fotos_barranco'/f'{pid}.jpg'))
        if image is None: raise FileNotFoundError(pid)
        assert feat['image_wh'].tolist() == [image.shape[1], image.shape[0]]
        uv = feat['keypoints_uv']
        ray = erp_pixel_to_unit_ray(uv[:, 0], uv[:, 1], *feat['image_wh'])
        local.append(ray); world.append(rays_to_world(ray, np.array(pose['R_camera_to_world'])))
        features.append(feat); images.append(image)
    ca, cb = [np.array(poses[name]['position']) for name in ('P16', 'P17')]
    matches = guided_search(*features, ca, cb, *world, args.guide_epipolar_deg)
    counts = matches['candidate_counts']
    for side, name, feat in zip(('a', 'b'), ('P16', 'P17'), features):
        matches[f'uv_{side}'] = feat['keypoints_uv'][matches[f'indices_{side}']]
        matches[f'pano_id_{side}'] = np.array(poses[name]['pano_id'])
    matches['ratio_threshold'] = np.array(0.7)
    matches['guide_epipolar_deg'] = np.array(args.guide_epipolar_deg)
    np.savez_compressed(output/'guided_matches.npz', **matches)
    geometry = output/'geometry'; geometry.mkdir(exist_ok=True)
    shutil.copy2(source/'camera_poses.json', geometry/'camera_poses.json')
    rays = matches.copy()
    for k, side, center in zip((0, 1), ('a', 'b'), (ca, cb)):
        idx = matches[f'indices_{side}']
        rays.update({f'pixel_{side}': matches[f'uv_{side}'],
                     f'ray_camera_{side}': local[k][idx], f'ray_world_{side}': world[k][idx],
                     f'camera_center_{side}': np.broadcast_to(center, (len(idx), 3)).copy()})
    np.savez_compressed(geometry/f'{pair}_rays.npz', **rays)
    results, stats = triangulate(argparse.Namespace(epipolar_px=4., min_parallax_deg=2., max_ray_gap_m=1.),
                                 [('P16', 'P17')], geometry, output/'triangulated', plots=False)
    guided = results[pair]
    baseline = load_npz(source/'triangulated'/f'{pair}_triangulated.npz')
    baseline_stats = json.loads((source/'stats.json').read_text())['pairs'][pair]
    for label, data in [('baseline', baseline), ('guided', guided)]:
        write_ply(output/f'{label}_points.ply', data['points_xyz'], data['colors_rgb'])
    for stage, mask in [('matches', np.ones(len(matches['indices_a']), bool)),
                        ('epipolar', guided['passed_epipolar']), ('final', guided['final_points'])]:
        ua, ub = matches['uv_a'][mask], matches['uv_b'][mask]
        label = f'Guided {stage}: {len(ua)} matches'
        save(output/f'guided_{stage}.jpg', draw_matches(*images, ua, ub, label))
        if len(ua) > 150:
            ids = np.linspace(0, len(ua)-1, 150, dtype=int)
            save(output/f'guided_{stage}_sample150.jpg', draw_matches(*images, ua[ids], ub[ids], label+' (150 shown)'))
        for side, image, uv in zip(('A', 'B'), images, (ua, ub)):
            save(output/f'guided_coverage_{stage}_{side}.jpg', points_image(image, uv, label))
    def final_pairs(data):
        mask = data['final_points']
        return set(zip(data['indices_a'][mask].tolist(), data['indices_b'][mask].tolist()))
    old, new = final_pairs(baseline), final_pairs(guided)
    common, gained, lost = old & new, new-old, old-new
    overlay = images[0].copy()
    # Exact (index_A,index_B) identity; a changed partner counts as lost + new.
    for pairs, color in [(lost, (0, 0, 255)), (gained, (0, 255, 0)), (common, (0, 255, 255))]:
        for i, _ in sorted(pairs):
            point = tuple(np.rint(features[0]['keypoints_uv'][i]).astype(int))
            cv2.circle(overlay, point, 5, color, 2, cv2.LINE_AA)
    text = f'Yellow common: {len(common)} | Green new: {len(gained)} | Red lost: {len(lost)}'
    cv2.putText(overlay, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 5)
    cv2.putText(overlay, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    save(output/'baseline_vs_guided_A.jpg', overlay)
    spatial = {}
    for label, data, mask in [('baseline_lowe', baseline, np.ones(len(baseline['pixel_a']), bool)),
                               ('baseline_final', baseline, baseline['final_points']),
                               ('guided_matches', guided, np.ones(len(guided['pixel_a']), bool)),
                               ('guided_final', guided, guided['final_points'])]:
        spatial[label] = {side: coverage(data[f'pixel_{side.lower()}'][mask], image)
                          for side, image in zip(('A', 'B'), images)}
    summary = dict(pair=pair, keypoints_A=len(features[0]['keypoints_uv']), keypoints_B=len(features[1]['keypoints_uv']),
                   guide_epipolar_deg=args.guide_epipolar_deg, lowe_ratio=0.7,
                   candidate_distribution={f'p{p}': float(np.percentile(counts, p)) for p in (25, 50, 75, 90, 100)},
                   queries_with_less_than_two_candidates=int((counts < 2).sum()),
                   baseline=baseline_stats, guided=stats[pair], coverage=spatial,
                   final_common=len(common), final_new=len(gained), final_lost=len(lost),
                   identity='Exact original (index_A,index_B) pair; changed partner counts as both lost and new',
                   mutual_implemented=False)
    (output/'guided_stats.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
