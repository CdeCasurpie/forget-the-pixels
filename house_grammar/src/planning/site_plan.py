"""R4: exterior site planning — the lot edge, its fence, gates and access.

The building envelope owns the entrance. This stage reads the planned ground
openings and the parcel front, decides the fence run and its gates, and reserves
the free ground a route needs. It authors no fence mesh: the enclosing pieces
come from the fence catalog at export time (``site_catalogue``), so the same
style vocabulary is shared with the rest of the grammar.

The fence *form* is a physical axis independent of the local *style*: a solid
wall, an open infill or a tall base with a rail are chosen here, and the style
only ornaments the infill. A requested cochera resolves to a shared vehicle gate
and does not force a second pedestrian leaf.
"""
from dataclasses import dataclass, asdict
import math

import numpy as np
from shapely.geometry import LineString, Point, Polygon, shape

from planning.massing import encode, fail, local

FENCE_THICKNESS = .16
FENCE_HEIGHT = {'low': 1.15, 'high': 2.20}
ACCESS_WIDTH = {'pedestrian': .82, 'vehicle': 2.20}
GATE_WIDTH = {'pedestrian': 1.02, 'vehicle': 2.72}
GATE_EDGE = .13
GATE_PIER = .25
DETAILS = ('meter', 'bell', 'number')


@dataclass
class ExteriorSitePlan:
    version: str
    request: dict
    fence: dict | None
    gates: list
    accesses: list
    routes: list
    decisions: list
    checks: dict

    def to_dict(self):
        return asdict(self)


def _line(frame, start, end, depth=0.):
    a = np.asarray(frame['origin'], float)
    t = np.asarray(frame['right'], float)
    n = np.asarray(frame['inward'], float)
    return LineString([a+t*start+n*depth, a+t*end+n*depth])


def _intervals(length, openings, form):
    """Fence panel intervals, excluding openings; a partial fence has a gap."""
    solids = [(0., length)] if form != 'partial' else [(0., length*.38), (length*.62, length)]
    for left, right in sorted(openings):
        solids = [piece for a, b in solids for piece in ((a, min(left, b)), (max(right, a), b))
                  if piece[1]-piece[0] > 1e-5]
    return solids


def _route(route_id, kind, start, end, free, occupied, level):
    width = ACCESS_WIDTH[kind]
    axis = LineString([start, end]); distance = axis.length
    if distance < .015:
        if level > .02:
            fail('access_run', route_id, 'raised building at the street edge has no space for a transition')
        return dict(id=route_id, kind=kind, axis=encode(axis), geometry=encode(Polygon()),
                    width_m=width, length_m=distance, rise_m=level, transition='direct')
    footprint = axis.buffer(width/2, cap_style=2, join_style=2)
    if not free.buffer(1e-5).covers(footprint):
        if distance <= .35:
            # A building sitting on the street line has no free strip to pave.
            return dict(id=route_id, kind=kind, axis=encode(axis), geometry=encode(Polygon()),
                        width_m=width, length_m=distance, rise_m=level, transition='direct')
        fail('access_outside_free', route_id, 'passage does not fit in the free ground')
    if footprint.intersection(occupied).area > 1e-4:
        fail('access_blocked', route_id, 'ground mass or column blocks the route')
    transition = 'level'
    if level > .02:
        if distance >= level*12+1.:
            transition = 'ramp'
        else:
            count = max(1, math.ceil(level/.17)); run = count*.32
            if distance < run+.25:
                fail('access_run', route_id, 'insufficient parcel run for steps or a compliant ramp')
            transition = 'steps'
    return dict(id=route_id, kind=kind, axis=encode(axis), geometry=encode(footprint),
                width_m=width, length_m=distance, rise_m=level, transition=transition)


def _front_space(massing):
    for reservation in massing['site'].get('reservations', ()):
        if reservation.get('id') == 'front_space':
            return shape(reservation['geometry'])
    return None


def _details(frame, gate, height, style):
    """Device plates on the inward face beside the gate, out of its clearance."""
    if gate is None:
        return []
    a, b = gate['interval_m']; length = frame['length_m']
    center = b+.12 if b+.35 < length else a-.12
    plates = []
    for name in DETAILS:
        width = {'meter': .17, 'bell': .075, 'number': .18}[name]
        plates.append(dict(id='site/detail/'+name, anchor_id=gate['id'], style=style,
                           geometry=encode(_line(frame, center-width/2, center+width/2,
                                                 FENCE_THICKNESS+.01))))
    return plates


