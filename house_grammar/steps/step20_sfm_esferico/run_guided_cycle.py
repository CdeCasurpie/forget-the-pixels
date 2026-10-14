"""Apply the validated guided search to the saved dense-sparse candidate list."""
import argparse
import contextlib
import hashlib
import json
import os
import shutil
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from guided_pair import guided_search
from diagnose_pair import STEP, load_npz
from geometry_stage4 import erp_pixel_to_unit_ray, rays_to_world
from run_stage5 import main as triangulate, plot_outputs
from cycle_pipeline import write_ply


def json_save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    temp.replace(path)


def npz_save(path, data):
    temp = path.with_suffix('.tmp')
    with temp.open('wb') as file:
        np.savez_compressed(file, **data)
    temp.replace(path)


def identities(data):
    mask = data['final_points']
    return set(zip(data['indices_a'][mask].tolist(), data['indices_b'][mask].tolist()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    start = time.time()
    source = STEP/'output_cycle_dense_sparse'
    output = STEP/'output_cycle_guided'
    selection = json.loads((STEP/'selected_cycle.json').read_text())
    assert selection == json.loads((source/'selected_cycle.json').read_text())
    candidates = json.loads((source/'pair_candidates.json').read_text())
    pairs = [p for p in candidates if p['within_distance']]
    document = json.loads((source/'camera_poses.json').read_text())
    poses = document['cameras']
    names = [f'P{i}' for i in range(len(selection['panorama_ids']))]
    assert len(names) == 30
    old = json.loads((source/'stats.json').read_text())
    original = json.loads((STEP/'output_cycle/stats.json').read_text())
    assert old['offsets'] == [1, 2, 3] and old['max_pair_distance_m'] == 35
    thresholds = argparse.Namespace(epipolar_px=4., min_parallax_deg=2., max_ray_gap_m=1.)
    manifest = dict(guide_epipolar_deg=1.5, lowe_ratio=0.7, thresholds=vars(thresholds),
                    input_hashes={str(p.relative_to(STEP)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in [STEP/'selected_cycle.json', source/'pair_candidates.json', source/'camera_poses.json']})
    for name, pid in zip(names, selection['panorama_ids']):
        assert poses[name]['pano_id'] == pid
        feature_path = source/'features'/f'{name}_{pid}.npz'
        manifest['input_hashes'][str(feature_path.relative_to(STEP))] = hashlib.sha256(feature_path.read_bytes()).hexdigest()
    output.mkdir(exist_ok=args.resume)
    if args.resume:
        assert json.loads((output/'manifest.json').read_text()) == manifest, 'Resume inputs/config changed'
    else:
        json_save(output/'manifest.json', manifest)
    for folder in ('features', 'matches', 'geometry', 'triangulated', 'cache'):
        (output/folder).mkdir(exist_ok=True)
    for name in ('pair_candidates.json', 'camera_poses.json', 'selected_cycle.json'):
        shutil.copy2(source/name, output/name)
    shutil.copy2(source/'camera_poses.json', output/'geometry/camera_poses.json')
    log = (STEP/'guided_cycle_run.log').open('a', buffering=1)
    def progress(text):
        text = time.strftime('%Y-%m-%d %H:%M:%S')+' '+text
        print(text, flush=True); print(text, file=log, flush=True)
    features, camera_rays, world_rays = {}, {}, {}
    for name in names:
        pid = poses[name]['pano_id']; path = source/'features'/f'{name}_{pid}.npz'
        dest = output/'features'/path.name
        if not dest.exists(): os.link(path, dest)
        features[name] = load_npz(path)
        assert features[name]['n'].item() == 6
        cache = output/'cache'/f'{name}_rays.npz'
        if args.resume and cache.exists():
            rays = load_npz(cache)
        else:
            uv = features[name]['keypoints_uv']
            local = erp_pixel_to_unit_ray(uv[:, 0], uv[:, 1], *features[name]['image_wh'])
            rays = dict(camera=local, world=rays_to_world(local, np.array(poses[name]['R_camera_to_world'])))
            npz_save(cache, rays)
        camera_rays[name], world_rays[name] = rays['camera'], rays['world']
    progress(f'Cached features and rays: {len(names)} cameras; pairs: {len(pairs)}')
    pair_stats, failures, results = {}, {}, {}
    for number, info in enumerate(pairs, 1):
        a, b = info['camera_a'], info['camera_b']; key = f'{a}_{b}'
        progress(f'[{number}/{len(pairs)}] {key}')
        match_path = output/'matches'/f'{key}_matches.npz'
        geometry_path = output/'geometry'/f'{key}_rays.npz'
        tri_path = output/'triangulated'/f'{key}_triangulated.npz'
        stats_path = output/'triangulated'/f'{key}_stats.json'
        try:
            if args.resume and tri_path.exists() and stats_path.exists():
                pair_stats[key] = json.loads(stats_path.read_text()); results[key] = load_npz(tri_path)
                progress(f'{key}: reused completed triangulation')
                continue
            ca, cb = np.array(poses[a]['position']), np.array(poses[b]['position'])
            if args.resume and match_path.exists():
                matches = load_npz(match_path)
            else:
                matches = guided_search(features[a], features[b], ca, cb, world_rays[a], world_rays[b], 1.5)
                for side, name in [('a', a), ('b', b)]:
                    matches[f'uv_{side}'] = features[name]['keypoints_uv'][matches[f'indices_{side}']]
                    matches[f'pano_id_{side}'] = np.array(poses[name]['pano_id'])
                matches['guide_epipolar_residual_deg'] = np.degrees(matches['epipolar_residual_before_final_filter'])
                matches['ratio_threshold'] = np.array(0.7)
                npz_save(match_path, matches)
            if not (args.resume and geometry_path.exists()):
                rays = matches.copy()
                for side, name in [('a', a), ('b', b)]:
                    idx = matches[f'indices_{side}']
                    rays.update({f'pixel_{side}': matches[f'uv_{side}'], f'ray_camera_{side}': camera_rays[name][idx],
                                 f'ray_world_{side}': world_rays[name][idx],
                                 f'camera_center_{side}': np.broadcast_to(poses[name]['position'], (len(idx), 3)).copy()})
                npz_save(geometry_path, rays)
            with contextlib.redirect_stdout(log):
                r, s = triangulate(thresholds, [(a, b)], output/'geometry', output/'triangulated', plots=False)
            result = r[key]
            baseline = load_npz(source/'triangulated'/f'{key}_triangulated.npz')
            before, after = identities(baseline), identities(result)
            counts = matches['candidate_counts']
            record = dict(**info, **s[key], keypoints_A=len(features[a]['keypoints_uv']),
                          keypoints_B=len(features[b]['keypoints_uv']), guided_descriptor_matches=len(matches['indices_a']),
                          baseline_final_points=len(before), guided_final_points=len(after),
                          common_matches=len(before & after), new_guided_matches=len(after-before), lost_baseline_matches=len(before-after))
            record.update({f'candidate_count_p{p}': float(np.percentile(counts, p)) for p in (25, 50, 75, 90)})
            record['candidate_count_max'] = int(counts.max()) if len(counts) else 0
            json_save(stats_path, record)
            pair_stats[key] = record; results[key] = result
            progress(f'{key}: {len(matches["indices_a"])} matches -> {len(after)} final points')
        except Exception as error:
            failures[key] = f'{type(error).__name__}: {error}'
            progress(f'ERROR {key}: {failures[key]}')
        finally:
            json_save(output/'progress.json', dict(completed=list(pair_stats), failures=failures))
    xyz = np.concatenate([r['points_xyz'] for r in results.values()]) if results else np.empty((0, 3))
    rgb = np.concatenate([r['colors_rgb'] for r in results.values()]) if results else np.empty((0, 3), np.uint8)
    write_ply(output/'reconstruction.ply', xyz, rgb)
    plot_outputs(results, poses, output/'triangulated')
    for src, dst in [('triangulated_points_3d', 'reconstruction_3d'), ('triangulated_top', 'reconstruction_top'), ('triangulated_side', 'reconstruction_side')]:
        shutil.copy2(output/'triangulated'/f'{src}.png', output/f'{dst}.png')
    labels = list(pair_stats); x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(24, 7))
    ax.bar(x-.2, [pair_stats[k]['baseline_final_points'] for k in labels], .4, label='Global')
    ax.bar(x+.2, [pair_stats[k]['final_points'] for k in labels], .4, label='Guided')
    ax.set_xticks(x, labels, rotation=90, fontsize=7); ax.set_ylabel('Final points'); ax.legend()
    fig.tight_layout(); fig.savefig(output/'points_per_pair.png', dpi=150); plt.close(fig)
    elapsed = time.time()-start
    timing_path = output/'elapsed_seconds.json'
    previous_elapsed = json.loads(timing_path.read_text()) if timing_path.exists() else 0
    json_save(timing_path, previous_elapsed+elapsed)
    summary = dict(num_cameras=len(names), num_pairs=len(pair_stats), num_candidate_pairs=len(candidates), failures=failures,
                   total_descriptor_matches=sum(s['guided_descriptor_matches'] for s in pair_stats.values()),
                   total_passed_epipolar=sum(s['passed_epipolar'] for s in pair_stats.values()),
                   total_passed_depth=sum(s['passed_positive_depth'] for s in pair_stats.values()),
                   total_passed_parallax=sum(s['passed_parallax'] for s in pair_stats.values()), total_final_points=len(xyz),
                   pairs_with_zero_matches=[k for k,s in pair_stats.items() if not s['guided_descriptor_matches']],
                   pairs_with_zero_final_points=[k for k,s in pair_stats.items() if not s['final_points']],
                   total_common=sum(s['common_matches'] for s in pair_stats.values()),
                   total_new=sum(s['new_guided_matches'] for s in pair_stats.values()),
                   total_lost=sum(s['lost_baseline_matches'] for s in pair_stats.values()),
                   pairs=pair_stats, elapsed_seconds=previous_elapsed+elapsed, configuration=manifest,
                   comparison={label: dict(pairs=n, points=points, increase=len(xyz)-points,
                                           increase_percent=100*(len(xyz)-points)/points if points else None)
                               for label,n,points in [('original',len(original['pairs']),original['total_points']),
                                                      ('dense_sparse_global',old['num_pairs_processed'],old['total_final_points'])]})
    json_save(output/'stats.json', summary)
    progress(f'Finished: {len(pair_stats)} pairs; {len(xyz)} points; {elapsed/60:.1f} min')
    log.close()
    if failures: raise RuntimeError(f'{len(failures)} pairs failed; inspect progress.json and resume')


if __name__ == '__main__':
    main()
