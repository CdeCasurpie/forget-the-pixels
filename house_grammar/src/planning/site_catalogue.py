"""R4: materialize the exterior site with the fence catalog.

The site plan owns the fence run, its gates and the access routes. This adapter
turns those decisions into catalog pieces through ``modeling.fences.build_fence``
and lays the pavement each route needs, exactly as ``catalogue_openings``
assembles the openings. It authors no fence member of its own: the styled bars,
scrolls, pickets, louvers and plaques all come from the catalog.
"""
import math

import numpy as np
from shapely.geometry import LineString, Polygon, shape

from domain.architecture import ParcelContext
from modeling.boundaries import BoundarySpec
from modeling.fences import build_fence
from modeling.grammar import street_envelope
from modeling.mesh_builder import MeshBuilder

from planning.catalogue_openings import mesh_items
from planning.site_plan import FENCE_THICKNESS

DETAIL_Z = {'meter': (.28, .58), 'bell': (.88, .98), 'number': (1.60, 1.72)}
CAP_MATERIAL = {'plain': 'stone', 'tile': 'roof_tile', 'corrugated': 'roof'}


def _street_envelope(context):
    return street_envelope(ParcelContext(
        tuple(map(tuple, context['parcel'])),
        explicit_fronts=tuple(sorted(set(context['fronts'].values())))))


def _boundary(frame, fence, gates):
    """One catalog boundary spec for the whole front, gates already placed."""
    pedestrian = next((g for g in gates if g['kind'] == 'pedestrian'), None)
    vehicle = next((g for g in gates if g['kind'] == 'vehicle'), None)
    a = np.asarray(frame['origin'], float)
    t = np.asarray(frame['right'], float)
    length = frame['length_m']
    return BoundarySpec(
        line=LineString([a, a+t*length]),
        kind=fence['style'], height=fence['height_m'], form=fence['form'],
        gate_u=pedestrian['interval_m'][0] if pedestrian else None,
        gate_width=pedestrian['width_m'] if pedestrian else 0.,
        garage_u=vehicle['interval_m'][0] if vehicle else None,
        garage_width=vehicle['width_m'] if vehicle else 0.,
        is_street=True, height_mode='high' if fence['height_m'] > 1.6 else 'low')


def _fence(builder, massing, site):
    fence = site['fence']
    if not fence:
        return 0
    frame = massing['fronts'][fence['front']]
    a = np.asarray(frame['origin'], float)
    t = np.asarray(frame['right'], float)
    # ``build_fence`` places members along the outward normal (away from the
    # lot), so its negative depth reaches *into* the parcel.
    n = -np.asarray(frame['inward'], float)
    cap = fence.get('cap', 'plain')
    height = fence['height_m']
    with builder.assembly('site/fence'):
        build_fence(builder, a, t, n, frame['length_m'], _boundary(frame, fence, site['gates']))
        if cap != 'plain':
            # A continuous coping crowns each solid span, above its own wall.
            for low, high in fence['panels_m']:
                builder.box(a, t, n, low, high, height, height+.055,
                            -(FENCE_THICKNESS+.02), 0., CAP_MATERIAL[cap], 'fence_cap')
        for gate in site['gates']:
            low, high = gate['interval_m']
            if gate['kind'] == 'vehicle' and cap in ('tile', 'corrugated'):
                # A portal roof bridges the gate and bears on both jambs.
                builder.box(a, t, n, low-.075, high+.075, height, height+.085,
                            -.65, 0., CAP_MATERIAL[cap], 'gate_canopy')
        for detail in fence['details']:
            edge = shape(detail['geometry'])
            u = sorted(edge.project(shape({'type': 'Point', 'coordinates': list(p)}))
                       for p in edge.coords)
            low, high = DETAIL_Z[detail['id'].rsplit('/', 1)[-1]]
            builder.box(a, t, n, u[0], u[1], low, high,
                        -(FENCE_THICKNESS+.02), -FENCE_THICKNESS, 'metal', detail['id'])
    return len(site['gates'])


def _pavement(builder, route):
    footprint = shape(route['geometry'])
    if footprint.is_empty:
        return
    with builder.assembly(route['id']):
        builder.solid(footprint, -.08, 0., 'pavement', 'access_route')
        if route['transition'] == 'steps':
            axis = LineString(shape(route['axis']).coords)
            width = route['width_m']; level = route['rise_m']
            axis_t = (np.asarray(axis.coords[-1], float)-np.asarray(axis.coords[0], float))/axis.length
            normal = np.array([-axis_t[1], axis_t[0]])
            count = max(1, math.ceil(level/.17)); run = count*.32
            for i in range(count):
                lo = axis.length-run+i*.32; hi = lo+.32
                strip_ = LineString([np.asarray(axis.coords[0], float)+axis_t*lo,
                                     np.asarray(axis.coords[0], float)+axis_t*hi])
                builder.solid(strip_.buffer(width/2, cap_style=2, join_style=2),
                              0., level*(i+1)/count, 'concrete', 'step')


def materialize_site(plan):
    data = plan.to_dict() if hasattr(plan, 'to_dict') else plan
    site = data.get('site')
    if site is None:
        return MeshBuilder(Polygon(data['request']['context']['parcel'])).finish()
    context = data['request']['context']
    builder = MeshBuilder(Polygon(context['parcel']), envelope=_street_envelope(context))
    _fence(builder, data['massing'], site)
    for route in site['routes']:
        _pavement(builder, route)
    return builder.finish()


__all__ = ['materialize_site', 'mesh_items']
