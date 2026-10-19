"""R4: materialize planned crowns with the crown catalog.

Crown geometry is authored once, in ``modeling.crown_assembly``; this adapter
only places it on the reserved sector, using the host surface's own origin,
tangent and normal and the planned base height. It mirrors ``site_catalogue``
and ``catalogue_openings``: the planning stage decides, the catalog draws.
"""
import numpy as np
from shapely.geometry import LineString, Polygon

from domain.architecture import ParcelContext
from domain.crowns import CrownDesign
from modeling.crown_assembly import build_crown
from modeling.grammar import street_envelope
from modeling.mesh_builder import MeshBuilder

from planning.catalogue_openings import mesh_items
from planning.crown_plan import plan_crowns


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


def materialize_crowns(plan):
    data = plan.to_dict() if hasattr(plan, 'to_dict') else plan
    crowns = plan_crowns(data)
    context = data['request']['context']
    builder = MeshBuilder(Polygon(context['parcel']), envelope=_street_envelope(context))
    for crown in crowns:
        surface = _surface(data['massing'], crown['host_surface_id'])
        if surface is None:
            continue
        line = LineString(surface['line'])
        a = np.asarray(line.coords[0], float)
        t = (np.asarray(line.coords[-1], float)-a)/line.length
        n = -np.asarray(surface['normal'], float)
        with builder.assembly('crown/'+crown['id']):
            build_crown(builder, a, t, n, crown['axis_u_m']-crown['width_m']/2,
                        crown['base_z_m'], crown['width_m'], crown['height_m'],
                        CrownDesign(**crown['design']))
    return builder.finish()


__all__ = ['materialize_crowns', 'mesh_items']
