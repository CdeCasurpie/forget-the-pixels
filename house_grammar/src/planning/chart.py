"""Surface chart for the new planning pipeline.

The catalog resolvers place pieces on a :class:`domain.surfaces.SurfaceChart`:
exposed bodies plus one facade surface per built edge. This module derives that
chart from the massing storeys (one body per storey, so a setback storey stays a
real body instead of being flattened into a single building footprint) and the
openings the constructive envelope already reserved.

It authors no geometry of its own: bodies are the massing storeys, surfaces are
the exposed edges the massing stage already charts, and the permitted projection
envelope is the parcel widened over its declared street fronts.
"""
import numpy as np
from shapely.geometry import LineString, Polygon, shape
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from domain.architecture import MassSpec
from domain.models import FacadeSpecification, Opening
from domain.surfaces import SurfaceChart, WallSurface
from modeling.geometry_constraints import projection_envelope
from planning.interiors import EXTERIOR

STREET_OVERHANG_M = 1.35


def _data(plan):
    return plan.to_dict() if hasattr(plan, 'to_dict') else plan


def _massing_of(plan):
    data = _data(plan)
    if 'massing' in data:
        massing = data['massing']
    elif 'interior' in data:
        massing = data['interior']['massing']
    else:
        massing = data
    return massing, data.get('request') or massing.get('request')


def primary_frame(frames):
    return min(frames, key=lambda key: (-frames[key]['length_m'], key))


def _canonical_ring(ring, frame):
    """Rotate a ring to the canonical start the massing chart used.

    The massing stage starts each ring at the point closest to the primary
    street frame so edge indices are stable and street-relative. Bodies must be
    rotated identically, otherwise ``edge`` on a control would name a different
    segment than the one the surface was charted for.
    """
    coords = [tuple(p) for p in list(ring.coords)[:-1]]

    def key(p):
        origin = frame['origin']
        right = frame['right']
        inward = frame['inward']
        delta = np.asarray(p) - origin
        return (round(float(delta @ right), 6), round(float(delta @ inward), 6))

    start = min(range(len(coords)), key=lambda i: key(coords[i]))
    return coords[start:] + coords[:start]


def _parse_surface_id(surface_id):
    """``{body}/floor{n}/ring{r}/edge{e}/part{p}`` -> (record, ring, edge)."""
    parts = surface_id.split('/')
    ring = int(parts[-3][len('ring'):])
    edge = int(parts[-2][len('edge'):])
    return '/'.join(parts[:-3]), ring, edge


def _openings_by_edge(openings):
    """Group envelope openings by the surface chart edge they were cut in."""
    grouped = {}
    for opening in openings:
        host = opening.get('surface')
        if not host:
            continue
        record, ring, edge = _parse_surface_id(host)
        grouped.setdefault((record, ring, edge), []).append(opening)
    return grouped


def _facade_openings(records, surface_vertex_a, tangent, base_z):
    result = []
    for opening in records:
        line = shape(opening['geometry'])
        points = [np.asarray(p, float) for p in line.coords]
        if not points:
            continue
        along = [float(np.dot(p - surface_vertex_a, tangent)) for p in points]
        u0, u1 = min(along), max(along)
        bottom = float(opening['bottom_m'])
        height = float(opening['top_m']) - bottom
        if u1 - u0 <= 1e-6 or height <= 1e-6:
            continue
        result.append(Opening(
            kind='window' if opening.get('kind') == 'window' else 'door',
            u_m=u0, v_m=bottom - base_z, width_m=u1 - u0, height_m=height,
            frame_width_m=float(opening.get('frame_width_m', .06)),
            recess_m=float(opening.get('recess_m', .08)),
            source=opening.get('source', 'planning')))
    return tuple(result)


