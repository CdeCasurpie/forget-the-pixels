"""Vistas angulares de la MISMA malla exportada, con rayos de angular-enu-v1.

Color base y luz simple; no es un render PBR ni reconstruye oclusores de la foto.
Open3D se importa solo al renderizar. La geometría de trabajo es Z-up local.
"""
from pathlib import Path
import json

import cv2
import numpy as np

from packages.barranco_imaging.angular import draw_prism, project_points


def camera_rays(spec, origin_xy):
    if spec['version'] != 'angular-enu-v1':
        raise ValueError('Versión de cámara no soportada.')
    w, h = spec['width'], spec['height']
    lon, lat = np.meshgrid(spec['yaw_rad'] + ((np.arange(w)+.5)/w-.5)*spec['fov_rad'],
        spec['top_rad']-(np.arange(h)+.5)/h*(spec['top_rad']-spec['bottom_rad']))
    directions = np.stack([np.cos(lat)*np.sin(lon), np.cos(lat)*np.cos(lon), np.sin(lat)], axis=-1)
    position = np.array([*(np.asarray(spec['camera_xy'])-origin_xy), spec['camera_height_m']])
    return np.concatenate([np.broadcast_to(position, directions.shape), directions], axis=-1).astype('float32')


def angular_views(mesh, evidence, origin_xy, inputs, output):
    import open3d as o3d
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    scene = o3d.t.geometry.RaycastingScene()
    scene.add_triangles(o3d.core.Tensor(np.asarray(mesh.vertices, dtype='float32')),
                        o3d.core.Tensor(np.asarray(mesh.faces, dtype='uint32')))
    tri = mesh.vertices[mesh.faces]
    normals = np.cross(tri[:,1]-tri[:,0], tri[:,2]-tri[:,0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
    light = np.array([-.4, -.6, .7]); light /= np.linalg.norm(light)
    colors = np.array([m['color'] for m in mesh.materials])[mesh.face_materials]
    colors = np.clip(colors*(.55+.45*np.abs(normals@light))[:,None]*255, 0, 255).astype('uint8')
    paths = []
    for i, e in enumerate(evidence, 1):
        rays = camera_rays(e['projection'], np.asarray(origin_xy))
        answer = scene.cast_rays(o3d.core.Tensor(rays))
        hit = np.isfinite(answer['t_hit'].numpy())
        face_ids = answer['primitive_ids'].numpy()
        photo = cv2.imread(str(Path(inputs)/e['attachment']))
        if photo is None or photo.shape[:2] != hit.shape:
            raise ValueError('Foto y cámara no coinciden en dimensiones.')
        render = np.full_like(photo, (236, 239, 242))
        render[hit] = colors[face_ids[hit]][:, ::-1]
        overlay = photo.copy()
        overlay[hit] = (.60*photo[hit]+.40*render[hit]).astype('uint8')
        contours, _ = cv2.findContours(hit.astype('uint8'), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, (0, 220, 255), 1)
        tiles = []
        for title, img in [('FOTO', photo), ('MALLA · color base', render), ('SUPERPOSICION', overlay)]:
            tile = cv2.copyMakeBorder(img, 32, 0, 0, 0, cv2.BORDER_CONSTANT, value=(35,35,35))
            cv2.putText(tile, f'{i:02d} {title}', (10,22), cv2.FONT_HERSHEY_SIMPLEX, .55, (255,255,255), 1)
            tiles.append(tile)
        name = f'{i:02d}_comparison.jpg'
        cv2.imwrite(str(output/name), np.concatenate(tiles, axis=1))
        cv2.imwrite(str(output/f'{i:02d}_render.png'), render)
        paths.append(name)
    (output/'render.json').write_text(json.dumps(dict(
        projection='angular-enu-v1', source='MeshData exported to building.glb',
        appearance='base_color; opaque first hit; no PBR/transparency',
        camera_height='metadata (currently assumed 2.5 m)', comparisons=paths), indent=2)+'\n')
    return paths


def prepare_images(evidence, inputs, height, parcel, fronts, origin_xy):
    """Identificación auxiliar y plano métrico, sin reemplazar fotos limpias."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    inputs = Path(inputs)
    for i, e in enumerate(evidence, 1):
        photo = cv2.imread(str(inputs/e['attachment']))
        if photo is None:
            raise ValueError('No se pudo abrir una foto del paquete.')
        marked = draw_prism(photo, e['projection'], height)
        cv2.putText(marked, 'LOTE: base humana de referencia, NO silueta observada',
                    (8,22), cv2.FONT_HERSHEY_SIMPLEX, .45, (0,0,0), 3)
        cv2.putText(marked, 'LOTE: base humana de referencia, NO silueta observada',
                    (8,22), cv2.FONT_HERSHEY_SIMPLEX, .45, (255,255,255), 1)
        cv2.imwrite(str(inputs/f'target_{i:02d}.jpg'), marked)
    fig, ax = plt.subplots(figsize=(9,9))
    ring = np.array([*parcel, parcel[0]])
    ax.fill(ring[:,0], ring[:,1], alpha=.15)
    for i, (a,b) in enumerate(zip(ring[:-1],ring[1:])):
        ax.plot([a[0],b[0]], [a[1],b[1]], color='tab:red' if i in fronts else 'gray', linewidth=2)
        midpoint = (a+b)/2
        ax.text(*midpoint, f'e{i} · {np.linalg.norm(b-a):.2f}m', fontsize=8)
        ax.annotate('', xy=a+.6*(b-a), xytext=a+.4*(b-a), arrowprops={'arrowstyle':'->'})
    for i,e in enumerate(evidence,1):
        camera = np.asarray(e['projection']['camera_xy'])-origin_xy
        ax.scatter(*camera, marker='^'); ax.text(*camera, f'cam{i}')
    ax.set_aspect('equal'); ax.set_xlabel('X este (m)'); ax.set_ylabel('Y norte (m)')
    ax.set_title('Parcela local · frentes rojos · flechas = dirección u · Z hacia arriba')
    fig.tight_layout(); fig.savefig(inputs/'plan.png', dpi=130); plt.close(fig)


def projected_wall_chart(walls, evidence, origin_xy):
    result = {}
    for e in evidence:
        shift = np.asarray(origin_xy)-np.asarray(e['projection']['camera_xy'])
        entries = []
        for w in walls:
            a,b = np.asarray(w['vertex_a']),np.asarray(w['vertex_b'])
            low,high = w['base_z'],w['base_z']+w['height_m']
            # A few corners aid correspondence; angular edges are curves, not straight pixel lines.
            corners = np.array([[*(a+shift),low], [*(b+shift),low], [*(b+shift),high], [*(a+shift),high]])
            entries.append(dict(wall_id=w['id'], corners_px=project_points(corners,e['projection']).tolist()))
        result[e['id']] = entries
    return result
