"""Plot the ERP center ray against forward, without changing camera poses."""

import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from geometry_stage4 import erp_pixel_to_unit_ray, rays_to_world


def main():
    step = Path(__file__).resolve().parent
    output = step / 'output_stage4'
    poses = json.loads((output / 'camera_poses.json').read_text())['cameras']
    fig, ax = plt.subplots(figsize=(9, 10))
    positions = np.array([p['position'] for p in poses.values()])
    ax.plot(positions[:, 0], positions[:, 1], 'k.--', label='Selected order C0 -> C3')
    report, tiles = {}, []
    for i, (name, pose) in enumerate(poses.items()):
        w, h = pose['image_wh']
        # Even-sized images have their exact center between four pixels.
        uv = np.array([(w-1)/2, (h-1)/2])
        local = erp_pixel_to_unit_ray(*uv, w, h)
        world = rays_to_world(local, np.array(pose['R_camera_to_world']))
        forward = np.array(pose['forward'])
        angle = np.degrees(np.arctan2(np.linalg.norm(np.cross(world, forward)),
                                     np.dot(world, forward)))
        np.testing.assert_allclose(world, forward, atol=1e-12)
        pos = np.array(pose['position'])
        # Same scale: dashed center ray overlays the solid forward vector.
        endpoint = pos + 3 * world
        ax.quiver(*pos[:2], *(3*forward[:2]), angles='xy', scale_units='xy',
                  scale=1, color='tab:blue', label='Forward (3 m)' if i == 0 else None)
        ax.plot([pos[0], endpoint[0]], [pos[1], endpoint[1]], '--',
                color='magenta', marker='x', label='ERP center ray (3 m)' if i == 0 else None)
        ax.annotate(name, pos[:2], xytext=(8, 8), textcoords='offset points')
        report[name] = {'center_uv': uv.tolist(), 'ray_camera': local.tolist(),
                        'ray_world': world.tolist(), 'angle_to_forward_deg': float(angle)}
        print(name, json.dumps(report[name]))
        image = cv2.imread(str(step.parent.parent / 'data/fotos_barranco' / f"{pose['pano_id']}.jpg"))
        if image is None:
            raise ValueError(f'Unreadable image: {name}')
        tile = cv2.resize(image, (1024, 512))
        cv2.drawMarker(tile, (512, 256), (255, 0, 255), cv2.MARKER_CROSS, 40, 2)
        cv2.putText(tile, f'{name}: ERP center', (12, 28), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (255, 0, 255), 2)
        tiles.append(tile)
    ax.set(xlabel='East (m)', ylabel='North (m)',
           title='Center ERP ray vs forward (overlap is by convention)')
    ax.set_aspect('equal'); ax.margins(0.2); ax.grid(); ax.legend()
    fig.savefig(output / 'camera_center_check.png', dpi=160, bbox_inches='tight')
    plt.close(fig)
    if not cv2.imwrite(str(output / 'erp_centers.jpg'), np.vstack(tiles)):
        raise OSError('Could not save ERP center debug image')
    (output / 'camera_center_check.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