def surface_chart(plan, *, openings=None, enclosed=False):
    """Build a :class:`SurfaceChart` from a massing/interior/envelope stage.

    ``openings`` defaults to the envelope openings carried by ``plan`` when it
    is an envelope plan; pass ``()`` to ignore them. The exterior-only route
    uses ``enclosed=True``: a projecting balcony belongs to the storey's slab
    silhouette, but its door and windows belong to the enclosure wall behind it.
    The original massing geometry remains unchanged in the plan.
    """
    massing, _request = _massing_of(plan)
    if openings is None:
        openings = _data(plan).get('openings', ())
    storeys = massing['storeys']
    frames = massing['fronts']
    primary = primary_frame(frames)
    frame = frames[primary]
    grouped = _openings_by_edge(openings)

    bodies = []
    surfaces = []
    for record in sorted(storeys, key=lambda r: (r['floor'], r['id'])):
        geometry = lambda s: s.get('enclosed_geometry', s['geometry']) if enclosed else s['geometry']
        poly = orient(shape(geometry(record)))
        neighbors = unary_union([shape(geometry(s)) for s in storeys
                                 if s['floor'] == record['floor'] and s['id'] != record['id']
                                 and s['kind'] == 'enclosed'])
        rings = [poly.exterior, *poly.interiors]
        canonical = [_canonical_ring(ring, frame) for ring in rings]
        base_z = float(record['bottom_m'])
        height = float(record['top_m']) - base_z
        bodies.append(MassSpec(
            id=record['id'], footprint=tuple(canonical[0]), base_z=base_z,
            roof_z=float(record['top_m']), floor_levels=(base_z, float(record['top_m'])),
            role=record['body'], roof_spec=None,
            footprint_holes=tuple(tuple(ring) for ring in canonical[1:]),
            kind=record['kind']))
        if record['kind'] != 'enclosed':
            continue
        edge_offset = 0
        for ring_index, coords in enumerate(canonical):
            count = len(coords)
            for local_edge in range(count):
                a = np.asarray(coords[local_edge], float)
                b = np.asarray(coords[(local_edge + 1) % count], float)
                line = LineString([a, b])
                visible = line.difference(neighbors)
                pieces = [visible] if visible.geom_type == 'LineString' else list(getattr(visible, 'geoms', ()))
                pieces = sorted((p for p in pieces if p.geom_type == 'LineString' and p.length > 1e-6),
                                key=lambda p: p.wkt)
                if not pieces:
                    continue
                tangent = (b - a) / line.length
                normal = np.array([tangent[1], -tangent[0]])
                front = None
                if ring_index == 0:
                    matches = [name for name, candidate in frames.items()
                               if float(np.dot(normal, -np.asarray(candidate['inward']))) > .98]
                    if matches:
                        front = min(matches)
                domains = []
                for piece in pieces:
                    along = [float(np.dot(np.asarray(p, float) - a, tangent)) for p in piece.coords]
                    domains.append((min(along), 0., max(along), height))
                edge = edge_offset + local_edge
                charted = grouped.get((record['id'], ring_index, local_edge), ())
                facade = FacadeSpecification(
                    edge_id=f'{record["id"]}/ring{ring_index}/edge{local_edge}',
                    vertex_a=tuple(a), vertex_b=tuple(b), width_m=float(line.length),
                    normal_xy=(float(normal[0]), float(normal[1])),
                    floor_levels_m=(0., height), openings=_facade_openings(charted, a, tangent, base_z),
                    is_front=front is not None, program_enabled=front is not None,
                    ornamented=False)
                surfaces.append(WallSurface(
                    mass_role=record['id'], edge=edge, base_z=base_z, height_m=height,
                    axes_m=(), facade=facade, visible_domains=tuple(domains),
                    thickness_m=EXTERIOR))
            edge_offset += count
    return SurfaceChart(tuple(bodies), tuple(surfaces))


def permitted_envelope(plan, overhang_m=STREET_OVERHANG_M):
    """Parcel widened over its declared street fronts, for projecting pieces."""
    massing, request = _massing_of(plan)
    if request is None:
        raise ValueError('A request with parcel and fronts is required for the projection envelope')
    context = request['context']
    parcel = Polygon(context['parcel'])
    fronts = context['fronts']
    coords = context['parcel']
    lines = [LineString([coords[index], coords[(index + 1) % len(coords)]])
             for index in sorted(set(fronts.values())) if 0 <= index < len(coords)]
    return projection_envelope(parcel, lines, overhang_m)
