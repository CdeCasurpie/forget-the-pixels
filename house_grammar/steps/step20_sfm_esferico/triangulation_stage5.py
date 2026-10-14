"""Known-pose angular residual and pairwise closest-point triangulation."""

import numpy as np


def spherical_epipolar_residual(center_a, center_b, ray_a, ray_b):
    """One-sided angular distance of B's ray to plane (baseline, A's ray).

    asin(|d_b . (baseline x d_a)| / ||baseline x d_a||), in radians.
    All inputs are ENU; rays must be unit length. Baseline normalization
    removes metric scale. Undefined epipolar planes return NaN and fail the
    threshold test. No essential-matrix estimation is involved.
    """
    baseline = center_b - center_a
    norm = np.linalg.norm(baseline, axis=-1, keepdims=True)
    baseline = np.divide(baseline, norm, out=np.zeros_like(baseline), where=norm > 1e-12)
    normal = np.cross(baseline, ray_a)
    normal_norm = np.linalg.norm(normal, axis=-1)
    sine = np.divide(np.abs(np.sum(ray_b * normal, axis=-1)), normal_norm,
                     out=np.full(len(ray_a), np.nan), where=normal_norm > 1e-12)
    return np.arcsin(np.clip(sine, 0, 1))


def closest_points(center_a, center_b, ray_a, ray_b):
    """Midpoint of closest points on two lines; caller checks positive depths.

    Parallel and antiparallel lines (1-dot**2 <= 1e-12) are invalid.
    """
    delta = center_b - center_a
    cosine = np.clip(np.sum(ray_a * ray_b, axis=-1), -1, 1)
    denominator = 1 - cosine**2
    valid = denominator > 1e-12
    ad = np.sum(ray_a * delta, axis=-1)
    bd = np.sum(ray_b * delta, axis=-1)
    s = np.divide(ad - cosine*bd, denominator,
                  out=np.full(len(ray_a), np.nan), where=valid)
    t = np.divide(cosine*ad - bd, denominator,
                  out=np.full(len(ray_a), np.nan), where=valid)
    pa, pb = center_a + s[:, None]*ray_a, center_b + t[:, None]*ray_b
    points = (pa + pb)/2
    gap = np.linalg.norm(pa-pb, axis=-1)
    # Angle between camera-to-midpoint sight lines, after triangulation.
    sight_a, sight_b = points-center_a, points-center_b
    na = np.linalg.norm(sight_a, axis=-1)
    nb = np.linalg.norm(sight_b, axis=-1)
    valid &= (na > 1e-12) & (nb > 1e-12)
    cos_parallax = np.divide(np.sum(sight_a*sight_b, axis=-1), na*nb,
                             out=np.full(len(ray_a), np.nan), where=valid)
    parallax = np.degrees(np.arccos(np.clip(cos_parallax, -1, 1)))
    return points, s, t, gap, parallax, valid
