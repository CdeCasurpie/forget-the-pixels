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
import hashlib

import numpy as np
from shapely.geometry import LineString, Polygon, shape
from shapely.ops import unary_union

from domain.architecture import ParcelContext
from domain.roof_details import EaveDesign, RoofDesign
from modeling.grammar import street_envelope
from modeling.mesh_builder import polygons
from modeling.roof_planes import faces, geometry, plan_faces
from modeling.roofscape import PROP_WEIGHTS, scatter_props
from planning.envelope import SLAB
from planning.massing import fail

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


def _design(style, main, area, controls=None):
    preset = ROOF_PRESET.get(style, ROOF_PRESET['republicano'])
    controls = controls or {}
    if not main:
        cover = controls.get('cover')
        if cover == 'tile':
            return RoofDesign(form='shed', covering='curved_tile', style=style, slope_deg=14.,
                              material='roof_tile', substrate_material='wood', detail='medium',
                              eave=EaveDesign(kind='exposed', overhang_m=.3, material='wood',
                                              fascia_material='wood'))
        if cover == 'corrugated':
            return RoofDesign(form='shed', covering='corrugated', style=style, slope_deg=12.,
                              material='roof', substrate_material='wood', detail='medium',
                              eave=EaveDesign(kind='exposed', overhang_m=.3, material='wood',
                                              fascia_material='wood'))
        return RoofDesign(form='flat', covering='panel', style=style, slope_deg=4.,
                          material='concrete', substrate_material='concrete', detail='medium',
                          eave=EaveDesign(kind='clean', overhang_m=0., fascia=False))
    overhang = 0. if preset['form'] == 'flat' else .45
    eave = EaveDesign(kind=preset['eave'], overhang_m=overhang, material='wood',
                      fascia_material='wood', fascia=overhang > 0.)
    form, covering = preset['form'], preset['covering']
    parapet, cap = preset.get('parapet_m', 0.), preset.get('cap', 'none')
    cover = controls.get('cover')
    if cover == 'slab' and form != 'flat':
        form, covering = 'flat', 'panel'
        parapet, cap = parapet or .55, 'moulded'
        eave = EaveDesign(kind='clean', overhang_m=0., fascia=False)
    elif cover == 'corrugated':
        covering = 'corrugated'
        if form == 'flat':
            form, parapet, cap = 'shed', 0., 'none'
            eave = EaveDesign(kind='clean', overhang_m=.30, fascia=True)
    elif cover == 'tile':
        covering = 'curved_tile'
        if form == 'flat':
            # Covering is independent of style: tiles need drainage and a
            # substrate, even on a building whose default roof is an azotea.
            form, parapet, cap = 'shed', 0., 'none'
            eave = EaveDesign(kind='clean', overhang_m=.30, fascia=True)
    elif cover == 'mixed':
        # A shallow tiled street band leaves the rear part of the roof flat.
        # The street-facing rotation and depth are resolved from the actual
        # parcel frame below, not from the style preset.
        form, covering, parapet, cap = 'band', 'curved_tile', 0., 'none'
        eave = EaveDesign(kind='clean', overhang_m=0., fascia=False)
    module = .24 if area <= 60. else .30 if area <= 150. else .38
    material = ('concrete' if cover == 'slab' else
                'roof_tile' if covering in ('curved_tile', 'flat_tile') else 'roof')
    substrate = 'concrete' if cover == 'slab' or form == 'flat' else 'wood'
    return RoofDesign(form=form, covering=covering, construction='solid',
                      style=style, slope_deg=(12. if cover == 'corrugated' and form == 'shed'
                                             else preset['slope_deg']), material=material,
                      substrate_material=substrate, eave=eave,
                      parapet_m=parapet if form == 'flat' else 0.,
                      cap=cap if form == 'flat' else 'none',
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


def _flat_props(data, flat, roof_id):
    """Azotea objects, with the stair head where the stair arrives."""
    controls = data['request']['building'].get('roof', {}) or {}
    if 'objects' in controls:
        kinds = controls['objects']
        if not kinds:
            return []
        weights = {kind: 1.0 for kind in kinds if kind != 'stair_bulkhead'}
    else:
        use = data['program'].get('use', 'residential')
        weights = {kind: weight for kind, weight in
                   PROP_WEIGHTS.get(use, PROP_WEIGHTS['residential']).items()
                   if kind != 'stair_bulkhead'}
    seed = int.from_bytes(hashlib.sha256(
        (str(data['request'].get('seed', 0))+roof_id).encode()).digest()[:4], 'little')
    rng = np.random.default_rng(seed)
    props = []
    usable = flat
    stair = data['core'].get('stairs')
    explicit = controls.get('objects')
    if stair is not None and (explicit is None or 'stair_bulkhead' in explicit):
        core = shape(stair)
        if core.intersects(flat) and core.intersection(flat).area > 1.0:
            centre = core.intersection(flat).representative_point()
            props.append(dict(kind='stair_bulkhead', position=[float(centre.x), float(centre.y)],
                              rotation_deg=0., scale=1., seed=int(rng.integers(0, 2**31-1))))
            usable = usable.difference(core.buffer(.25))
    if usable.area > 1.0 and weights:
        for prop in scatter_props(usable, weights, rng, density=.04, limit=6):
            props.append(dict(kind=prop.kind, position=[float(prop.position[0]), float(prop.position[1])],
                              rotation_deg=float(prop.rotation_deg), scale=float(prop.scale),
                              seed=int(prop.seed)))
    return props


def plan_roofs(plan):
    data = plan.to_dict() if hasattr(plan, 'to_dict') else plan
    massing = data['massing']
    envelope = _street_envelope(data['request']['context'])
    storeys = [row for row in massing['storeys'] if row['kind'] == 'enclosed']
    if not storeys:
        return []
    highest = {body: max(r['floor'] for r in storeys if r['body'] == body)
               for body in {r['body'] for r in storeys}}
    roofs = []
    for row in sorted(storeys, key=lambda r: (r['floor'], r['body'])):
        floor = row['floor']
        owner = shape(row['enclosed_geometry'])
        upper = unary_union([shape(r['enclosed_geometry']) for r in storeys
                             if r['floor'] > floor])
        exposed = owner.difference(upper) if not upper.is_empty else owner
        if exposed.area < LEDGE_MIN_AREA:
            continue
        datum = row['top_m']-SLAB
        style = _style(data['request'], row['body'])
        controls = data['request']['building'].get('roof', {}) or {}
        design = _design(style, floor == highest[row['body']], owner.area, controls)
        neighbors = unary_union([shape(r['enclosed_geometry']) for r in storeys
                                 if r['floor'] == floor and r['id'] != row['id']])
        parts = list(exposed.geoms) if hasattr(exposed, 'geoms') else [exposed]
        for part_index, part in enumerate(parts):
            if part.area < (MAIN_MIN_AREA if floor == highest[row['body']] else LEDGE_MIN_AREA):
                continue
            part_design = design
            if part_design.form == 'band':
                frame = massing['fronts'][sorted(massing['fronts'])[0]]
                inward = np.asarray(frame['inward'], float)
                axis = np.asarray(part.exterior.coords) @ inward
                depth = min(part_design.band_depth_m, (axis.max()-axis.min())*.45)
                part_design = replace(part_design, band_depth_m=depth,
                                      rotation_deg=float(np.degrees(np.arctan2(inward[1], inward[0]))))
            if part_design.form in ('hip', 'pavilion') and part.symmetric_difference(part.convex_hull).area > 1e-6:
                part_design = replace(part_design, form='gable')
            poly = part.buffer(part_design.eave.overhang_m, join_style=2)
            available = poly.difference(upper.buffer(.02)) if not upper.is_empty else poly
            if not neighbors.is_empty:
                available = available.difference(neighbors.buffer(.02))
            available = available.intersection(envelope)
            joints = []
            junction = 'none'
            for crown in data.get('crowns', ()):
                if abs(crown['base_z_m']-datum) > 1e-6:
                    continue
                cut, _ = _crown_cut(massing, crown)
                if cut is None or not available.intersects(cut):
                    continue
                junction = 'behind'
                available = available.difference(cut)
                joints += _lines(available.boundary.intersection(cut.boundary))
            roof_id = f'{row["body"]}/roof{floor}/part{part_index}'
            if available.is_empty or available.geom_type != 'Polygon':
                fail('roof_capacity', roof_id, 'no connected roof remains after crown and upper-mass reservations')
            try:
                planned = plan_faces(poly, part_design, datum)
            except ValueError as error:
                fail('roof_capacity', roof_id, str(error))
            ff = [patch for f in planned
                  for piece in polygons(geometry(f).intersection(available))
                  for patch in faces(piece, [f.plane])]
            if not ff:
                fail('roof_capacity', roof_id, 'no roof faces remain inside the permitted envelope')
            props = _flat_props(data, available, roof_id) if part_design.form == 'flat' else []
            roofs.append(dict(id=roof_id, body=row['body'],
                              floor=floor, datum_m=round(datum, 6), style=style, junction=junction,
                              design=asdict(part_design), props=props,
                              support=tuple(tuple(p) for p in part.exterior.coords[:-1]),
                              support_holes=[tuple(tuple(p) for p in ring.coords[:-1])
                                             for ring in part.interiors],
                              faces=[dict(polygon=f.polygon, holes=f.holes, plane=f.plane) for f in ff],
                              wall_joints=joints))
    return roofs


__all__ = ['plan_roofs']
