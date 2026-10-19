"""R4: facade pilasters autocompleted between the bays of an ordered language.

The street styles that carry a classical order (republican, classical, baroque)
frame their bays with attached pilasters; the modern and timber languages stay
unadorned, and a plain residential facade is never stamped. Placement follows
the real opening axes: one pilaster per pier wide enough to carry it, measured
from the aperture edges, so the order matches the composition instead of a fixed
rhythm. Geometry comes from the vertical-member catalog at export time.
"""
from dataclasses import asdict

from shapely.geometry import LineString

from domain.vertical_members import MemberDesign
from planning.envelope import SLAB

ORDERED = {'republicano': 'smooth_moulded', 'clasico': 'panel_pilaster',
           'barroco': 'scroll_pilaster'}
WIDTH, DEPTH, EDGE = .36, .22, .28


def _style(request, body):
    for entry in request['building'].get('bodies', []) or []:
        if entry.get('id') == body and entry.get('style'):
            return entry['style']
    return request['building'].get('style', 'republicano')


def _gaps(line, openings):
    """Free u-intervals between the surface ends and the apertures, in order."""
    intervals = []
    for opening in openings:
        ends = sorted(line.project(__import__('shapely').geometry.Point(p))
                      for p in opening['geometry']['coordinates'])
        intervals.append(tuple(ends))
    intervals.sort()
    spans = []
    cursor = 0.
    for left, right in intervals:
        if left-cursor > 1e-6:
            spans.append((cursor, left))
        cursor = max(cursor, right)
    if line.length-cursor > 1e-6:
        spans.append((cursor, line.length))
    return spans


def plan_pilasters(plan):
    data = plan.to_dict() if hasattr(plan, 'to_dict') else plan
    openings = data['openings']
    pilasters = []
    for row in data['massing']['storeys']:
        if row['kind'] != 'enclosed':
            continue
        style = _style(data['request'], row['body'])
        if style not in ORDERED:
            continue
        bottom = row['bottom_m']
        height = row['top_m']-SLAB-bottom
        if height < .90:
            continue
        for surface in row.get('surfaces', []):
            if not surface.get('enclosure') or surface.get('front') is None:
                continue
            line = LineString(surface['line'])
            if line.length < 1.4:
                continue
            placed = sorted((op for op in openings if op['surface'] == surface['id']),
                            key=lambda op: line.project(
                                LineString(op['geometry']['coordinates']).centroid))
            if not placed:
                continue
            for index, (start, end) in enumerate(_gaps(line, placed)):
                span = end-start
                if span < WIDTH+2*EDGE:
                    continue
                pilasters.append(dict(
                    id=f'{surface["id"]}/pilaster{index}', surface_id=surface['id'],
                    floor=row['floor'], u_m=round((start+end)/2, 6),
                    bottom_m=round(bottom, 6), height_m=round(height, 6),
                    width_m=WIDTH, depth_m=DEPTH, style=style, placement='attached',
                    design=asdict(MemberDesign(style=style, variant=ORDERED[style],
                                               material='plaster', detail=2))))
    return pilasters


__all__ = ['plan_pilasters']
