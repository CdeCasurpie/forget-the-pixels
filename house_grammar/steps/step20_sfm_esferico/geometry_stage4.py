"""Spherical rays and assumed metadata conventions, without pose refinement."""

import numpy as np


CONVENTION = {
    'world': 'ENU: x=east, y=north, z=up; meters',
    'camera': 'Right-handed: +x=right, +y=down, +z=forward; up=-y',
    'heading': 'Degrees clockwise from north towards east',
    'pitch': 'Positive raises forward above horizon; active Rx(pitch)',
    'roll': 'Positive tips right towards down; active Rz(roll) about forward',
    'order': 'R_camera_to_ENU = Rz(-heading) @ B @ Rx(pitch) @ Rz(roll)',
    'B': 'Zero-angle columns: east, -up, north; acts on column vectors',
    'erp': 'Pixel centers +0.5; center faces +z, increasing u towards +x, top towards -y',
    'status': 'Assumed interpretation for manual review, not calibrated or optimized',
    'height': 'WGS84 ECEF uses h=0 for all cameras; after ENU projection force up=0',
}


def rotation_x(angle):
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rotation_z(angle):
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def camera_to_enu(heading_deg, pitch_deg, roll_deg):
    """See CONVENTION: signs/order deliberately explicit and easily editable."""
    h, p, r = np.deg2rad([heading_deg, pitch_deg, roll_deg])
    base = np.array([[1., 0., 0.], [0., 0., 1.], [0., -1., 0.]])
    return rotation_z(-h) @ base @ rotation_x(p) @ rotation_z(r)


def geodetic_to_ecef(lat_deg, lon_deg):
    """WGS84, common ellipsoidal height h=0 (not measured altitude)."""
    lat, lon = np.deg2rad([lat_deg, lon_deg])
    a, f = 6378137.0, 1 / 298.257223563
    e2 = f * (2 - f)
    radius = a / np.sqrt(1 - e2 * np.sin(lat)**2)
    return np.array([radius * np.cos(lat) * np.cos(lon),
                     radius * np.cos(lat) * np.sin(lon),
                     radius * (1 - e2) * np.sin(lat)])


def position_enu(lat, lon, origin_lat, origin_lon):
    phi, lam = np.deg2rad([origin_lat, origin_lon])
    transform = np.array([
        [-np.sin(lam), np.cos(lam), 0],
        [-np.sin(phi)*np.cos(lam), -np.sin(phi)*np.sin(lam), np.cos(phi)],
        [np.cos(phi)*np.cos(lam), np.cos(phi)*np.sin(lam), np.sin(phi)],
    ])
    position = transform @ (geodetic_to_ecef(lat, lon) - geodetic_to_ecef(origin_lat, origin_lon))
    position[2] = 0.0  # Explicit flat-height experimental assumption.
    return position


def erp_pixel_to_unit_ray(u, v, width, height):
    """Jiang-style spherical bearing, in right/down/forward camera axes.

    Same pixel-center convention as Stage 1; that stage's image-local axes
    (forward, right, up) are permuted here to (right, down, forward).
    No pinhole intrinsics or metadata are involved in this conversion.
    """
    longitude = 2 * np.pi * (np.asarray(u) + 0.5) / width - np.pi
    latitude = np.pi / 2 - np.pi * (np.asarray(v) + 0.5) / height
    return np.stack([np.cos(latitude)*np.sin(longitude), -np.sin(latitude),
                     np.cos(latitude)*np.cos(longitude)], axis=-1)


def rays_to_world(rays, rotation):
    world = rays @ rotation.T
    return world / np.linalg.norm(world, axis=-1, keepdims=True)
