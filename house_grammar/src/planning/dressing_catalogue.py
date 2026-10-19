"""R5: draw the shallow window dressing with the facade builders.

The backdrop is a thin backing panel just behind the inner wall face; the
curtain is a fabric panel of the planned coverage hanging behind the glass,
both emitted with ``MeshBuilder.panel`` on the same facade frame as the
catalogue opening. No room, partition or furniture is authored.
"""
import numpy as np
from shapely.geometry import LineString, Polygon, box

from domain.architecture import ParcelContext
from modeling.grammar import street_envelope
from modeling.mesh_builder import MeshBuilder

from planning.catalogue_openings import mesh_items, opening_for_record
from planning.dressing_plan import plan_dressings


def _street_envelope(context):
    return street_envelope(ParcelContext(
        tuple(map(tuple, context['parcel'])),
        explicit_fronts=tuple(sorted(set(context['fronts'].values())))))


def _surface(massing, surface_id):
    for row in massing['storeys']:
        for surface in row.get('surfaces', []):
            if surface['id'] == surface_id:
                return surface
    return None


def materialize_dressings(plan):
    data = plan.to_dict() if hasattr(plan, 'to_dict') else plan
    specs = {d['id']: d for d in plan_dressings(data)}
    if not specs:
        return MeshBuilder(Polygon(data['request']['context']['parcel'])).finish()
    context = data['request']['context']
    builder = MeshBuilder(Polygon(context['parcel']), envelope=_street_envelope(context))
    for record in data['openings']:
        spec = specs.get(record['id'])
        if spec is None:
            continue
        host = _surface(data['massing'], record['surface'])
        if host is None:
            continue
        line = LineString(host['line'])
        a = np.asarray(line.coords[0], float)
        t = (np.asarray(line.coords[-1], float)-a)/line.length
        n = np.asarray(host['normal'], float)
        opening = opening_for_record(record, host)
        u0, z0 = opening.u_m, opening.v_m
        width, height = opening.width_m, opening.height_m
        wall = float(record.get('wall_thickness_m') or .30)
        with builder.assembly('dressing/'+record['id']):
            panel = box(u0, z0, u0+width, z0+height)
            builder.panel(a, t, n, [panel], -(wall+.05), -(wall+.03),
                          lambda *args: 'accent', 'window_backdrop')
            if spec['fraction'] > 0.:
                curtain = box(u0, z0, u0+width*spec['fraction'], z0+height)
                builder.panel(a, t, n, [curtain], -(opening.recess_m+.10),
                              -(opening.recess_m+.07), lambda *args: 'curtain',
                              'window_curtain')
    return builder.finish()


__all__ = ['materialize_dressings', 'mesh_items']
