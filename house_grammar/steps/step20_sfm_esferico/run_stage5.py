"""Stage 5 only. Masks are cumulative, aligned to all Stage 2 input matches.

points_xyz/colors_rgb contain final points only; final_indices maps them to
the input-length diagnostic arrays. Untriangulated diagnostics contain NaN.
Medians: residual on all defined inputs; gap/parallax on valid epipolar-pass
triangulations BEFORE depth/parallax/gap filtering. Histograms use same sets.
"""

import argparse
import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from triangulation_stage5 import spherical_epipolar_residual, closest_points

EPIPOLAR_PX = 4.0
MIN_PARALLAX_DEG = 2.0
MAX_RAY_GAP_M = 1.0
PAIRS = [('C0', 'C1'), ('C1', 'C2'), ('C2', 'C3'), ('C0', 'C2'), ('C1', 'C3')]
STEP = Path(__file__).resolve().parent


def distribution(values):
    values = values[np.isfinite(values)]
    return {f'p{p}': float(np.percentile(values, p)) if len(values) else None
            for p in (0, 25, 50, 75, 90, 95, 100)}


def plot_outputs(results, cameras, output):
    for key, filename, label in [
        ('epipolar_residual_deg', 'epipolar_residuals.png', 'Epipolar residual (deg), all defined inputs'),
        ('ray_gap_m', 'ray_gap_histogram.png', 'Ray gap (m), valid epipolar-pass triangulations'),
        ('parallax_deg', 'parallax_histogram.png', 'Parallax (deg), valid epipolar-pass triangulations'),
    ]:
        rows = max(1, (len(results)+1)//2)
        fig, axes = plt.subplots(rows, 2, figsize=(12, 3.5*rows), squeeze=False)
        for ax, (pair, data) in zip(axes.flat, results.items()):
            values = data[key]
            values = values[np.isfinite(values)]
            ax.hist(values, bins=40)
            ax.set(title=f'{pair}: n={len(values)}', xlabel=label, ylabel='Count')
        for ax in list(axes.flat)[len(results):]:
            ax.axis('off')
        fig.tight_layout(); fig.savefig(output/filename, dpi=150); plt.close(fig)
    for name, dimensions in [('triangulated_points_3d', (0, 1, 2)),
                             ('triangulated_top', (0, 1)), ('triangulated_side', (1, 2))]:
        fig = plt.figure(figsize=(11, 9))
        ax = fig.add_subplot(111, projection='3d' if len(dimensions) == 3 else None)
        all_positions = []
        for pair, data in results.items():
            points = data['points_xyz']
            all_positions.extend(points)
            ax.scatter(*(points[:, d] for d in dimensions), c=data['colors_rgb']/255., s=5)
        for camera, pose in cameras.items():
            pos = np.array(pose['position'])
            all_positions.append(pos)
            xyz = [pos[d] for d in dimensions]
            ax.scatter(*xyz, c='red', marker='^', s=65)
            ax.text(*xyz, camera)
        labels = ['East (m)', 'North (m)', 'Up (m)']
        ax.set_xlabel(labels[dimensions[0]]); ax.set_ylabel(labels[dimensions[1]])
        if len(dimensions) == 3:
            ax.set_zlabel(labels[2])
            extent = np.ptp(np.array(all_positions), axis=0)
            ax.set_box_aspect(np.maximum(extent, 1))
        else:
            ax.set_aspect('equal', adjustable='box')
        ax.set_title('Final pairwise points (duplicates retained)')
        ax.grid(); fig.tight_layout()
        fig.savefig(output/f'{name}.png', dpi=160); plt.close(fig)


def main(args=None, pairs=None, geometry_dir=None, output=None, progress=print, plots=True):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--epipolar-px', type=float, default=EPIPOLAR_PX)
    parser.add_argument('--min-parallax-deg', type=float, default=MIN_PARALLAX_DEG)
    parser.add_argument('--max-ray-gap-m', type=float, default=MAX_RAY_GAP_M)
    args = args if args is not None else parser.parse_args()
    if not all(np.isfinite(x) and x >= 0 for x in vars(args).values()):
        parser.error('Thresholds must be finite and nonnegative')
    output = output or STEP/'output_stage5'; output.mkdir(exist_ok=True)
    geometry_dir = geometry_dir or STEP/'output_stage4'
    cameras = json.loads((geometry_dir/'camera_poses.json').read_text())['cameras']
    results, stats = {}, {}
    for a, b in (pairs if pairs is not None else PAIRS):
        progress(f'Triangulating {a} -> {b}')
        pair = f'{a}_{b}'
        with np.load(geometry_dir/f'{pair}_rays.npz') as source:
            data = {k: source[k].copy() for k in source.files}
        ca, cb = data['camera_center_a'], data['camera_center_b']
        da, db = data['ray_world_a'], data['ray_world_b']
        np.testing.assert_allclose(np.linalg.norm(da, axis=1), 1, atol=1e-6)
        np.testing.assert_allclose(np.linalg.norm(db, axis=1), 1, atol=1e-6)
        residual = spherical_epipolar_residual(ca, cb, da, db)
        # One-sided residual is measured in B; use B's ERP resolution.
        threshold = 2*np.pi/max(cameras[b]['image_wh'])*args.epipolar_px
        epipolar = np.isfinite(residual) & (residual <= threshold)
        n = len(residual)
        xyz = np.full((n, 3), np.nan)
        s, t, gap, parallax = [np.full(n, np.nan) for _ in range(4)]
        valid = np.zeros(n, dtype=bool)
        xyz[epipolar], s[epipolar], t[epipolar], gap[epipolar], parallax[epipolar], valid[epipolar] = closest_points(
            ca[epipolar], cb[epipolar], da[epipolar], db[epipolar])
        depth = epipolar & valid & (s > 0) & (t > 0)
        passed_parallax = depth & (parallax >= args.min_parallax_deg)
        passed_gap = passed_parallax & (gap <= args.max_ray_gap_m)
        final = passed_gap & np.isfinite(xyz).all(axis=1)
        pid = cameras[a]['pano_id']
        image = cv2.imread(str(STEP.parent.parent/'data/fotos_barranco'/f'{pid}.jpg'))
        if image is None:
            raise ValueError(f'Unreadable image: {pid}')
        uv = np.rint(data['pixel_a'][final]).astype(int)
        colors = image[np.clip(uv[:, 1], 0, image.shape[0]-1), uv[:, 0] % image.shape[1], ::-1]
        result = dict(points_xyz=xyz[final], colors_rgb=colors,
                      pixel_a=data['pixel_a'], pixel_b=data['pixel_b'],
                      indices_a=data['indices_a'], indices_b=data['indices_b'],
                      epipolar_residual_rad=residual, epipolar_residual_deg=np.degrees(residual),
                      parallax_deg=parallax, ray_gap_m=gap, depth_a=s, depth_b=t,
                      candidate_points_xyz=xyz, matches_input=np.arange(n),
                      passed_epipolar=epipolar, valid_triangulation=valid,
                      passed_depth=depth, passed_parallax=passed_parallax, passed_ray_gap=passed_gap,
                      final_points=final, final_indices=np.flatnonzero(final),
                      epipolar_threshold_rad=np.array(threshold))
        np.savez_compressed(output/f'{pair}_triangulated.npz', **result)
        results[pair] = result
        residual_dist = distribution(np.degrees(residual))
        gap_dist, parallax_dist = distribution(gap[valid]), distribution(parallax[valid])
        stats[pair] = dict(matches_input=n, passed_epipolar=int(epipolar.sum()),
                           passed_positive_depth=int(depth.sum()), passed_parallax=int(passed_parallax.sum()),
                           passed_ray_gap=int(passed_gap.sum()), final_points=int(final.sum()),
                           median_epipolar_residual_deg=residual_dist['p50'],
                           median_parallax_deg=parallax_dist['p50'], median_ray_gap_m=gap_dist['p50'],
                           residual_percentiles_deg=residual_dist, ray_gap_percentiles_m=gap_dist,
                           parallax_percentiles_deg=parallax_dist,
                           undefined_residuals=int((~np.isfinite(residual)).sum()),
                           epipolar_threshold_deg=float(np.degrees(threshold)))
        print(pair, json.dumps(stats[pair]), flush=True)
    (output/'stats.json').write_text(json.dumps({
        'thresholds': vars(args), 'mask_semantics': 'Cumulative, input-match aligned',
        'median_population': 'Residual: all defined inputs. Parallax/gap: valid epipolar-pass triangulations before further filters.',
        'npz_layout': 'points_xyz/colors_rgb: final only; final_indices maps to all other per-match arrays. NaN means not triangulated/undefined.',
        'pairs': stats, 'total_points': sum(s['final_points'] for s in stats.values()),
    }, indent=2, allow_nan=False)+'\n')
    if plots:
        plot_outputs(results, cameras, output)
    return results, stats


if __name__ == '__main__':
    main()
