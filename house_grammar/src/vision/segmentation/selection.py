"""Model-independent selection in original image pixel coordinates."""
import numpy as np


def select_vertical(masks, x: float, half_width: int = 0):
    """Return indices and evidence for masks intersecting a vertical band.

    This selects candidates, not cadastral identities. Occluders or background
    buildings can share a bearing. Never test bounding boxes instead of masks.
    """
    masks = np.asarray(masks)
    if masks.ndim != 3 or masks.dtype != np.bool_:
        raise ValueError("masks must be boolean N x H x W")
    n, h, w = masks.shape
    if h == 0 or w == 0 or not np.isfinite(x) or not 0 <= x < w:
        raise ValueError("target column outside image")
    if type(half_width) is not int or half_width < 0:
        raise ValueError("half_width must be a nonnegative integer")
    column = min(w - 1, int(np.floor(x + .5)))
    left, right = max(0, column-half_width), min(w, column+half_width+1)
    evidence = []
    for i in range(n):
        rows = np.any(masks[i, :, left:right], axis=1)
        evidence.append({"index": i, "selected": bool(rows.any()),
                         "intersection_rows": int(rows.sum()),
                         "vertical_coverage": float(rows.mean()),
                         "area_pixels": int(masks[i].sum())})
    return [e['index'] for e in evidence if e['selected']], evidence