def plan_site(plan):
    data = plan.to_dict() if hasattr(plan, 'to_dict') else plan
    request = data['request']; site = request['building'].get('site', {})
    massing = data['massing']; frames = massing['fronts']
    free = shape(massing['site']['free']); occupied = shape(massing['site']['occupied'])
    level = request['context']['levels_m'][0]
    decisions = []
    targets = [o for o in data['openings']
               if o['floor'] == 1 and o['kind'] in ('entrance', 'vehicle_entry')]
    pedestrian = next((o for o in targets if o['kind'] == 'entrance'), None)
    vehicle = next((o for o in targets if o['kind'] == 'vehicle_entry'), None)
    garage = site.get('garage')
    # A requested cochera is a shared street access even without a building opening.
    wanted_vehicle = vehicle is not None or bool(garage)
    fencespec = site.get('fence')
    if fencespec is False:
        fencespec = None
        decisions.append(dict(path='site.fence', reason='explicit absence respected', source='explicit'))
    elif fencespec is None and site.get('front_space'):
        fencespec = dict(front=site['front_space']['front'], form='open', height='low')
        decisions.append(dict(path='site.fence',
                              reason='low open boundary for requested front garden',
                              source='completion'))
    if fencespec:
        access_front = fencespec['front']
    elif pedestrian is not None:
        access_front = pedestrian.get('front') or next(iter(frames))
    elif vehicle is not None:
        access_front = vehicle.get('front') or next(iter(frames))
    else:
        access_front = max(frames, key=lambda f: frames[f]['length_m'])
    if access_front not in frames:
        fail('site_front', access_front, 'unknown parcel front for the site plan')
    fence = None; gates = []
    if fencespec:
        front = fencespec['front'] if fencespec['front'] in frames else access_front
        frame = frames[front]; length = frame['length_m']
        form = fencespec.get('form', 'open')
        height = FENCE_HEIGHT[fencespec.get('height', 'low')]
        cap = fencespec.get('cap', 'plain')
        style = fencespec.get('style', request['building'].get('style', 'moderno'))
        intervals = []

        def place(name, center, width):
            spans = [(GATE_EDGE, length-GATE_EDGE)]
            for a, b in intervals:
                spans = [piece for lo, hi in spans
                         for piece in ((lo, a-GATE_PIER), (b+GATE_PIER, hi))
                         if piece[1]-piece[0] >= width]
            if not spans:
                fail('gate_capacity', name, 'no fence span fits the gate and its piers')
            inside = [piece for piece in spans if piece[0] <= center <= piece[1]]
            a, b = (min(inside, key=lambda piece: abs((piece[0]+piece[1])/2-center))
                    if inside else max(spans, key=lambda piece: (piece[1]-piece[0], -piece[0])))
            center = max(a+width/2, min(b-width/2, center))
            interval = (center-width/2, center+width/2)
            intervals.append(interval)
            return interval

        if pedestrian is not None:
            width = GATE_WIDTH['pedestrian']
            center = local(shape(pedestrian['geometry']).centroid, frame).x
            interval = place('site/pedestrian_gate', center, width)
            door = site.get('door', {})
            if not isinstance(door, dict):
                door = {}
            gates.append(dict(id='site/pedestrian_gate', kind='pedestrian', front=front,
                              interval_m=list(interval), width_m=width,
                              material=door.get('material', 'metal'),
                              style=door.get('style', style), shared=False,
                              geometry=encode(_line(frame, *interval))))
        if wanted_vehicle:
            width = GATE_WIDTH['vehicle']
            if vehicle is not None:
                # The street gate must line up with the building's vehicle door.
                center = local(shape(vehicle['geometry']).centroid, frame).x
            else:
                center = length-GATE_EDGE-width/2
                if isinstance(garage, str):
                    center = {'left': GATE_EDGE+width/2, 'center': length/2,
                              'right': length-GATE_EDGE-width/2}[garage]
            interval = place('site/vehicle_gate', center, width)
            gates.append(dict(id='site/vehicle_gate', kind='vehicle', front=front,
                              interval_m=list(interval), width_m=width, material='metal',
                              style=style, shared=vehicle is None,
                              geometry=encode(_line(frame, *interval))))
            if vehicle is None:
                decisions.append(dict(path='site.garage',
                                      reason='shared cochera gate without a second pedestrian door',
                                      source='completion'))
        panels = _intervals(length, intervals, form)
        thickness = _line(frame, 0, length).buffer(FENCE_THICKNESS/2, cap_style=2)
        if thickness.intersection(occupied.buffer(-1e-6)).area > 1e-4:
            fail('fence_blocked', 'site.fence', 'building mass reaches the fence')
        fence = dict(front=front, form=form, height_m=height, cap=cap, style=style,
                     geometry=encode(_line(frame, 0, length)), panels_m=panels,
                     details=_details(frame, next((g for g in gates if g['kind'] == 'pedestrian'),
                                                  gates[0] if gates else None), height, style))
    accesses = []; routes = []
    front_space = _front_space(massing)
    frame = frames[access_front]
    inward = np.asarray(frame['inward'], float)

    def make_access(kind, gate, target):
        route_id = 'site/'+kind+'_access/route'
        if gate is not None:
            center = sum(gate['interval_m'])/2
            start = _line(frame, center, center, FENCE_THICKNESS/2).centroid
            from_id = gate['id']
        else:
            center = (local(shape(target['geometry']).centroid, frame).x
                      if target is not None else frame['length_m']/2)
            start = _line(frame, center, center, 0.).centroid
            from_id = 'street/'+access_front
        if target is not None:
            end = shape(target['geometry']).centroid
        elif front_space is not None:
            # A cochera without a building door drives straight into the lot.
            end = Point(start.coords[0][0], front_space.centroid.y)
        else:
            end = Point(start.coords[0][0] + inward[0]*3., start.coords[0][1] + inward[1]*3.)
        route = _route(route_id, kind, start.coords[0], end.coords[0], free, occupied, level)
        routes.append(route)
        clear = 2.10 if kind == 'vehicle' else .75
        open_clear = (gate['width_m']-2*.05) if gate is not None else GATE_WIDTH[kind]
        if target is not None:
            open_clear = min(open_clear, target['width_m']-2*target['frame_width_m'])
        if open_clear < clear:
            fail('access_clear_width', gate['id'] if gate else route_id,
                 'insufficient clear passage')
        accesses.append(dict(id='site/'+kind+'_access', kind=kind, from_id=from_id,
                             to_id=target['id'] if target is not None else 'site/front_space',
                             route_id=route_id, clear_width_m=open_clear))

    ped_gate = next((g for g in gates if g['kind'] == 'pedestrian'), None)
    veh_gate = next((g for g in gates if g['kind'] == 'vehicle'), None)
    if pedestrian is not None:
        make_access('pedestrian', ped_gate, pedestrian)
    if wanted_vehicle:
        make_access('vehicle', veh_gate, vehicle)
    plan_ = ExteriorSitePlan('exterior-site-v1', request, fence, gates, accesses, routes, decisions, {})
    plan_.checks = validate_site(plan_)
    return plan_


def validate_site(plan):
    parcel = Polygon(plan.request['context']['parcel'])
    if plan.fence is not None:
        if not parcel.buffer(1e-6).covers(shape(plan.fence['geometry'])):
            fail('site_outside_parcel', 'site.fence', 'fence leaves the parcel')
    if len({a['kind'] for a in plan.accesses}) != len(plan.accesses):
        fail('duplicate_access', 'site', 'more than one street access for a kind')
    for access in plan.accesses:
        route = next(r for r in plan.routes if r['id'] == access['route_id'])
        if access['clear_width_m'] < (.75 if access['kind'] == 'pedestrian' else 2.10):
            fail('access_clear_width', access['id'], 'insufficient clear passage')
        if route['transition'] == 'ramp' and route['rise_m']/route['length_m'] > 1/12+1e-9:
            fail('ramp_slope', route['id'], 'ramp steeper than 1:12')
    return dict(parcel_containment=True, accesses_connected=True,
                fence_absent=plan.fence is None, ground_routes=len(plan.routes),
                engineering_verified=False)
