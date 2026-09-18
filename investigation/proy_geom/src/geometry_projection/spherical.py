"""Metric ENU points to upright equirectangular panoramas and Step 5 strips.

World axes: east, north, up. Heading clockwise from true north; pitch positive
up; roll positive rotates camera right toward camera up. Provider pitch/roll
must be converted to these conventions before use.
"""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class PanoramaCamera:
    center: tuple[float, float, float]
    heading_deg: float
    pitch_deg: float = 0.
    roll_deg: float = 0.

    def __post_init__(self):
        if np.asarray(self.center).shape != (3,) or not np.isfinite([*self.center, self.heading_deg, self.pitch_deg, self.roll_deg]).all():
            raise ValueError('Camera pose must be finite XYZ and angles')

    @property
    def basis(self):
        h, p, r = np.radians([self.heading_deg, self.pitch_deg, self.roll_deg])
        right = np.array([np.cos(h), -np.sin(h), 0])
        forward = np.array([np.sin(h)*np.cos(p), np.cos(h)*np.cos(p), np.sin(p)])
        up = np.cross(right, forward)
        return np.column_stack((right*np.cos(r)+up*np.sin(r),
                                up*np.cos(r)-right*np.sin(r), forward))

    def angles(self, points):
        points = np.asarray(points, dtype=float)
        if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():
            raise ValueError('Expected finite Nx3 points')
        rays = (points-np.asarray(self.center)) @ self.basis
        if np.any(np.linalg.norm(rays, axis=1) < 1e-9):
            raise ValueError('Cannot project the camera center')
        return np.degrees(np.column_stack((np.arctan2(rays[:, 0], rays[:, 2]),
                         np.arctan2(rays[:, 1], np.hypot(rays[:, 0], rays[:, 2])))))

    def pixels(self, points, width, height):
        if width < 2 or height < 2:
            raise ValueError('Image dimensions must be >=2')
        angles = self.angles(points)
        return np.column_stack((np.mod((.5+angles[:, 0]/360)*width, width),
                                np.clip((.5-angles[:, 1]/180)*height, 0, height-1)))


def strip_pixels(panorama_pixels, source_size, strip_size, center_yaw_deg, fov_deg):
    """Exact inverse of Step 5 sampling, including its vertical endpoint rule."""
    sw, sh = source_size
    w, h = strip_size
    if min(sw, sh, w, h) < 2 or not 0 < fov_deg <= 360:
        raise ValueError('Invalid dimensions or FOV')
    pixels = np.asarray(panorama_pixels, float)
    yaw = (pixels[:, 0]/sw-.5)*360
    offset = (yaw-center_yaw_deg+180) % 360-180
    return np.column_stack(((offset/fov_deg+.5)*w, pixels[:, 1]*(h-1)/(sh-1)))


def prism_edges(footprint, height, base_z=0., spacing=.2):
    """Sample every exterior/interior ring edge and vertical; no visibility culling."""
    if not np.isfinite([height, base_z, spacing]).all() or height <= 0 or spacing <= 0:
        raise ValueError('Height and spacing must be positive and finite')
    if footprint.geom_type != 'Polygon' or not footprint.is_valid or footprint.is_empty:
        raise ValueError('A valid nonempty Polygon is required')
    result = []
    def add(a, b, kind):
        n = max(2, int(np.ceil(np.linalg.norm(np.array(b)-a)/spacing))+1)
        result.append((kind, np.linspace(a, b, n)))
    for ring in [footprint.exterior, *footprint.interiors]:
        xy = np.array(ring.coords)[:, :2]
        for a, b in zip(xy[:-1], xy[1:]):
            add([*a, base_z], [*b, base_z], 'base')
            add([*a, base_z+height], [*b, base_z+height], 'roof')
            add([*a, base_z], [*a, base_z+height], 'vertical')
    return result


def draw_edges(image, curves, color, thickness=2):
    """Clip segments to image and break seam crossings; keep curved spherical edges."""
    import cv2
    h, w = image.shape[:2]
    for points in curves:
        for a, b in zip(points[:-1], points[1:]):
            if not np.isfinite([a, b]).all() or abs(b[0]-a[0]) > w/2:
                continue
            visible, start, end = cv2.clipLine((0, 0, w, h), tuple(np.rint(a).astype(int)), tuple(np.rint(b).astype(int)))
            if visible:
                cv2.line(image, start, end, color, thickness, cv2.LINE_AA)
