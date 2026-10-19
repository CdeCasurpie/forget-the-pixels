"""R5: shallow window dressing, not a full interior.

Every exterior window receives a flat backdrop just behind its wall so the
aperture reads as depth instead of a hole to the sky, and the residential
windows draw a deterministic curtain coverage. The decision is data only; the
catalog draws the fabric and the backing plane.
"""
import hashlib

import numpy as np


def plan_dressings(plan):
    data = plan.to_dict() if hasattr(plan, 'to_dict') else plan
    if 'interior' in data:
        return []
    seed = data['request'].get('seed', 0)
    dressings = []
    for opening in data['openings']:
        if opening['kind'] != 'window':
            continue
        digest = int.from_bytes(hashlib.sha256(
            f'{seed}:{opening["id"]}'.encode()).digest()[:4], 'little')
        rng = np.random.default_rng(digest)
        # Shopfronts stay clear; a home draws a curtain in most windows.
        closed = opening.get('use') not in ('commercial', 'shop')
        fraction = 0.0 if not closed or rng.random() > .6 else float(rng.uniform(.18, .52))
        dressings.append(dict(id=opening['id'], surface_id=opening['surface'],
                              fraction=round(fraction, 4), backdrop=True, seed=digest))
    return dressings


__all__ = ['plan_dressings']
