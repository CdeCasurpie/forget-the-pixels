"""Exterior-first envelope: stair footprint, exterior apertures and wall solids.

Unlike the historic ``plan_envelope``, this route never calls ``plan_interiors``.
There are no room polygons, corridors, partitions or invisible door leaves.
Every articulated outdoor balcony/loggia receives a real facade door linked by
``access_for``; a window cannot stand in for that access.
"""
from dataclasses import dataclass, asdict
import math

import numpy as np
from shapely.geometry import LineString, Polygon, box, shape
from shapely.ops import unary_union

from planning.envelope import (EXTERIOR, SLAB, LINTEL, PROFILE_WIDTH, _design,
                               _joinery, _part, strip, validate_envelope,
                               window_dimensions)
from planning.exterior_program import plan_exterior_program
from planning.massing import clean, encode, fail, local, world


@dataclass
class ExteriorEnvelopePlan:
    version: str
    request: dict
    massing: dict
    program: dict
    core: dict
    openings: list
    parts: list
    decisions: list
    checks: dict

    def to_dict(self):
        return asdict(self)


def _stair_footprint(massing):
    """Reserve a single continuous stair void, not bathroom/room layouts."""
    floors = sorted({r['floor'] for r in massing['storeys'] if r['kind'] == 'enclosed'})
    if len(floors) < 2:
        return Polygon()
    frames = massing['fronts']
    primary = min(frames, key=lambda key: (-frames[key]['length_m'], key))
    frame = frames[primary]
    common = None
    for floor in floors:
        occupied = unary_union([shape(r['enclosed_geometry']) for r in massing['storeys']
                                if r['floor'] == floor and r['kind'] == 'enclosed'])
        usable = local(occupied, frame).buffer(-EXTERIOR, join_style=2)
        common = usable if common is None else common.intersection(usable)
    if common.is_empty:
        fail('vertical_core_fit', 'stairs', 'no shared stair footprint across floors')
    x0, y0, x1, y1 = common.bounds
    levels = massing['request']['context']['levels_m']
    rise = max(b-a for a, b in zip(levels, levels[1:]))
    length = max(3.4, (math.ceil(math.ceil(rise/.18)/2)-1)*.27 + 1.1)
    candidates = []
    for width, depth in ((2.2, length), (length, 2.2)):
        if x1-x0 < width+.2 or y1-y0 < depth+.2:continue
        # Prefer a lateral/rear stair, but allow an inner placement when a
        # courtyard or irregular bite makes either outer corner unusable.
        for x in np.linspace(x0+.1, x1-width-.1, 9):
            for y in np.linspace(y1-depth-.1, y0+.1, 9):
                candidates.append(box(x, y, x+width, y+depth))
    stair = next((candidate for candidate in candidates
                  if common.buffer(1e-7).covers(candidate)), None)
    if stair is None:
        fail('vertical_core_fit', 'stairs', 'no continuous 2.20 m stair fits the masses')
    return world(stair, frame)


def _segment(surface, u, width):
    line = LineString(surface['line'])
    a = np.asarray(line.coords[0], float)
    b = np.asarray(line.coords[-1], float)
    tangent = (b-a)/line.length
    return LineString([a+tangent*u, a+tangent*(u+width)])


def _accesses(row, surfaces):
    """Reserve a facade door at each outdoor-space landing, by actual contact."""
    found = []
    for space in row.get('spaces', []):
        if space['kind'] not in ('balcony', 'loggia', 'portico', 'vestibule'):
            continue
        landing = shape(space['access']['geometry'])
        candidates = [(LineString(s['line']).intersection(landing.buffer(1e-6)).length, s)
                      for s in surfaces]
        overlap, host = max(candidates, key=lambda item: item[0], default=(0., None))
        width = min(1.0, space['access']['width_m'], overlap-.02)
        if host is None or width < .8:
            fail('balcony_access', space['id'], 'no exterior wall supports a pedestrian door')
        line = LineString(host['line'])
        center = line.project(landing.centroid)
        start = max(.05, min(center-width/2, line.length-width-.05))
        door = _segment(host, start, width)
        if not landing.buffer(1e-6).intersects(door):
            fail('balcony_access', space['id'], 'door does not meet its landing')
        found.append((host, door, 'exterior_space', space['id']))
    return found


