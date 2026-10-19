"""R4: materialize planned facade pilasters with the vertical-member catalog.

As ``crown_catalogue`` does for crowns, this adapter authors no member of its
own: the section, base, capital, shaft, collar and ornament all come from
``modeling.vertical_member_assembly.build_member``. It only anchors each one on
its host surface, offset outwards by half its depth so the back face bears on
the wall, exactly as the resolver does for a facade member.
"""
import numpy as np
from shapely.geometry import LineString, Polygon

from domain.architecture import ParcelContext
from domain.vertical_members import MemberDesign
from modeling.grammar import street_envelope
from modeling.mesh_builder import MeshBuilder
from modeling.vertical_member_assembly import build_member

from planning.catalogue_openings import mesh_items
from planning.pilaster_plan import plan_pilasters


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


def materialize_pilasters(plan):
    data = plan.to_dict() if hasattr(plan, 'to_dict') else plan
    specs = plan_pilasters(data)
    if not specs:
        return MeshBuilder(Polygon(data['request']['context']['parcel'])).finish()
    context = data['request']['context']
    builder = MeshBuilder(Polygon(context['parcel']), envelope=_street_envelope(context))
    for spec in specs:
        surface = _surface(data['massing'], spec['surface_id'])
        if surface is None:
            continue
        line = LineString(surface['line'])
        a = np.asarray(line.coords[0], float)
        t = (np.asarray(line.coords[-1], float)-a)/line.length
        n = np.asarray(surface['normal'], float)
        center = a + t*spec['u_m'] + n*(spec['depth_m']/2)
        with builder.assembly('pilaster/'+spec['id']):
            build_member(builder, center, t, n, spec['bottom_m'], spec['width_m'],
                         spec['depth_m'], spec['height_m'], MemberDesign(**spec['design']),
                         spec['placement'])
    return builder.finish()


__all__ = ['materialize_pilasters', 'mesh_items']
