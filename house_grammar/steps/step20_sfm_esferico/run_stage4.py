"""Prepare known poses and every Stage 2 match ray, without filtering."""

import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from geometry_stage4 import (CONVENTION, camera_to_enu, position_enu,
                             erp_pixel_to_unit_ray, rays_to_world)

STEP = Path(__file__).resolve().parent
ROOT = STEP.parent.parent


def plot_cameras(poses, output):
    colors = {'forward': 'tab:blue', 'right': 'tab:orange', 'up': 'tab:green'}
    length = 3.0  # Display length in meters, not vector magnitude.
    fig, ax = plt.subplots(figsize=(8, 10))
    fig3 = plt.figure(figsize=(9, 9))
    ax3 = fig3.add_subplot(111, projection='3d')
    for i, (name, pose) in enumerate(poses.items()):
        pos = np.array(pose['position'])
        ax.scatter(*pos[:2], c='black')
        ax.annotate(name, pos[:2], xytext=(6, 6), textcoords='offset points')
        ax3.scatter(*pos, c='black')
        ax3.text(*pos, name)
        for axis, color in colors.items():
            vector = np.array(pose[axis]) * length
            if axis != 'up':
                ax.quiver(*pos[:2], *vector[:2], angles='xy', scale_units='xy',
                          scale=1, color=color, label=axis if i == 0 else None)
            ax3.quiver(*pos, *vector, color=color, label=axis if i == 0 else None)
    positions = np.array([p['position'] for p in poses.values()])
    low, high = positions.min(axis=0)-4, positions.max(axis=0)+4
    ax.set(xlabel='East (m)', ylabel='North (m)', xlim=(low[0], high[0]),
           ylim=(low[1], high[1]), title='Camera ENU poses — arrows: 3 m')
    ax.set_aspect('equal'); ax.grid(); ax.legend()
    ax3.set(xlabel='East (m)', ylabel='North (m)', zlabel='Up (m)',
            xlim=(low[0], high[0]), ylim=(low[1], high[1]), zlim=(low[2], high[2]),
            title='Camera ENU poses — arrows: 3 m')
    ax3.set_box_aspect(high-low)
    ax3.legend()
    fig.savefig(output/'camera_geometry.png', dpi=160, bbox_inches='tight')
    fig3.savefig(output/'camera_geometry_3d.png', dpi=160, bbox_inches='tight')
    plt.close('all')


def main(entries=None, pairs=None, match_dir=None, output=None, progress=print):
    output = output or STEP/'output_stage4'
    output.mkdir(exist_ok=True)
    entries = entries if entries is not None else json.loads((STEP/'output_stage1/summary.json').read_text())
    entries = {e['camera']: e for e in entries}
    metadata = json.loads((ROOT/'data/poses_barranco/metadata.json').read_text())['panoramas']
    origin_name = next(iter(entries))
    origin = metadata[entries[origin_name]['pano_id']]
    poses = {}
    for name in entries:
        progress(f'Pose {name}')
        pid = entries[name]['pano_id']
        meta = metadata[pid]
        image = cv2.imread(str(ROOT/'data/fotos_barranco'/f'{pid}.jpg'))
        if image is None:
            raise ValueError(f'Unreadable panorama: {pid}')
        height, width = image.shape[:2]
        del image
        assert [width, height] == entries[name]['image_wh']
        rotation = camera_to_enu(meta['heading_deg'], meta['pitch_deg'], meta['roll_deg'])
        np.testing.assert_allclose(rotation.T @ rotation, np.eye(3), atol=1e-12)
        np.testing.assert_allclose(np.linalg.det(rotation), 1, atol=1e-12)
        poses[name] = {
            'pano_id': pid, 'image_wh': [width, height],
            **{key: meta[key] for key in ('lat', 'lon', 'heading_deg', 'pitch_deg', 'roll_deg')},
            'position': position_enu(meta['lat'], meta['lon'], origin['lat'], origin['lon']).tolist(),
            'R_camera_to_world': rotation.tolist(),
            'forward': rotation[:, 2].tolist(), 'right': rotation[:, 0].tolist(),
            'up': (-rotation[:, 1]).tolist(),
        }
        print(name, json.dumps(poses[name]), flush=True)
    distances = {}
    for a, b in zip(list(entries)[:-1], list(entries)[1:]):
        distances[f'{a}_{b}'] = float(np.linalg.norm(np.array(poses[b]['position'])-poses[a]['position']))
    print('Distances (m):', distances)
    counts = {}
    for a, b in (pairs if pairs is not None else [('C0', 'C1'), ('C1', 'C2'), ('C2', 'C3'), ('C0', 'C2'), ('C1', 'C3')]):
        pair = f'{a}_{b}'
        with np.load((match_dir or STEP/'output_stage2')/f'{pair}_matches.npz', allow_pickle=False) as data:
            saved = {key: data[key].copy() for key in data.files}
        for side, name in [('a', a), ('b', b)]:
            pose = poses[name]
            assert saved[f'pano_id_{side}'].item() == pose['pano_id']
            uv = saved[f'uv_{side}']
            rays = erp_pixel_to_unit_ray(uv[:, 0], uv[:, 1], *pose['image_wh'])
            world = rays_to_world(rays, np.array(pose['R_camera_to_world']))
            np.testing.assert_allclose(np.linalg.norm(rays, axis=1), 1, atol=1e-6)
            np.testing.assert_allclose(np.linalg.norm(world, axis=1), 1, atol=1e-6)
            saved.update({f'pixel_{side}': uv, f'ray_camera_{side}': rays,
                          f'ray_world_{side}': world,
                          f'camera_center_{side}': np.broadcast_to(pose['position'], rays.shape).copy()})
        assert len(saved['pixel_a']) == len(saved['pixel_b'])
        counts[pair] = len(saved['pixel_a'])
        np.savez_compressed(output/f'{pair}_rays.npz', **saved)
        print(f'{pair}: {counts[pair]} matches, {2*counts[pair]} rays')
    (output/'camera_poses.json').write_text(json.dumps({
        'conventions': CONVENTION, 'origin_camera': origin_name, 'cameras': poses,
        'consecutive_distances_m': distances, 'match_counts': counts,
    }, indent=2)+'\n')
    plot_cameras(poses, output)


if __name__ == '__main__':
    main()