def _entrance(row, surfaces, request):
    """One ground entrance, independently of any interior room arrangement."""
    if row['floor'] != 1 or request['building'].get('site', {}).get('door') is False:
        return []
    available = [s for s in surfaces if s['front'] is not None and s['length_m'] >= 3.1]
    if not available:return []
    host = max(available, key=lambda s: (s['length_m'], s['id']))
    door = request['building'].get('site', {}).get('door', 'left')
    position = door.get('position', 'left') if isinstance(door, dict) else door
    width = 1.05
    start = (1.0 if position == 'left' else
             host['length_m']-1.0-width if position == 'right' else
             (host['length_m']-width)/2)
    return [(host, _segment(host, start, width), 'entrance', 'ground_entry')]


def _windows(row, surfaces, blocked, request, usage):
    """Small R2 facade prior. R3 will resolve full bay sizes and catalog frames."""
    floor = row['floor']; body = row['body']; selected = []
    declarations = [fac for fac in request['building'].get('facades', [])
                    if fac['body'] == body and floor in fac['floors']]
    for front in sorted({s['front'] for s in surfaces if s['front'] is not None}):
        matched = next((fac for fac in declarations if fac['front'] == front), None)
        if matched is not None and 'windows' in matched:
            count = matched['windows']['count']; proportions = matched['windows'].get('proportions')
            default_proportion = matched['windows'].get('proportion', 'vertical')
        elif declarations:  # explicit facade scopes close unlisted fronts
            continue
        else:
            count = 1 if usage in ('commercial', 'office') else 2
            proportions = None; default_proportion = 'vertical'
        if count == 0:continue
        candidates = []
        for surface in surfaces:
            if surface['front'] != front:continue
            free = LineString(surface['line']).difference(
                unary_union([door.buffer(.35, cap_style=2) for door in blocked])) if blocked else LineString(surface['line'])
            pieces = ([free] if free.geom_type == 'LineString' else
                      [p for p in getattr(free, 'geoms', ()) if p.geom_type == 'LineString'])
            for part in sorted(pieces, key=lambda p: p.wkt):
                if part.length >= 2.55:
                    candidates.append(dict(surface, line=list(part.coords), length_m=part.length,
                                           slot_id=f'{surface["id"]}/free{len(candidates)}'))
        allocation = {s['slot_id']: 0 for s in candidates}
        for _ in range(count):
            eligible = [s for s in candidates if
                        (s['length_m']-1.7)/(allocation[s['slot_id']]+1) >= .85]
            if not eligible:
                if matched is not None:fail('window_capacity', front, 'facade too short for requested windows')
                break
            chosen = max(eligible, key=lambda s: ((s['length_m']-1.7)/(allocation[s['slot_id']]+1), s['slot_id']))
            allocation[chosen['slot_id']] += 1
        index = 0
        for surface in candidates:
            n = allocation[surface['slot_id']]
            if not n:continue
            line = LineString(surface['line'])
            window_width = min(1.35, (line.length-1.7)/n)
            for i in range(n):
                start = .85 + (line.length-1.7)*(i+.5)/n-window_width/2
                candidate = _segment(surface, start, window_width)
                proportion = proportions[index] if proportions is not None else default_proportion
                selected.append((surface, candidate, 'window',
                                 (proportion, 'explicit' if matched is not None else 'completion')))
                index += 1
    return selected


