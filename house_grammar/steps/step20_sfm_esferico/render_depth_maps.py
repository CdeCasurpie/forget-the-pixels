"""Visual depth densification from saved sparse ENU points, not dense stereo.

All nonzero finite directions are projectable in a 360 camera; visibility is
unknown. A minimum-distance pixel z-buffer only resolves same-pixel collisions.
Confidence describes sparse support, NOT visibility or calibrated accuracy.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np
from scipy.interpolate import griddata
from scipy.spatial import cKDTree, QhullError

from geometry_stage4 import erp_pixel_to_unit_ray

STEP = Path(__file__).resolve().parent


def read_points(path):
    """Read the ASCII XYZ RGB PLY exported by the existing cycle pipeline."""
    with path.open() as file:
        if file.readline().strip() != 'ply' or file.readline().strip() != 'format ascii 1.0':
            raise ValueError('Expected pipeline ASCII PLY')
        count = None
        for line in file:
            if line.startswith('element vertex '): count = int(line.split()[-1])
            if line.strip() == 'end_header': break
        if count is None: raise ValueError('Missing vertex count')
        points = np.array([[float(x) for x in file.readline().split()[:3]] for _ in range(count)], dtype=float).reshape(-1, 3)
    return points


def project(points, pose, width, height, max_depth):
    """Row-vector world->camera: (X-C) @ R_camera_to_world.

    Camera axes right/down/forward. Inverse of Stage 4 pixel-center mapping.
    Distance is radial, including points behind the forward axis.
    """
    camera = (points-np.array(pose['position'])) @ np.array(pose['R_camera_to_world'])
    depth = np.linalg.norm(camera, axis=1)
    valid = np.isfinite(camera).all(axis=1) & (depth > 1e-6) & (depth <= max_depth)
    camera, depth = camera[valid], depth[valid]
    longitude = np.arctan2(camera[:, 0], camera[:, 2])
    latitude = np.arctan2(-camera[:, 1], np.hypot(camera[:, 0], camera[:, 2]))
    u = (longitude+np.pi)*width/(2*np.pi)-0.5
    v = (np.pi/2-latitude)*height/np.pi-0.5
    return np.stack([u, v], axis=1), depth


def sparse_map(uv, depth, width, height):
    image = np.full((height, width), np.inf, dtype=np.float32)
    x = np.floor(uv[:, 0]+0.5).astype(int) % width
    y = np.clip(np.floor(uv[:, 1]+0.5).astype(int), 0, height-1)
    np.minimum.at(image, (y, x), depth)
    image[~np.isfinite(image)] = np.nan
    return image


def interpolate(sparse, method, downscale, support_deg):
    height, width = sparse.shape
    y, x = np.where(np.isfinite(sparse))
    if not len(x):
        return np.full_like(sparse, np.nan), np.zeros_like(sparse), 'no samples'
    samples = np.column_stack([x, y]).astype(float)
    inverse = 1/sparse[y, x].astype(float)
    # Linear mode evaluates the full ERP; hybrid uses local spherical IDW at
    # reduced resolution, avoiding global triangles bridging large gaps.
    rw, rh = (width, height) if method == 'linear' else (max(1, width//downscale), max(1, height//downscale))
    gx, gy = np.meshgrid((np.arange(rw)+.5)*width/rw-.5, (np.arange(rh)+.5)*height/rh-.5)
    queries = np.column_stack([gx.ravel(), gy.ravel()])
    rays = erp_pixel_to_unit_ray(samples[:, 0], samples[:, 1], width, height)
    tree = cKDTree(rays)
    values = np.empty(len(queries)); confidence = np.empty(len(queries))
    note = 'local spherical k=8 inverse-depth IDW, reduced resolution; no image-edge guidance'
    # Chunk queries to keep linear/full-resolution runs bounded in memory.
    for start in range(0, len(queries), 100000):
        q = queries[start:start+100000]
        qrays = erp_pixel_to_unit_ray(q[:, 0], q[:, 1], width, height)
        distance, index = tree.query(qrays, k=min(8, len(samples)))
        if distance.ndim == 1: distance, index = distance[:, None], index[:, None]
        weights = 1/np.maximum(distance, 1e-8)**2
        weights /= weights.sum(axis=1, keepdims=True)
        local = inverse[index]
        mean = (weights*local).sum(axis=1)
        deviation = np.sqrt((weights*(local-mean[:, None])**2).sum(axis=1))
        angle = 2*np.arcsin(np.clip(distance[:, 0]/2, 0, 1))
        conf = np.exp(-(angle/np.deg2rad(support_deg))**2)/(1+(deviation/mean)**2)
        values[start:start+len(q)] = mean
        confidence[start:start+len(q)] = conf
    if method == 'linear':
        # Periodic copies join the longitude seam; nearest fills outside hull.
        extended = np.concatenate([samples+[-width, 0], samples, samples+[width, 0]])
        inv = np.tile(inverse, 3)
        note = 'ERP periodic griddata linear inverse-depth; nearest fill outside hull'
        try:
            linear = griddata(extended, inv, queries, method='linear')
        except QhullError:
            linear = np.full(len(queries), np.nan)
            note += '; degenerate samples: nearest fallback'
        missing = ~np.isfinite(linear)
        if missing.any(): linear[missing] = griddata(extended, inv, queries[missing], method='nearest')
        confidence[missing] *= 0.25
        values = linear
    inv_image = values.reshape(rh, rw).astype(np.float32)
    conf_image = confidence.reshape(rh, rw).astype(np.float32)
    if (rh, rw) != (height, width):
        inv_image = cv2.resize(inv_image, (width, height), interpolation=cv2.INTER_LINEAR)
        conf_image = cv2.resize(conf_image, (width, height), interpolation=cv2.INTER_LINEAR)
    dense = 1/inv_image
    # Preserve actual raster samples, not a smoothed version of them.
    dense[y, x] = sparse[y, x]; conf_image[y, x] = 1
    return dense, conf_image, note


def depth_color(depth, low, high):
    valid = np.isfinite(depth)
    values = np.zeros(depth.shape, np.uint8)
    values[valid] = np.clip((depth[valid]-low)/(high-low)*255, 0, 255).astype(np.uint8)
    rgb = cv2.applyColorMap(values, cv2.COLORMAP_TURBO)
    rgb[~valid] = 0
    return rgb


def write_image(path, image):
    if not cv2.imwrite(str(path), image): raise OSError(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=STEP/'output_cycle_guided')
    parser.add_argument('--output-dir', type=Path, default=STEP/'output_depth_maps')
    parser.add_argument('--method', choices=['linear', 'hybrid'], default='hybrid')
    parser.add_argument('--downscale', type=int, default=8)
    parser.add_argument('--max-depth', type=float, default=150.)
    parser.add_argument('--min-confidence', type=float, default=.15)
    parser.add_argument('--support-deg', type=float, default=5.)
    parser.add_argument('--panorama-id', help='P0..P29 label or actual pano_id')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--resume', action='store_true'); mode.add_argument('--overwrite', action='store_true')
    args = parser.parse_args(); start = time.time()
    if args.downscale < 1 or not (np.isfinite(args.max_depth) and args.max_depth > 0) or not 0 <= args.min_confidence <= 1 or not 0 < args.support_deg <= 180:
        parser.error('Invalid numerical parameter')
    points = read_points(args.input_dir/'reconstruction.ply')
    poses = json.loads((args.input_dir/'camera_poses.json').read_text())['cameras']
    selection = json.loads((args.input_dir/'selected_cycle.json').read_text())
    assert set(selection['panorama_ids']) == {p['pano_id'] for p in poses.values()}
    source_stats = json.loads((args.input_dir/'stats.json').read_text())
    assert len(points) == source_stats['total_final_points']
    chosen = {k:p for k,p in poses.items() if not args.panorama_id or args.panorama_id in (k,p['pano_id'])}
    if not chosen: parser.error('Panorama not found')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    config = dict(method=args.method, downscale=args.downscale, max_depth=args.max_depth,
                  min_confidence=args.min_confidence, support_deg=args.support_deg,
                  inputs={name: hashlib.sha256((args.input_dir/name).read_bytes()).hexdigest()
                          for name in ('reconstruction.ply','camera_poses.json','selected_cycle.json')})
    print('Assumption: projectable != visible; no occlusion model. Confidence = sparse support only.', flush=True)
    records = []; processed_now = 0
    files = ['depth_sparse.npy','depth_dense.npy','confidence.npy','depth_sparse_vis.png','depth_dense_vis.png',
             'confidence_vis.png','overlay_points_depth.png','overlay_dense_depth.png']
    for name, pose in chosen.items():
        out = args.output_dir/name
        if args.resume and (out/'metadata.json').exists():
            previous = json.loads((out/'metadata.json').read_text())
            if previous['configuration'] != config: raise ValueError(f'{name}: resume configuration mismatch')
            if all((out/f).exists() for f in files+[f'summary_{name}.png']):
                records.append(previous); print(name, 'reused', flush=True); continue
        if out.exists() and any(out.iterdir()) and not (args.overwrite or args.resume):
            raise FileExistsError(f'{out}: use --resume or --overwrite')
        out.mkdir(exist_ok=True)
        if (out/'metadata.json').exists(): (out/'metadata.json').unlink()
        t0 = time.time()
        image = cv2.imread(str(STEP.parent.parent/'data/fotos_barranco'/f"{pose['pano_id']}.jpg"))
        if image is None: raise FileNotFoundError(pose['pano_id'])
        height, width = image.shape[:2]; assert [width,height] == pose['image_wh']
        uv, depths = project(points, pose, width, height, args.max_depth)
        sparse = sparse_map(uv, depths, width, height)
        dense, confidence, note = interpolate(sparse, args.method, args.downscale, args.support_deg)
        np.save(out/'depth_sparse.npy', sparse); np.save(out/'depth_dense.npy', dense); np.save(out/'confidence.npy', confidence)
        # Fixed metric scale across all cameras. Depth PNGs are visualizations,
        # not metric encodings; metric radial distance lives in float32 NPY.
        sparse_vis = depth_color(sparse, 0, args.max_depth)
        # Dilated markers are display-only; sparse NPY retains single pixels.
        y,x = np.where(np.isfinite(sparse)); overlay = image.copy()
        for px,py in zip(x,y):
            cv2.circle(overlay,(int(px),int(py)),3,tuple(int(c) for c in sparse_vis[py,px]),-1)
        sparse_vis = cv2.dilate(sparse_vis, np.ones((3,3),np.uint8))
        dense_vis = depth_color(dense, 0, args.max_depth)
        trusted = confidence >= args.min_confidence
        dense_vis[~trusted] = 0
        alpha = np.where(trusted, .65*confidence, 0)[...,None]
        overlay_dense = np.clip(image*(1-alpha)+dense_vis*alpha,0,255).astype(np.uint8)
        conf_vis = cv2.applyColorMap((confidence*255).astype(np.uint8),cv2.COLORMAP_VIRIDIS)
        conf_vis[~trusted] = 0
        for filename,data in [('depth_sparse_vis.png',sparse_vis),('depth_dense_vis.png',dense_vis),
                              ('confidence_vis.png',conf_vis),('overlay_points_depth.png',overlay),('overlay_dense_depth.png',overlay_dense)]:
            write_image(out/filename,data)
        tiles=[]
        for label,data in [('Original ERP',image),('Projected sparse radial depth',overlay),
                           (f'{args.method} depth: 0-{args.max_depth:g} m',dense_vis),('Support confidence: 0-1',conf_vis)]:
            tile=cv2.resize(data,(800,400)); tile=cv2.copyMakeBorder(tile,32,0,0,0,cv2.BORDER_CONSTANT)
            cv2.putText(tile,label,(10,23),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1);tiles.append(tile)
        write_image(out/f'summary_{name}.png',np.vstack([np.hstack(tiles[:2]),np.hstack(tiles[2:])]))
        values=sparse[np.isfinite(sparse)]
        record=dict(camera=name,panorama_id=pose['pano_id'],resolution=[width,height],
                    projected_points=len(depths),occupied_sparse_pixels=len(values),
                    min_depth=float(values.min()) if len(values) else None,
                    median_depth=float(np.median(values)) if len(values) else None,
                    max_depth=float(values.max()) if len(values) else None,
                    method=args.method,interpolation=note,configuration=config,
                    confidence_fraction=float(trusted.mean()),seconds=time.time()-t0,
                    units='meters, Euclidean radial distance; NPY float32 at original resolution',
                    visibility='Not tested: all finite nonzero projectable points within max_depth; pixel collision minimum only',
                    confidence='Angular proximity (5 deg default decay scale) and local inverse-depth agreement; not visibility probability',
                    visual_scale_m=[0,args.max_depth],duplicates='Minimum radial distance per original ERP pixel')
        (out/'metadata.json').write_text(json.dumps(record,indent=2)+'\n'); records.append(record); processed_now+=1
        print(f'{name}: {len(depths)} projected; {len(values)} sparse pixels; {100*trusted.mean():.1f}% supported',flush=True)
    total=sum(r['projected_points'] for r in records)
    summary=dict(panoramas_processed=len(records),processed_this_run=processed_now,projected_points_total=total,
                 average_projected_points=total/len(records),total_seconds=time.time()-start,
                 source_points=len(points),configuration=config,panoramas=records)
    (args.output_dir/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(f'Done: {len(records)} panoramas; {total} projections; mean {total/len(records):.1f}; {time.time()-start:.1f}s',flush=True)


if __name__ == '__main__':
    main()
