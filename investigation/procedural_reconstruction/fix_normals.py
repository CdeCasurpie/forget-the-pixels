from shapely.geometry import Point

def get_outward_normal(poly, p1, p2):
    import numpy as np
    a = np.array(p1)
    b = np.array(p2)
    t = b - a
    length = np.linalg.norm(t)
    if length == 0: return None, None, None
    t /= length
    n = np.array([t[1], -t[0]])
    
    mid = a + t * (length / 2.0)
    # Check if n points inwards
    if poly.contains(Point(mid + n * 0.01)):
        n = -n # flip so it points outwards
    return t, n, length