def plan_exterior_envelope(request):
    """New exterior-only route; the historic interior route remains opt-in separately."""
    program_plan = plan_exterior_program(request)
    massing = program_plan.massing; request = program_plan.request
    levels = request['context']['levels_m']
    stair = _stair_footprint(massing)
    parts = []; openings = []; decisions = list(program_plan.decisions)
    uses = {s['id']: s['use'] for s in program_plan.storeys}
    for floor in range(1, len(levels)):
        rows = [r for r in massing['storeys'] if r['floor'] == floor and r['kind'] == 'enclosed']
        if not rows:continue
        bottom, top = levels[floor-1], levels[floor]-SLAB
        if top-bottom < 2.30:fail('useful_height', f'floor{floor}', 'less than 2.30 m below slab')
        full = unary_union([shape(row['enclosed_geometry']) for row in rows])
        inside = full.buffer(-EXTERIOR, join_style=2)
        outer = clean(full.difference(inside))
        current = []
        for row in rows:
            surfaces = [dict(s, body=row['body']) for s in row['surfaces'] if s['enclosure']]
            access = _accesses(row, surfaces) + _entrance(row, surfaces, request)
            requested = _windows(row, surfaces, [door for _, door, _, _ in access],
                                 request, uses[row['id']])
            for index, (surface, line, kind, source) in enumerate(access+requested):
                width = line.length
                proportion, provenance = source if kind == 'window' else (None, None)
                design = _design(request, surface, floor, kind,
                                 proportion)
                frame = PROFILE_WIDTH[design['style']]
                if kind == 'window':
                    sill, head, adapted = window_dimensions(width, proportion, 'shop' if uses[row['id']] == 'commercial' else 'living', top-bottom)
                    if adapted:decisions.append(dict(path=surface['id'], reason='window height limited by lintel'))
                else:
                    sill = 0.; head = min(2.15, top-bottom-LINTEL)
                inward = -np.asarray(surface['normal'], float)
                cut = strip(line, 0., width, -.01, EXTERIOR+.08, inward)
                if outer.intersection(cut).area < width*.04:
                    fail('opening_out_of_wall', surface['id'], 'opening has no exterior masonry')
                op = dict(id=f'{row["id"]}/{kind}{index}', kind=kind, floor=floor,
                           room=None, source='balcony_access' if kind == 'exterior_space' else 'entry' if kind == 'entrance' else provenance,
                           access_for=source if kind == 'exterior_space' else None,
                          geometry=encode(line), axis=encode(line), inward=inward.tolist(),
                          cut_geometry=encode(cut), width_m=width, bottom_m=bottom+sill,
                          top_m=bottom+head, sill_m=sill, head_m=head,
                          wall_thickness_m=EXTERIOR, frame_width_m=frame,
                          surface=surface['id'], body=row['body'], front=surface['front'],
                           proportion=proportion, **design)
                if kind != 'window' and width-2*frame < .70:
                    fail('door_clear_width', op['id'], 'insufficient pedestrian clearance')
                current.append(op)
        for i, op in enumerate(current):
            for other in current[:i]:
                if min(op['top_m'], other['top_m']) <= max(op['bottom_m'], other['bottom_m']):
                    continue
                if shape(op['cut_geometry']).intersection(shape(other['cut_geometry'])).area > 1e-5:
                    fail('opening_overlap', op['id'], other['id'])
        heights = sorted({bottom, top, *[v for op in current for v in (op['bottom_m'], op['top_m'])]})
        for i, (low, high) in enumerate(zip(heights, heights[1:])):
            active = [shape(op['cut_geometry']) for op in current
                      if op['bottom_m'] < (low+high)/2 < op['top_m']]
            _part(parts, f'floor{floor}/wall{i}', 'wall', 'plaster', floor,
                  clean(outer.difference(unary_union(active))), low, high)
        for op in current:_joinery(op, parts)
        openings.extend(current)
        for row in rows:
            for space in row.get('spaces', []):
                if space['protection']:
                    _part(parts, space['id']+'/parapet', 'parapet', 'plaster', floor,
                          shape(space['protection']), bottom,
                          bottom+space['protection_height_m'])
    for index, z in enumerate(levels):
        upper = [shape(r['geometry']) for r in massing['storeys'] if r['floor'] == index+1]
        lower = []
        for row in massing['storeys']:
            if row['floor'] != index:continue
            poly = shape(row['geometry'])
            for space in row.get('spaces', []):
                if not space['ceiling_thickness_m']:
                    poly = poly.difference(shape(space['geometry']))
            lower.append(poly)
        slab = clean(unary_union(upper+lower))
        if 0 < index < len(levels)-1 and not stair.is_empty:
            slab = clean(slab.difference(stair))
        _part(parts, f'level{index}/slab', 'slab', 'concrete', max(1, index),
              slab, z-SLAB, z)
    for support in massing['supports']:
        if support['kind'] == 'cantilever':continue
        high = support['top_m']-SLAB if support['kind'] == 'plinth' else support['top_m']
        _part(parts, support['id'], support['kind'], 'concrete', 1,
              shape(support['geometry']), support['bottom_m'], high)
    plan = ExteriorEnvelopePlan('exterior-envelope-v1', request, massing,
                                program_plan.program, dict(stairs=encode(stair)),
                                openings, parts, decisions, {})
    plan.checks = validate_envelope(plan)
    return plan
