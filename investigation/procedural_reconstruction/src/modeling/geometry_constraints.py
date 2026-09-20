import numpy as np
from shapely.geometry import Polygon, LineString, MultiLineString, Point
from shapely.ops import linemerge

def extend_line_start(coords, dist):
    p0, p1 = np.array(coords[0]), np.array(coords[1])
    v = p0 - p1
    length = np.linalg.norm(v)
    if length == 0: return tuple(p0)
    return tuple(p0 + (v / length) * dist)

def extend_line_end(coords, dist):
    pn, pn_1 = np.array(coords[-1]), np.array(coords[-2])
    v = pn - pn_1
    length = np.linalg.norm(v)
    if length == 0: return tuple(pn)
    return tuple(pn + (v / length) * dist)

def get_interior_side(polygon: Polygon, line: LineString) -> str:
    pt = line.interpolate(0.5, normalized=True)
    pt1 = line.interpolate(0.49, normalized=True)
    pt2 = line.interpolate(0.51, normalized=True)
    dx, dy = pt2.x - pt1.x, pt2.y - pt1.y
    length = np.hypot(dx, dy)
    
    if length == 0: return 'left'
        
    nx, ny = -dy / length, dx / length
    for dist in [0.01, 0.1, 1.0, 5.0]:
        if polygon.contains(Point(pt.x + nx * dist, pt.y + ny * dist)):
            return 'left'
        if polygon.contains(Point(pt.x - nx * dist, pt.y - ny * dist)):
            return 'right'
            
    return 'left'

def create_setback_mask(polygon: Polygon, front_line: LineString, distance: float) -> Polygon:
    if distance <= 0: return Polygon()
    minx, miny, maxx, maxy = polygon.bounds
    extension = np.hypot(maxx - minx, maxy - miny) * 2.0 + distance
    if extension < 100: extension = 100
    
    side = get_interior_side(polygon, front_line)
    signed_distance = distance if side == 'left' else -distance
    
    try:
        offset = front_line.offset_curve(signed_distance, join_style=2)
    except Exception:
        return front_line.buffer(distance, cap_style=2)
        
    if isinstance(offset, MultiLineString) or offset.is_empty:
        return front_line.buffer(distance, cap_style=2)
        
    f_coords = list(front_line.coords)
    o_coords = list(offset.coords)
    
    dist_straight = np.hypot(f_coords[0][0] - o_coords[0][0], f_coords[0][1] - o_coords[0][1])
    dist_flipped = np.hypot(f_coords[0][0] - o_coords[-1][0], f_coords[0][1] - o_coords[-1][1])
    if dist_flipped < dist_straight:
        o_coords.reverse()

    f_start_ext = extend_line_start(f_coords, extension)
    f_end_ext = extend_line_end(f_coords, extension)
    o_start_ext = extend_line_start(o_coords, extension)
    o_end_ext = extend_line_end(o_coords, extension)
    
    mask_coords = [f_start_ext] + f_coords + [f_end_ext, o_end_ext] + list(reversed(o_coords)) + [o_start_ext, f_start_ext]
    mask = Polygon(mask_coords)
    if not mask.is_valid: mask = mask.buffer(0)
    return mask

def apply_edge_setbacks(parcel_poly: Polygon, specific_edges: list[LineString], distance: float) -> Polygon:
    if distance <= 0: return parcel_poly
    if not specific_edges: return parcel_poly
    
    merged_edges = linemerge(specific_edges)
    lines = [merged_edges] if isinstance(merged_edges, LineString) else list(merged_edges.geoms)
        
    footprint = parcel_poly
    for line in lines:
        mask = create_setback_mask(parcel_poly, line, distance)
        footprint = footprint.difference(mask)
        
    return footprint
