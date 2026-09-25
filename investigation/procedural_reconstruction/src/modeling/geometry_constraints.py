import numpy as np
import shapely
from shapely.geometry import Polygon, LineString, MultiLineString, Point
from shapely.ops import linemerge, unary_union

# Cadastral coordinates are snapped to this grid before anything is derived from
# them. `modeling.exposure` already snaps footprints to survive coincident-edge
# differences; unless every consumer agrees on the same grid, the half-grid drift
# leaks out as vertices microns outside the lot, which long thin triangles then
# smear into metres of apparent violation.
CADASTRAL_GRID_M = 1e-4
# Thin finish coatings protrude 2 mm, with their backs buried in the support.
# This is architectural surface separation, not a tessellation tolerance.
SURFACE_EPSILON_M = 0.002


def snap(geometry, grid: float = CADASTRAL_GRID_M):
    """Geometry on the shared cadastral grid, repaired if snapping broke it."""
    snapped = shapely.set_precision(geometry, grid)
    if not snapped.is_valid:
        snapped = snapped.buffer(0)
    return snapped


def parcel_polygon(context, grid: float = CADASTRAL_GRID_M) -> Polygon:
    """The lot polygon every stage of one building must agree on."""
    polygon = Polygon(context.polygon)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    return snap(polygon, grid)


def front_lines(context) -> list[LineString]:
    """LineStrings of the parcel edges a ParcelContext declares as street fronts."""
    coords = context.polygon
    lines = []
    for index in context.explicit_fronts:
        if 0 <= index < len(coords):
            lines.append(LineString([coords[index], coords[(index + 1) % len(coords)]]))
    return lines


def largest_polygon(geometry):
    """Single Polygon from any geometry, or None when nothing usable remains."""
    if geometry is None or geometry.is_empty:
        return None
    if geometry.geom_type == "Polygon":
        return geometry
    parts = [
        part
        for part in getattr(geometry, "geoms", [])
        if part.geom_type == "Polygon" and not part.is_empty
    ]
    return max(parts, key=lambda part: part.area) if parts else None


def outward_normal(polygon: Polygon, p1, p2, probe: float = 1e-3):
    """Unit normal of segment p1->p2 pointing away from the polygon interior."""
    a = np.asarray(p1, float)[:2]
    b = np.asarray(p2, float)[:2]
    tangent = b - a
    length = float(np.linalg.norm(tangent))
    if length < 1e-9:
        return None, None, 0.0
    tangent = tangent / length
    normal = np.array([tangent[1], -tangent[0]])
    if polygon.contains(Point(a + tangent * (length / 2.0) + normal * probe)):
        normal = -normal
    return tangent, normal, length


def projection_envelope(parcel: Polygon, front_lines, overhang_m: float = 1.35) -> Polygon:
    """Parcel plus a bounded apron over the street in front of its front edges.

    Balconies, cornices, eaves and awnings legitimately overhang the sidewalk, so
    attachments are clipped to this instead of the cadastral line. Party-wall and
    rear edges get no apron: nothing may grow over a neighbour.
    """
    if parcel.is_empty or not np.isfinite(overhang_m) or overhang_m <= 0:
        return parcel
    lines = [line for line in (front_lines or []) if line is not None and not line.is_empty]
    if not lines:
        return parcel
    # Mitred dilation keeps corners square instead of rounding them off.
    dilated = parcel.buffer(overhang_m, join_style=2)
    aprons = []
    for line in lines:
        coords = list(line.coords)
        if len(coords) < 2:
            continue
        for p1, p2 in zip(coords[:-1], coords[1:]):
            tangent, normal, length = outward_normal(parcel, p1, p2)
            if tangent is None:
                continue
            a = np.asarray(p1, float)[:2] - tangent * overhang_m
            b = np.asarray(p2, float)[:2] + tangent * overhang_m
            reach = normal * (overhang_m * 1.5)
            aprons.append(Polygon([a, b, b + reach, a + reach]))
    if not aprons:
        return parcel
    envelope = unary_union([parcel, dilated.intersection(unary_union(aprons))])
    if not envelope.is_valid:
        envelope = envelope.buffer(0)
    if envelope.geom_type == "MultiPolygon":
        envelope = max(envelope.geoms, key=lambda part: part.area)
    return envelope

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
