"""Small orchestrator reusing Stages 1, 2, 4 and 5 unchanged mathematically."""

import json
import shutil
from pathlib import Path

import cv2
import numpy as np

from pr_sift import extract
from run_stage2 import main as matching
from run_stage4 import main as geometry
from run_stage5 import main as triangulation

STEP = Path(__file__).resolve().parent
ROOT = STEP.parent.parent


def cycle_pairs(ids):
    return list(zip(ids, ids[1:] + ids[:1])) if ids else []


def is_cycle(ids, metadata):
    return (len(ids) >= 4 and len(set(ids)) == len(ids)
            and all(b in metadata[a]['neighbor_ids'] for a, b in cycle_pairs(ids)))


def write_ply(path, xyz, rgb):
    """ASCII XYZ RGB, including a valid zero-vertex file for an empty cloud."""
    with path.open('w') as file:
        file.write(f'ply\nformat ascii 1.0\nelement vertex {len(xyz)}\n'
                   'property double x\nproperty double y\nproperty double z\n'
                   'property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n')
        for p, c in zip(xyz, rgb):
            file.write(' '.join([*(f'{v:.9f}' for v in p), *(str(int(v)) for v in c)])+'\n')


def valid_features(path, pid, wh):
    try:
        with np.load(path, allow_pickle=False) as data:
            uv, desc = data['keypoints_uv'], data['descriptors']
            return (data['pano_id'].item() == pid and data['n'].item() == 6
                    and np.array_equal(data['image_wh'], wh)
                    and uv.shape == (len(desc), 2) and desc.shape == (len(uv), 128)
                    and np.isfinite(uv).all() and np.isfinite(desc).all())
    except (OSError, ValueError, KeyError):
        return False


def run_cycle(selection_path, args, progress=print):
    selection = json.loads(selection_path.read_text())
    metadata = json.loads((ROOT/'data/poses_barranco/metadata.json').read_text())['panoramas']
    ids = selection['panorama_ids']
    if not is_cycle(ids, metadata) or selection['pairs'] != [list(p) for p in cycle_pairs(ids)]:
        raise ValueError('Invalid cycle: need >=4 distinct nodes and directed neighbor links including closure')
    # Preflight all input images before spending time extracting features.
    entries = []
    for i, pid in enumerate(ids):
        image = cv2.imread(str(ROOT/'data/fotos_barranco'/f'{pid}.jpg'))
        if image is None:
            raise FileNotFoundError(f'Imagen ausente o ilegible: {pid}')
        entries.append({'camera': f'P{i}', 'pano_id': pid, 'image_wh': [image.shape[1], image.shape[0]]})
    del image
    output = STEP/'output_cycle'; output.mkdir(exist_ok=True)
    # Archive the preceding run so stale clouds never masquerade as this run.
    if (output/'selected_cycle.json').exists():
        from datetime import datetime
        previous = STEP/('output_cycle_previous_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        output.rename(previous)
        output.mkdir()
    else:
        previous = None
    shutil.copy2(selection_path, output/'selected_cycle.json')
    for name in ('features', 'matches', 'geometry', 'triangulated'):
        (output/name).mkdir(exist_ok=True)
    (output/'stats.json').write_text(json.dumps({'status': 'running', 'thresholds': vars(args)}, indent=2))
    pairs = cycle_pairs([e['camera'] for e in entries])
    for i, entry in enumerate(entries):
        pid = entry['pano_id']; progress(f'[1/5] PR+SIFT {i+1}/{len(entries)}: {pid}')
        destination = output/'features'/f"{entry['camera']}_{pid}.npz"
        candidates = list((STEP/'output_stage1').glob(f'*_{pid}.npz'))
        if previous:
            candidates += list((previous/'features').glob(f'*_{pid}.npz'))
        cached = next((p for p in candidates if valid_features(p, pid, entry['image_wh'])), None)
        if cached:
            shutil.copy2(cached, destination)
        else:
            image = cv2.imread(str(ROOT/'data/fotos_barranco'/f'{pid}.jpg'))
            data, _ = extract(image, n=6)
            np.savez_compressed(destination, **data, pano_id=np.array(pid))
        progress(f'[1/5] Features listas: {pid}')
    (output/'features/summary.json').write_text(json.dumps(entries, indent=2))
    matching(entries, pairs, output/'features', output/'matches',
             lambda text: progress('[2/5] '+text))
    geometry(entries, pairs, output/'matches', output/'geometry',
             lambda text: progress('[3/5] '+text))
    shutil.copy2(output/'geometry/camera_poses.json', output/'camera_poses.json')
    triangulation(args, pairs, output/'geometry', output/'triangulated',
                  lambda text: progress('[4/5] '+text))
    progress('[5/5] Exportando PLY...')
    xyz, rgb = [], []
    for a, b in pairs:
        with np.load(output/'triangulated'/f'{a}_{b}_triangulated.npz') as data:
            xyz.append(data['points_xyz']); rgb.append(data['colors_rgb'])
    write_ply(output/'reconstruction.ply', np.concatenate(xyz), np.concatenate(rgb))
    poses = json.loads((output/'camera_poses.json').read_text())['cameras']
    camera_points, camera_colors = [], []
    for pose in poses.values():
        pos = np.array(pose['position'])
        camera_points.append(pos); camera_colors.append([255, 255, 255])
        for axis, color in [('forward', [0, 100, 255]), ('right', [255, 140, 0])]:
            for length in np.linspace(0, 3, 31):
                camera_points.append(pos + length*np.array(pose[axis])); camera_colors.append(color)
    write_ply(output/'cameras.ply', camera_points, camera_colors)
    for source, dest in [('triangulated_points_3d', 'reconstruction_3d'),
                         ('triangulated_top', 'reconstruction_top'), ('triangulated_side', 'reconstruction_side')]:
        shutil.copy2(output/'triangulated'/f'{source}.png', output/f'{dest}.png')
    stats = json.loads((output/'triangulated/stats.json').read_text())
    stats.update(status='completed', panorama_ids=ids, pairs_selected=selection['pairs'])
    (output/'stats.json').write_text(json.dumps(stats, indent=2))
    progress(f"Terminado: {stats['total_points']} puntos; output_cycle/reconstruction.ply")
