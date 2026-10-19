"""R5: contextual planting in a front garden or a generous balcony.

The lot's free area is not permission to scatter objects. Only an explicitly
reserved front garden/patio may carry a handful of pots, near its building
edge, after carving out the pedestrian and vehicle access corridors and fence.
The geometry comes from the existing roof planter prefab, also usable on the
ground. Only wide balconies with a real door carry corner pots, clear of the
access strip; ordinary streets and driveways remain uncluttered.
"""
import hashlib

import numpy as np
from shapely.geometry import LineString, Point, Polygon, box, shape

from domain.architecture import ParcelContext
from modeling.grammar import street_envelope
from modeling.mesh_builder import MeshBuilder
from modeling.prefabs_roof import planter
from planning.catalogue_openings import mesh_items


POT_WIDTH = .8
ROUTE_CLEARANCE = .45
FENCE_CLEARANCE = .4


def _garden_details(data):
    requested = data['request']['building'].get('site', {}).get('front_space')
    if not isinstance(requested, dict):
        # The massing may reserve a front strip to keep a requested fence from
        # touching the building. That is not a requested garden.
        return []
    reservations = data['massing']['site'].get('reservations', ())
    front = next((r for r in reservations if r['id'] == 'front_space'), None)
    if front is None or front.get('use') not in ('garden', 'patio', 'mixed'):
        return []
    site = data['site']
    free = shape(data['massing']['site']['free'])
    zone = shape(front['geometry']).intersection(free)
    if zone.area < 5.:
        return []
    for route in site['routes']:
        zone = zone.difference(shape(route['geometry']).buffer(ROUTE_CLEARANCE))
    if site['fence'] is not None:
        zone = zone.difference(shape(site['fence']['geometry']).buffer(FENCE_CLEARANCE))
    zone = zone.buffer(-.12, join_style=2)
    if zone.is_empty:
        return []
    front_name = requested['front']
    frame = data['massing']['fronts'][front_name]
    origin = np.asarray(frame['origin'], float)
    inward = np.asarray(frame['inward'], float)
    right = np.asarray(frame['right'], float)
    minx, miny, maxx, maxy = zone.bounds
    candidates = [(x, y) for x in np.arange(minx+.4, maxx, 1.2)
                  for y in np.arange(miny+.4, maxy, 1.2)]
    # Plant toward the house and then close to the side piers. This is a
    # grouping rule, not jittered uniform scatter in the accessible ground.
    candidates.sort(key=lambda xy: (-float((np.asarray(xy)-origin)@inward),
                                   min(float((np.asarray(xy)-origin)@right),
                                       frame['length_m']-float((np.asarray(xy)-origin)@right))))
    count = 2 if front['use'] == 'patio' else 3
    planted = []
    for x, y in candidates:
        footprint = box(x-POT_WIDTH/2, y-POT_WIDTH/2,
                        x+POT_WIDTH/2, y+POT_WIDTH/2)
        if not zone.covers(footprint):
            continue
        if any(Point(x, y).distance(Point(*row['position'])) < 1.35 for row in planted):
            continue
        index = len(planted)
        seed = int.from_bytes(hashlib.sha256(
            f'{data["request"].get("seed", 0)}:garden:{index}'.encode()).digest()[:4], 'little')
        planted.append(dict(id=f'site/planter{index}', kind='planter',
                            position=[round(float(x), 6), round(float(y), 6)],
                            footprint=footprint.__geo_interface__, scale=.85, seed=seed))
        if len(planted) >= count:
            break
    return planted


def _balcony_details(data):
    planted = []
    for row in data['massing']['storeys']:
        for space in row.get('spaces', ()):
            if space['kind'] != 'balcony' or space['depth_m'] < .9:
                continue
            floor = shape(space['geometry'])
            if floor.area < 4.:
                continue
            access = next((o for o in data['openings'] if o.get('access_for') == space['id']), None)
            if access is None:
                continue  # no object may occupy an inaccessible balcony
            door = shape(access['geometry']).centroid
            frame = data['massing']['fronts'][space['front']]
            inward = np.asarray(frame['inward'], float)
            # The route behind the door extends to the parapet, not just along
            # the door line. The guard receives its own clearance as well.
            walk = LineString([door, Point(door.x-inward[0]*space['depth_m'],
                                           door.y-inward[1]*space['depth_m'])])
            zone = floor.difference(walk.buffer(.55))
            if space.get('protection'):
                zone = zone.difference(shape(space['protection']).buffer(.08))
            zone = zone.buffer(-.04, join_style=2)
            if zone.is_empty:
                continue
            minx, miny, maxx, maxy = zone.bounds
            candidates = [(float(x), float(y)) for x in np.arange(minx+.21, maxx, .38)
                          for y in np.arange(miny+.21, maxy, .38)]
            candidates.sort(key=lambda xy: (-Point(*xy).distance(door), xy[0], xy[1]))
            for x, y in candidates:
                footprint = box(x-.21, y-.21, x+.21, y+.21)
                if not zone.covers(footprint):
                    continue
                if any(Point(x, y).distance(Point(*p['position'])) < 1.3 for p in planted
                       if p.get('space_id') == space['id']):
                    continue
                index = sum(p.get('space_id') == space['id'] for p in planted)
                seed = int.from_bytes(hashlib.sha256(
                    f'{data["request"].get("seed", 0)}:{space["id"]}:{index}'.encode()
                ).digest()[:4], 'little')
                planted.append(dict(id=f'{space["id"]}/planter{index}', kind='planter',
                                    space_id=space['id'], position=[round(x, 6), round(y, 6)],
                                    footprint=footprint.__geo_interface__,
                                    z_m=space['bottom_m'], scale=.55, seed=seed))
                if index >= 1:
                    break
    return planted


def plan_outdoor_details(plan):
    data = plan.to_dict() if hasattr(plan, 'to_dict') else plan
    if 'interior' in data:
        return []
    return _garden_details(data) + _balcony_details(data)


def materialize_outdoor_details(plan):
    data = plan.to_dict() if hasattr(plan, 'to_dict') else plan
    context = data['request']['context']
    envelope = street_envelope(ParcelContext(
        tuple(map(tuple, context['parcel'])),
        explicit_fronts=tuple(sorted(set(context['fronts'].values())))))
    builder = MeshBuilder(Polygon(context['parcel']), envelope=envelope)
    ground = float(context.get('ground_z_m', 0.))
    for record in plan_outdoor_details(data):
        with builder.assembly(record['id']):
            planter(builder, record['position'], record.get('z_m', ground), 0., record['scale'],
                    np.random.default_rng(record['seed']))
    return builder.finish()


__all__ = ['plan_outdoor_details', 'materialize_outdoor_details', 'mesh_items']
