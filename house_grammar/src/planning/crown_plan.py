"""R4: crown (fronton) planning anchored to its reserved facade sector.

The envelope reserves one host panel per requested crown (R2) and records the
sector's opening axes. This stage turns that reservation into a dimensioned
crown tied to those axes, the panel span and the wall top, instead of a fixed
triangle centred on the facade: the width comes from the outermost reserved
window axes, the height follows the family, and the style only chooses the
family and its ornament. R5 owns the meeting with the roof.
"""
from dataclasses import asdict, replace

import numpy as np
from shapely.geometry import LineString, Point, shape

from domain.crowns import CrownDesign
from modeling.crown_catalog import classify
from modeling.crown_paths import validate
from planning.envelope import EXTERIOR, SLAB
from planning.massing import fail

CROWN_PRESET = {
    'republicano': dict(family='auto', silhouette='angular', ornament='keystone'),
    'clasico': dict(family='auto', silhouette='angular', ornament='dentils'),
    'barroco': dict(family='auto', silhouette='mixed', ornament='volutes', detail=3),
    'madera': dict(family='stepped', silhouette='angular', ornament='none'),
    'moderno': dict(family='stepped', silhouette='angular', ornament='none'),
}
RISE = {'triangular': .50, 'segmental': .30, 'compound_curve': .42, 'curved_pointed': .45,
        'stepped': .30, 'stepped_segmental': .34, 'concave_shoulders': .40,
        'rectangular_attic': .34, 'broken': .36}
AXIS_MARGIN = .35
MIN_WIDTH, MAX_HEIGHT = .90, 2.60


def _style(request, body):
    for entry in request['building'].get('bodies', []) or []:
        if entry.get('id') == body and entry.get('style'):
            return entry['style']
    return request['building'].get('style', 'republicano')


def _surface(massing, surface_id):
    for row in massing['storeys']:
        for surface in row.get('surfaces', []):
            if surface['id'] == surface_id:
                return row, surface
    fail('crown_host', surface_id, 'crown host surface disappeared')


def _span(frame, line, support, openings, surface_id):
    """Reserved span narrowed to the outermost window axes of its own panel."""
    origin = np.asarray(frame['origin'], float)
    right = np.asarray(frame['right'], float)
    project = lambda u: line.project(Point(origin+right*u))
    low, high = sorted((project(support[0]), project(support[1])))
    axes = []
    for op in openings:
        if op['surface'] != surface_id:
            continue
        seg = shape(op['geometry'])
        ends = sorted(line.project(Point(p)) for p in seg.coords)
        axes.append((ends[0], ends[1]))
    if axes:
        low = max(low, min(a for a, _ in axes)-AXIS_MARGIN)
        high = min(high, max(b for _, b in axes)+AXIS_MARGIN)
    return low, high


def _design(style, width):
    preset = CROWN_PRESET.get(style, CROWN_PRESET['republicano'])
    design = CrownDesign(family=preset['family'], style=style,
                         silhouette=preset['silhouette'], ornament=preset['ornament'],
                         detail=preset.get('detail', 2), thickness_m=.30, recess_m=.055,
                         moulding_width_m=.16, projection_m=.16,
                         material='plaster', moulding_material='stone')
    family, _ = classify(design)
    height = min(max(RISE.get(family, .40)*width, .60), MAX_HEIGHT)
    design = replace(design, family=family,
                     moulding_width_m=min(design.moulding_width_m, width*.18, height*.48, .5))
    try:
        validate(design, width, height)
    except ValueError as error:
        fail('crown_capacity', family, str(error))
    return design, height


def plan_crowns(plan):
    data = plan.to_dict() if hasattr(plan, 'to_dict') else plan
    massing = data['massing']
    frames = massing['fronts']
    crowns = []
    for crown in data.get('facade', {}).get('coronations', ()):
        row, surface = _surface(massing, crown['host_surface_id'])
        line = LineString(surface['line'])
        if line.length < MIN_WIDTH+2*EXTERIOR:
            fail('crown_host', crown['id'], 'host panel is too short for a crown')
        low, high = _span(frames[surface['front']], line, crown['support_span_m'],
                          data['openings'], surface['id'])
        width = high-low
        if width < MIN_WIDTH:
            fail('crown_capacity', crown['id'],
                 'no span between the reserved window axes fits a crown')
        design, height = _design(_style(data['request'], row['body']), width)
        crowns.append(dict(id=crown['id'], sector_id=crown['sector_id'],
                           host_surface_id=surface['id'],
                           axis_u_m=round((low+high)/2, 6), width_m=round(width, 6),
                           height_m=round(height, 6),
                           base_z_m=round(row['top_m']-SLAB, 6), design=asdict(design)))
    return crowns


__all__ = ['plan_crowns']
