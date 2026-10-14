"""Angular longitude/elevation view; identical conventions to the step21 viewer.

The photo is independent of extrusion height. Compute it once, then project
the few prism edges separately (in the browser or here for image exports).
"""
import cv2
import numpy as np

PROJECTION_VERSION = 'angular-enu-v1'


def camera_to_enu(heading_deg, pitch_deg, roll_deg):
    """Rz(-heading) @ [east,-up,north] @ Rx(pitch) @ Rz(roll)."""
    h, p, r = np.deg2rad([heading_deg, pitch_deg, roll_deg])
    def rz(a):
        c, s = np.cos(a), np.sin(a)
        return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    cp, sp = np.cos(p), np.sin(p)
    rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    base = np.array([[1., 0., 0.], [0., 0., 1.], [0., -1., 0.]])
    return rz(-h) @ base @ rx @ rz(r)


def wrap(angle):
    return (angle + np.pi) % (2 * np.pi) - np.pi


def view_spec(polygon, camera_xy, size=(960, 640)):
    camera = np.asarray(camera_xy)
    target = np.asarray(polygon.centroid.coords[0])
    vertices = np.asarray(polygon.exterior.coords)[:, :2] - camera
    yaw = np.arctan2(*(target-camera))
    bearings = np.arctan2(vertices[:, 0], vertices[:, 1])
    fov = min(2*np.pi, max(np.deg2rad(40), 2*np.max(np.abs(wrap(bearings-yaw)))+np.deg2rad(16)))
    return dict(version=PROJECTION_VERSION, width=size[0], height=size[1], yaw_rad=float(yaw),
        fov_rad=float(fov), bottom_rad=float(np.deg2rad(-35)), top_rad=float(np.deg2rad(85)),
        camera_height_m=2.5, camera_xy=camera.tolist(), vertices_relative_xy=vertices.tolist(),
        coordinate_system='EPSG:32718; east,north metres; flat ground; z up')


def project_image(image, metadata, spec):
    w, h = spec['width'], spec['height']
    lon, lat = np.meshgrid(spec['yaw_rad']+((np.arange(w)+.5)/w-.5)*spec['fov_rad'],
        spec['top_rad']-(np.arange(h)+.5)/h*(spec['top_rad']-spec['bottom_rad']))
    world = np.stack([np.cos(lat)*np.sin(lon), np.cos(lat)*np.cos(lon), np.sin(lat)], axis=-1)
    local = world @ camera_to_enu(metadata['heading_deg'], metadata['pitch_deg'], metadata['roll_deg'])
    ih, iw = image.shape[:2]
    sx = ((np.arctan2(local[..., 0], local[..., 2])+np.pi)*iw/(2*np.pi)-.5) % iw
    sy = (np.pi/2-np.arctan2(-local[..., 1], np.hypot(local[..., 0], local[..., 2])))*ih/np.pi-.5
    return cv2.remap(image, sx.astype('float32'), np.clip(sy, 0, ih-1).astype('float32'),
                     cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)


def project_points(relative_xyz, spec):
    points = np.asarray(relative_xyz, dtype=float)
    yaw = np.arctan2(points[:, 0], points[:, 1])
    pitch = np.arctan2(points[:, 2]-spec['camera_height_m'], np.hypot(points[:, 0], points[:, 1]))
    return np.column_stack([(wrap(yaw-spec['yaw_rad'])/spec['fov_rad']+.5)*spec['width'],
        (spec['top_rad']-pitch)/(spec['top_rad']-spec['bottom_rad'])*spec['height']])


def draw_prism(image, spec, height):
    result = image.copy()
    w, h = spec['width'], spec['height']
    def line(a, b, color):
        uv = project_points(np.linspace(a, b, 80), spec)
        for p, q in zip(uv[:-1], uv[1:]):
            if np.linalg.norm(p-q) < max(w, h)/2:
                ok, p0, p1 = cv2.clipLine((0, 0, w, h), tuple(np.rint(p).astype(int)), tuple(np.rint(q).astype(int)))
                if ok:
                    cv2.line(result, p0, p1, color, 2, cv2.LINE_AA)
    vertices = spec['vertices_relative_xy']
    for a, b in zip(vertices[:-1], vertices[1:]):
        line([*a, 0], [*b, 0], (0, 255, 255))
        line([*a, height], [*b, height], (255, 80, 255))
        line([*a, 0], [*a, height], (255, 180, 40))
    return result
