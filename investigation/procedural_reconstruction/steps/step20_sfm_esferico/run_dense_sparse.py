"""Same selected cycle and poses, circular offsets 1/2/3, distance cap only."""
import argparse
import json
import shutil
from pathlib import Path

import cv2
import numpy as np

from cycle_pipeline import STEP, ROOT, valid_features, write_ply
from pr_sift import extract
from run_stage2 import main as matching
from run_stage4 import main as geometry
from run_stage5 import main as triangulation, plot_outputs


def candidate_pairs(names, poses, offsets, max_distance):
    seen, candidates = set(), []
    # Offset-first preserves consecutive directed pairs when deduplicating.
    for offset in sorted(set(offsets)):
        for i, a in enumerate(names):
            b = names[(i+offset) % len(names)]
            key = frozenset((a, b))
            if a == b or key in seen:
                continue
            seen.add(key)
            distance = float(np.linalg.norm(np.array(poses[a]['position'])-poses[b]['position']))
            candidates.append(dict(camera_a=a, camera_b=b, cycle_step_distance=offset,
                                   camera_distance_m=distance, within_distance=distance <= max_distance))
    return candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offsets', type=int, nargs='+', default=[1, 2, 3])
    parser.add_argument('--max-pair-distance-m', type=float, default=35)
    parser.add_argument('--resume', action='store_true', help='Resume this experiment using completed matching outputs')
    args = parser.parse_args()
    if any(x < 1 for x in args.offsets) or not np.isfinite(args.max_pair_distance_m) or args.max_pair_distance_m < 0:
        parser.error('Offsets must be positive; distance must be finite and nonnegative')
    previous = STEP/'output_cycle'
    selection = json.loads((STEP/'selected_cycle.json').read_text())
    old = json.loads((previous/'stats.json').read_text())
    old_selection = json.loads((previous/'selected_cycle.json').read_text())
    assert selection['panorama_ids'] == old_selection['panorama_ids'], 'Previous output belongs to another selection'
    poses_document = json.loads((previous/'camera_poses.json').read_text())
    poses = poses_document['cameras']
    names = [f'P{i}' for i in range(len(selection['panorama_ids']))]
    for name, pid in zip(names, selection['panorama_ids']):
        assert poses[name]['pano_id'] == pid
    output = STEP/'output_cycle_dense_sparse'
    output.mkdir(exist_ok=args.resume)
    if args.resume and (output/'selected_cycle.json').exists():
        assert json.loads((output/'selected_cycle.json').read_text()) == selection
    for folder in ('features', 'matches', 'geometry', 'triangulated'):
        (output/folder).mkdir(exist_ok=args.resume)
    shutil.copy2(STEP/'selected_cycle.json', output/'selected_cycle.json')
    candidates = candidate_pairs(names, poses, args.offsets, args.max_pair_distance_m)
    (output/'pair_candidates.json').write_text(json.dumps(candidates, indent=2))
    entries = []
    reused = 0
    for name in names:
        pose = poses[name]; pid = pose['pano_id']
        image = cv2.imread(str(ROOT/'data/fotos_barranco'/f'{pid}.jpg'))
        if image is None:
            raise FileNotFoundError(pid)
        wh = [image.shape[1], image.shape[0]]
        assert wh == pose['image_wh']
        entry = dict(camera=name, pano_id=pid, image_wh=wh); entries.append(entry)
        cache = previous/'features'/f'{name}_{pid}.npz'
        dest = output/'features'/cache.name
        if valid_features(cache, pid, wh):
            if not dest.exists() or not dest.samefile(cache):
                shutil.copy2(cache, dest)
            reused += 1
        else:
            data, _ = extract(image, n=6)
            np.savez_compressed(dest, **data, pano_id=np.array(pid))
    (output/'features/summary.json').write_text(json.dumps(entries, indent=2))
    print(f'Features reused: {reused}/{len(names)}', flush=True)
    eligible = [p for p in candidates if p['within_distance']]
    successes, failures, matching_stats = [], {}, []
    for p in eligible:
        a, b = p['camera_a'], p['camera_b']; key = f'{a}_{b}'
        try:
            saved = output/'matches'/f'{key}_matches.npz'
            if args.resume and saved.exists():
                with np.load(saved) as matches:
                    assert matches['pano_id_a'].item() == poses[a]['pano_id']
                    assert matches['pano_id_b'].item() == poses[b]['pano_id']
                    assert matches['ratio_threshold'].item() == 0.7
                    count = len(matches['indices_a'])
                matching_stats.append(dict(pair=key, matches_after_ratio=count, reused=True))
            else:
                matching_stats.extend(matching(entries, [(a, b)], output/'features', output/'matches', debug_images=False))
            successes.append((a, b))
        except Exception as error:
            failures[key] = dict(**p, error=f'{type(error).__name__}: {error}', failed_stage='matching')
            print(key, failures[key], flush=True)
    (output/'matches/stats.json').write_text(json.dumps(matching_stats, indent=2))
    geometry(entries, successes, output/'matches', output/'geometry')
    actual = json.loads((output/'geometry/camera_poses.json').read_text())['cameras']
    # Exact unchanged poses are a prerequisite for this controlled comparison.
    assert actual == poses, 'Poses differ from the previous experiment'
    shutil.copy2(previous/'camera_poses.json', output/'camera_poses.json')
    thresholds = argparse.Namespace(epipolar_px=4., min_parallax_deg=2., max_ray_gap_m=1.)
    results, pair_stats = {}, {}
    info = {f"{p['camera_a']}_{p['camera_b']}": p for p in eligible}
    for a, b in successes:
        key = f'{a}_{b}'
        try:
            r, s = triangulation(thresholds, [(a, b)], output/'geometry', output/'triangulated', plots=False)
            results.update(r)
            pair_stats[key] = dict(**info[key], **s[key])
        except Exception as error:
            failures[key] = dict(**info[key], error=f'{type(error).__name__}: {error}', failed_stage='triangulation')
            print(key, failures[key], flush=True)
    xyz = np.concatenate([r['points_xyz'] for r in results.values()]) if results else np.empty((0, 3))
    rgb = np.concatenate([r['colors_rgb'] for r in results.values()]) if results else np.empty((0, 3), np.uint8)
    write_ply(output/'reconstruction.ply', xyz, rgb)
    plot_outputs(results, poses, output/'triangulated')
    for src, dst in [('triangulated_points_3d', 'reconstruction_3d'), ('triangulated_top', 'reconstruction_top'), ('triangulated_side', 'reconstruction_side')]:
        shutil.copy2(output/'triangulated'/f'{src}.png', output/f'{dst}.png')
    total = len(xyz); before = old['total_points']; increase = total-before
    stats = dict(num_cameras=len(names), num_original_pairs=len(old['pairs']),
                 num_candidate_pairs=len(candidates), num_pairs_within_distance=len(eligible),
                 num_pairs_processed=len(pair_stats), num_pairs_attempted=len(eligible),
                 num_pairs_with_matches=sum(s['matches_after_ratio'] > 0 for s in matching_stats),
                 num_pairs_with_final_points=sum(s['final_points'] > 0 for s in pair_stats.values()),
                 total_input_matches=sum(s['matches_after_ratio'] for s in matching_stats),
                 total_final_points=total, features_reused=reused, thresholds=vars(thresholds),
                 max_pair_distance_m=args.max_pair_distance_m, offsets=args.offsets,
                 pairs=pair_stats, failures=failures,
                 median_population=old.get('median_population'),
                 comparison=dict(previous_pairs=len(old['pairs']), previous_points=before,
                                 increase_points=increase, increase_percent=100*increase/before if before else None))
    for path in (output/'stats.json', output/'triangulated/stats.json'):
        path.write_text(json.dumps(stats, indent=2, allow_nan=False))
    print('ANTES:', len(old['pairs']), 'pares;', before, 'puntos', flush=True)
    print('AHORA:', len(pair_stats), 'pares;', total, 'puntos', flush=True)
    print('INCREMENTO:', stats['comparison'], flush=True)


if __name__ == '__main__':
    main()
