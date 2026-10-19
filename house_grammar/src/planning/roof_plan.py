"""R5: roofs and eaves drawn from the catalog on each exposed storey top.

The exterior route used to stop at the wall head. This stage slabs every
exposed storey top: the top floor takes the roof its language asks for (a tiled
gable, a hipped or ridged shelter, a corrugated cover or a flat parapet azotea),
and any setback ledge left by a smaller upper storey becomes a flat terrace.
The eave projects only where the street envelope allows it, so a party wall
stays flush and the front may overhang its sidewalk.

A fronton (R4) is met, not crossed: its reserved volume is carved out of the
roof behind it and the junction is flashed. Matching the roof to the crown as a
true gable end is a later refinement.
"""
from dataclasses import asdict, replace

import numpy as np
from shapely.geometry import LineString, Polygon, shape
from shapely.ops import unary_union

from domain.architecture import ParcelContext
from domain.roof_details import EaveDesign, RoofDesign
from modeling.grammar import street_envelope
from modeling.mesh_builder import polygons
from modeling.roof_planes import faces, geometry, plan_faces
from planning.envelope import SLAB

ROOF_PRESET = {
    'republicano': dict(form='gable', covering='curved_tile', slope_deg=22., eave='profiled',
                        material='roof_tile', substrate='wood'),
    'barroco': dict(form='hip', covering='curved_tile', slope_deg=24., eave='cornice',
                    material='roof_tile', substrate='wood'),
    'clasico': dict(form='hip', covering='flat_tile', slope_deg=18., eave='cornice',
                    material='roof_tile', substrate='wood'),
    'madera': dict(form='gable', covering='corrugated', slope_deg=26., eave='exposed',
                   material='roof', substrate='wood'),
    'moderno': dict(form='flat', covering='panel', slope_deg=6., eave='clean',
                    material='roof', substrate='concrete', parapet_m=.55, cap='moulded'),
}
LEDGE_MIN_AREA = 1.5
MAIN_MIN_AREA = 6.0


def _style(request, body):
    for entry in request['building'].get('bodies', []) or []:
        if entry.get('id') == body and entry.get('style'):
            return entry['style']
    return request['building'].get('style', 'republicano')


def _design(style, main, area):
    preset = ROOF_PRESET.get(style, ROOF_PRESET['republicano'])
    if not main:
        return RoofDesign(form='flat', covering='panel', style=style, slope_deg=4.,
                          material='concrete', substrate_material='concrete', detail='medium',
                          eave=EaveDesign(kind='clean', overhang_m=0., fascia=False))
    overhang = 0. if preset['form'] == 'flat' else .45
    eave = EaveDesign(kind=preset['eave'], overhang_m=overhang, material='wood',
                      fascia_material='wood', fascia=overhang > 0.)
    module = .24 if area <= 60. else .30 if area <= 150. else .38
    return RoofDesign(form=preset['form'], covering=preset['covering'], construction='solid',
                      style=style, slope_deg=preset['slope_deg'], material=preset['material'],
                      substrate_material=preset['substrate'], eave=eave,
                      parapet_m=preset.get('parapet_m', 0.), cap=preset.get('cap', 'none'),
                      cap_material='stone', detail='medium', tile_width_m=module,
                      tile_length_m=round(module*1.9, 3), overlap_m=round(module*.35, 3))


def _surface(massing, surface_id):
    for row in massing['storeys']:
        for surface in row.get('surfaces', []):
            if surface['id'] == surface_id:
                return surface
    return None


def _crown_cut(massing, crown):
    """Rectangular volume behind a fronton, in world coordinates."""
    surface = _surface(massing, crown['host_surface_id'])
    if surface is None:
        return None, ()
    line = LineString(surface['line'])
    a = np.asarray(line.coords[0], float)
    t = (np.asarray(line.coords[-1], float)-a)/line.length
    n = np.asarray(surface['normal'], float)
    thickness = crown['design']['thickness_m']
    low = crown['axis_u_m']-crown['width_m']/2
    high = crown['axis_u_m']+crown['width_m']/2
    box = Polygon([a+t*u+n*v for u, v in ((low, -thickness-.035), (high, -thickness-.035),
                                          (high, 2.), (low, 2.))])
    return box, (a, t, n)


def _lines(geom):
    if geom.is_empty:
        return []
    if geom.geom_type in ('LineString', 'LinearRing'):
        coords = tuple(geom.coords)
        return [coords] if len(coords) >= 2 else []
    result = []
    for part in getattr(geom, 'geoms', ()):
        result += _lines(part)
    return result


def _street_envelope(context):
    return street_envelope(ParcelContext(
        tuple(map(tuple, context['parcel'])),
        explicit_fronts=tuple(sorted(set(context['fronts'].values())))))


def plan_roofs(plan):
    data = plan.to_dict() if hasattr(plan, 'to_dict') else plan
    massing = data['massing']
    envelope = _street_envelope(data['request']['context'])
    storeys = [row for row in massing['storeys'] if row['kind'] == 'enclosed']
    floors = {}
    for row in storeys:
        floors.setdefault(row['floor'], []).append(row)
    order = sorted(floors)
    if not order:
        return []
    union = {f: unary_union([shape(r['enclosed_geometry']) for r in floors[f]]) for f in order}
    highest = order[-1]
    roofs = []
    for index, floor in enumerate(order):
        upper = unary_union([union[f] for f in order[index+1:]]) if index+1 < len(order) else Polygon()
        exposed = union[floor].difference(upper) if not upper.is_empty else union[floor]
        if exposed.area < LEDGE_MIN_AREA:
            continue
        datum = max(r['top_m'] for r in floors[floor])-SLAB
        style = _style(data['request'], floors[floor][0]['body'])
        design = _design(style, floor == highest, union[floor].area)
        parts = list(exposed.geoms) if hasattr(exposed, 'geoms') else [exposed]
        for part in parts:
            if part.area < (MAIN_MIN_AREA if floor == highest else LEDGE_MIN_AREA):
                continue
            if design.form in ('hip', 'pavilion') and part.symmetric_difference(part.convex_hull).area > 1e-6:
                design = replace(design, form='gable')
            poly = part.buffer(design.eave.overhang_m, join_style=2)
            available = poly.difference(upper.buffer(.02)) if not upper.is_empty else poly
            available = available.intersection(envelope)
            joints = []
            junction = 'none'
            for crown in data.get('crowns', ()):
                if abs(crown['base_z_m']-datum) > 1e-6:
                    continue
                cut, _ = _crown_cut(massing, crown)
                if cut is None:
                    continue
                junction = 'behind'
                available = available.difference(cut)
                joints += _lines(available.boundary.intersection(cut.boundary))
            if available.is_empty or available.geom_type != 'Polygon':
                continue
            try:
                planned = plan_faces(poly, design, datum)
            except ValueError:
                continue
            ff = [patch for f in planned
                  for piece in polygons(geometry(f).intersection(available))
                  for patch in faces(piece, [f.plane])]
            if not ff:
                continue
            roofs.append(dict(id=f'{floors[floor][0]["body"]}/roof{floor}', body=floors[floor][0]['body'],
                              floor=floor, datum_m=round(datum, 6), style=style, junction=junction,
                              design=asdict(design),
                              support=tuple(tuple(p) for p in part.exterior.coords[:-1]),
                              faces=[dict(polygon=f.polygon, holes=f.holes, plane=f.plane) for f in ff],
                              wall_joints=joints))
    return roofs


__all__ = ['plan_roofs']
