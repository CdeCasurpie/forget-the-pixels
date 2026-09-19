"""Metric height fitting and optional architectural floor regularization."""
from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares


def predicted_row(height_m, distance_m, image_height_px, camera_height_m: float = 2.5):
    """Equirectangular row of a point at `height_m` over a flat ground plane."""
    return np.asarray(image_height_px) * (
        0.5 - np.arctan2(np.asarray(height_m) - camera_height_m, distance_m) / np.pi
    )


def fit_height(observations: list[dict], camera_height_m: float = 2.5, bounds_m=(1.0, 150.0)) -> dict:
    """Fit one vertical extrusion height with robust multiview reprojection."""
    if len(observations) < 2:
        raise ValueError("At least two usable views are required")
    distances = np.asarray([item["distance_m"] for item in observations], dtype=float)
    image_heights = np.asarray([item["image_height"] for item in observations], dtype=float)
    observed_rows = np.asarray([item["cut_y"] for item in observations], dtype=float)
    if not np.isfinite([*distances, *image_heights, *observed_rows, camera_height_m]).all() or np.any(distances <= 0):
        raise ValueError("Invalid observation geometry")

    def residual(height):
        return (predicted_row(height[0], distances, image_heights, camera_height_m) - observed_rows) * 1024.0 / image_heights

    initial = np.clip(
        np.median(camera_height_m + distances * np.tan((0.5 - observed_rows / image_heights) * np.pi)),
        *bounds_m,
    )
    ordinary = least_squares(residual, [initial], bounds=bounds_m)
    robust = least_squares(residual, [initial], bounds=bounds_m, loss="soft_l1", f_scale=3.0)
    height = float(robust.x[0])
    normalized = residual([height])
    return {
        "height_m": height,
        "least_squares_height_m": float(ordinary.x[0]),
        "residuals_normalized_px": normalized.tolist(),
        "rmse_normalized_px": float(np.sqrt(np.mean(normalized ** 2))),
        "bounds_m": list(bounds_m),
        "at_bound": bool(min(height - bounds_m[0], bounds_m[1] - height) < 0.01),
        "loss": "soft_l1",
        "f_scale_normalized_px": 3.0,
    }


def regularize_height_to_floors(
    height_m: float,
    *,
    minimum_floor_height_m: float = 2.30,
    maximum_floor_height_m: float = 3.00,
    nominal_floor_height_m: float = 2.80,
    minimum_floors: int = 1,
    maximum_floors: int = 80,
) -> dict:
    """Choose an integer floor count while retaining the continuous estimate.

    The result is a convention for procedural generation. It does not replace
    the measured/reprojected continuous height in diagnostics.
    """
    if not np.isfinite(height_m) or height_m <= 0:
        raise ValueError("height_m must be positive and finite")
    if not minimum_floor_height_m <= nominal_floor_height_m <= maximum_floor_height_m:
        raise ValueError("nominal_floor_height_m must lie within the allowed range")
    candidates = []
    for floors in range(minimum_floors, maximum_floors + 1):
        implied_floor_height = height_m / floors
        if minimum_floor_height_m <= implied_floor_height <= maximum_floor_height_m:
            candidates.append((abs(height_m - floors * nominal_floor_height_m), floors))
    if not candidates:
        return {"floor_count": None, "floor_height_m": None, "regularized_height_m": None}
    _, floors = min(candidates)
    return {
        "floor_count": floors,
        "floor_height_m": float(nominal_floor_height_m),
        "regularized_height_m": float(floors * nominal_floor_height_m),
    }
