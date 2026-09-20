"""Pinhole views of an upright 2:1 equirectangular panorama.

Panorama frame: X right, Y up, Z toward its horizontal center. Yaw is
positive rightward; pitch is positive upward. No source pitch/roll correction
is assumed. Pixel centers use integer coordinates; image center is (W-1)/2.
"""
from dataclasses import dataclass
import math

import cv2
import numpy as np


def angles_from_direction(direction) -> tuple[float, float]:
    """Convert an XYZ direction in the panorama frame to yaw/pitch degrees."""
    vector = np.asarray(direction, dtype=float)
    if vector.shape != (3,) or not np.isfinite(vector).all() or not np.any(vector):
        raise ValueError("direction must be a finite nonzero XYZ vector")
    vector = vector / np.max(np.abs(vector))
    x, y, z = vector
    return math.degrees(math.atan2(x, z)), math.degrees(math.atan2(y, math.hypot(x, z)))


@dataclass(frozen=True)
class PinholeCamera:
    width: int = 1200
    height: int = 900
    horizontal_fov_deg: float = 90.0
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0

    def __post_init__(self):
        if any(type(n) is not int or n <= 0 for n in (self.width, self.height)):
            raise ValueError("width and height must be positive integers")
        if not all(math.isfinite(v) for v in (self.horizontal_fov_deg, self.yaw_deg, self.pitch_deg)):
            raise ValueError("angles must be finite")
        if not 0 < self.horizontal_fov_deg < 180:
            raise ValueError("horizontal FOV must be in (0, 180)")
        if not -90 <= self.pitch_deg <= 90:
            raise ValueError("pitch must be in [-90, 90]")

    @property
    def intrinsics(self) -> np.ndarray:
        focal = self.width / (2 * math.tan(math.radians(self.horizontal_fov_deg) / 2))
        return np.array([[focal, 0, (self.width - 1) / 2],
                         [0, focal, (self.height - 1) / 2], [0, 0, 1]])

    @property
    def vertical_fov_deg(self) -> float:
        return math.degrees(2 * math.atan(self.height / (2 * self.intrinsics[1, 1])))

    @property
    def camera_to_panorama(self) -> np.ndarray:
        """Columns are right, down, forward (OpenCV camera axes) in XYZ."""
        yaw, pitch = np.radians([self.yaw_deg, self.pitch_deg])
        right = [np.cos(yaw), 0, -np.sin(yaw)]
        down = [np.sin(yaw) * np.sin(pitch), -np.cos(pitch), np.cos(yaw) * np.sin(pitch)]
        forward = [np.sin(yaw) * np.cos(pitch), np.sin(pitch), np.cos(yaw) * np.cos(pitch)]
        return np.column_stack((right, down, forward))


def extract_rectilinear(panorama: np.ndarray, camera: PinholeCamera) -> np.ndarray:
    """Render with horizontal seam wrapping and clamped polar sampling.

    Source convention matches existing acquisition: yaw=0 samples x=W/2,
    pitch=0 samples y=H/2. Source must cover the full sphere, uncropped.
    """
    if panorama.ndim not in (2, 3) or panorama.size == 0:
        raise ValueError("panorama must be a nonempty image")
    h, w = panorama.shape[:2]
    if w != 2 * h or max(h, w, camera.width, camera.height) >= 32767:
        raise ValueError("source must be 2:1 and dimensions must be below OpenCV's 32767 limit")
    if panorama.dtype not in (np.uint8, np.uint16, np.float32, np.float64):
        raise ValueError("unsupported image dtype")
    k = camera.intrinsics
    u, v = np.meshgrid(np.arange(camera.width), np.arange(camera.height))
    rays = np.stack(((u-k[0, 2])/k[0, 0], (v-k[1, 2])/k[1, 1], np.ones_like(u)), axis=-1)
    rays = rays @ camera.camera_to_panorama.T
    longitude = np.arctan2(rays[..., 0], rays[..., 2])
    latitude = np.arctan2(rays[..., 1], np.hypot(rays[..., 0], rays[..., 2]))
    map_x = np.mod((0.5 + longitude/(2*np.pi))*w, w).astype(np.float32)
    map_y = np.clip((0.5 - latitude/np.pi)*h, 0, h-1).astype(np.float32)
    return cv2.remap(panorama, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
