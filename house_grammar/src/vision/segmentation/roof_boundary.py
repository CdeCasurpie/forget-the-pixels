"""Ordered sky/facade change-point detection on a narrow vertical strip."""
from __future__ import annotations

import cv2
import numpy as np


def split_vertical_strip(rgb: np.ndarray, min_segment_px: int = 8) -> tuple[int, float]:
    """Return the first structural row and Lab separation score.

    The detector partitions ordered rows into sky [0, cut) and structure
    [cut, end). It is deliberately a heuristic observation, never a semantic
    certainty. Luminance is downweighted so dark ground floors do not dominate
    the sky-to-building transition.
    """
    rgb = np.asarray(rgb)
    if rgb.ndim != 3 or rgb.shape[2] != 3 or len(rgb) < 2 * min_segment_px:
        raise ValueError("Expected a sufficiently long HxWx3 RGB strip")
    lab = cv2.cvtColor(rgb.astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)
    profile = np.median(lab, axis=1).astype(float) * np.array([0.2, 1.0, 1.0])
    profile -= profile.mean(axis=0)
    if np.sum(profile**2) < 1e-8:
        return min_segment_px, 0.0
    count = len(profile)
    sums = np.vstack((np.zeros((1, 3)), np.cumsum(profile, axis=0)))
    squares = np.r_[0.0, np.cumsum(np.sum(profile**2, axis=1))]
    cuts = np.arange(min_segment_px, count - min_segment_px + 1)
    costs = (
        squares[cuts] - np.sum(sums[cuts] ** 2, axis=1) / cuts
        + squares[count] - squares[cuts]
        - np.sum((sums[count] - sums[cuts]) ** 2, axis=1) / (count - cuts)
    )
    best = int(np.argmin(costs))
    total = squares[count] - np.sum(sums[count] ** 2) / count
    return int(cuts[best]), float(np.clip(1.0 - costs[best] / max(total, 1e-12), 0.0, 1.0))


def detect_roof_boundary(rgb_strip: np.ndarray, *, min_segment_px: int = 8) -> dict[str, float | int]:
    cut_y, separation = split_vertical_strip(rgb_strip, min_segment_px)
    return {
        "cut_y": cut_y,
        "separation": separation,
        "sky_start_y": 0,
        "sky_end_y": cut_y,
        "structure_start_y": cut_y,
        "structure_end_y": int(rgb_strip.shape[0]),
    }
