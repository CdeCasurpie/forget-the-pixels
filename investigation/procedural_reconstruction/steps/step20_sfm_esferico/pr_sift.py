"""Panoramic rectification + SIFT. All rotations here are image-local."""

import cv2
import numpy as np


def erp_to_ray(uv, width, height):
    """Pixel centers: longitude [-pi, pi), latitude positive upwards.

    Axes: x at the ERP center, y towards increasing longitude, z upwards.
    """
    lon = 2 * np.pi * (uv[..., 0] + 0.5) / width - np.pi
    lat = np.pi / 2 - np.pi * (uv[..., 1] + 0.5) / height
    return np.stack((np.cos(lat) * np.cos(lon),
                     np.cos(lat) * np.sin(lon), np.sin(lat)), axis=-1)


def ray_to_erp(ray, width, height):
    lon = np.arctan2(ray[..., 1], ray[..., 0])
    lat = np.arctan2(ray[..., 2], np.hypot(ray[..., 0], ray[..., 1]))
    return np.stack(((lon + np.pi) * width / (2 * np.pi) - 0.5,
                     (np.pi / 2 - lat) * height / np.pi - 0.5), axis=-1)


def rotation_x(alpha):
    c, s = np.cos(alpha), np.sin(alpha)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float32)


def pr_mask(rays, n):
    """Taira's undulating mask, not a constant-width equatorial band.

    beta=pi/(2n); |z| <= |y| tan(beta), equivalently
    |latitude| <= atan(|sin(longitude)| tan(beta)). These wedges partition
    the sphere under the n rotations about x (apart from boundary ties).
    """
    if n == 1:
        return np.full(rays.shape[:-1], 255, dtype=np.uint8)
    valid = np.abs(rays[..., 2]) <= np.abs(rays[..., 1]) * np.tan(np.pi / (2*n))
    return valid.astype(np.uint8) * 255


def extract(image, n=6):
    """Return original-ERP coordinates, unchanged descriptors and debug tiles.

    R maps original rays to rectified rays. Inverse image sampling and mapping
    detected keypoints back both use R.T (row-vector equivalent: ray @ R).
    SIFT size/angle are retained in the rectified frame, not claimed to be
    original-ERP scales/orientations. No cross-view matching is performed.
    """
    if n < 1:
        raise ValueError('n must be positive')
    height, width = image.shape[:2]
    yy, xx = np.indices((height, width), dtype=np.float32)
    rays = erp_to_ray(np.stack((xx, yy), axis=-1), width, height)
    mask = pr_mask(rays, n)
    sift = cv2.SIFT_create()
    coords, descriptors, rect_uv, indices, properties, tiles = [], [], [], [], [], []
    for m in range(n):
        rotation = rotation_x(m * np.pi / n)
        source = ray_to_erp(rays @ rotation, width, height).astype(np.float32)
        # Longitude wraps; latitude clamps, rather than wrapping across poles.
        source[..., 0] %= width
        source[..., 1] = np.clip(source[..., 1], 0, height - 1)
        rectified = cv2.remap(image, source[..., 0], source[..., 1],
                             cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        keys, desc = sift.detectAndCompute(cv2.cvtColor(rectified, cv2.COLOR_BGR2GRAY), mask)
        if keys:
            uv = np.array([k.pt for k in keys], dtype=np.float32)
            original = ray_to_erp(erp_to_ray(uv, width, height) @ rotation, width, height)
            coords.append(original.astype(np.float32))
            descriptors.append(desc)
            rect_uv.append(uv)
            indices.append(np.full(len(keys), m, dtype=np.int32))
            properties.append(np.array([(k.size, k.angle, k.response) for k in keys], dtype=np.float32))
        # Full rotated panorama, with invalid detection regions darkened.
        tile = rectified.copy()
        tile[mask == 0] //= 4
        tile = cv2.resize(tile, (640, 320))
        cv2.putText(tile, f'm={m} alpha={180*m/n:.0f} deg; SIFT={len(keys)}',
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        tiles.append(tile)
    def combine(parts, shape, dtype):
        return np.concatenate(parts) if parts else np.empty(shape, dtype=dtype)
    data = {
        'keypoints_uv': combine(coords, (0, 2), np.float32),
        'descriptors': combine(descriptors, (0, 128), np.float32),
        'rectified_uv': combine(rect_uv, (0, 2), np.float32),
        'rectification_index': combine(indices, (0,), np.int32),
        'rectified_size_angle_response': combine(properties, (0, 3), np.float32),
        'image_wh': np.array([width, height]), 'n': np.array(n),
    }
    return data, np.vstack(tiles)
