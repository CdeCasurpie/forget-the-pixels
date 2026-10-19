"""Materialize exterior apertures with the existing door/window catalog.

The facade plan owns the opening's metric line and height. This adapter only
turns that already-cut aperture into a catalog Opening and calls the existing
``build_opening`` assembler; it does not author a second joinery mesh.
"""
import numpy as np
import trimesh
from shapely.geometry import LineString, Polygon, shape

from domain.models import DoorControls, Opening
from modeling.mesh_builder import MeshBuilder
from modeling.opening_catalog import build_opening, resolve_opening
from planning.envelope import EXTERIOR


def opening_for_record(record, host):
    """The same catalog contour used for both the masonry cut and assembly."""
    line = LineString(host['line'])
    opening_line = shape(record['geometry'])
    u = sorted(line.project(shape({'type': 'Point', 'coordinates': list(p)}))
               for p in opening_line.coords)
    if abs(u[1]-u[0]-record['width_m']) > 1e-5:
        raise ValueError(f'{record["id"]}: opening does not lie on its catalog facade')
    window = record['kind'] == 'window'
    style = record['style']
    catalogue = Opening(
        kind='window' if window else 'door', u_m=u[0],
        v_m=record['bottom_m'],  # MeshBuilder panels use absolute world Z.
        width_m=record['width_m'], height_m=record['top_m']-record['bottom_m'],
        frame_width_m=record['frame_width_m'], frame_depth_m=.10 if window else .12,
        recess_m=.08 if window else .12,
        frame_profile=style if window else None,
        frame_material=({'wood':'wood','metal':'metal','pvc':'plastic'}
                        .get(record['material']) if window else None),
        prefab='catalog', source=record['source'], sill=record.get('sill', window),
        shape=record.get('shape','rectangle'), arch_rise_m=record.get('arch_rise_m'),
        grille=record.get('grille',False), grille_pattern=record.get('grille_pattern','vertical'),
        door=None if window else DoorControls(
            model=style,
            frame_material=('metal' if record['material']=='glass' else
                            record['material'] if record['material'] in ('wood','metal') else 'auto'),
            construction='glazed' if record['source'] == 'balcony_access' or
                           record['use'] == 'commercial' or
                           record['material'] == 'glass' else 'auto',
            transom_height_m=.35 if record.get('transom','none') != 'none' else 0.,
            transom_infill='open' if record.get('transom') == 'open' else 'glass',
            portal=record.get('portal','none')))
    return resolve_opening(catalogue, style)


def materialize_openings(plan):
    data = plan.to_dict() if hasattr(plan, 'to_dict') else plan
    context = data['request']['context']
    parcel = Polygon(context['parcel'])
    builder = MeshBuilder(parcel)
    hosts = {surface['id']: surface for row in data['massing']['storeys']
             for surface in row['surfaces']}
    for record in data['openings']:
        host = hosts[record['surface']]
        line = LineString(host['line'])
        catalogue = opening_for_record(record, host)
        a = np.asarray(line.coords[0], float)
        tangent = (np.asarray(line.coords[-1], float)-a)/line.length
        normal = np.asarray(host['normal'], float)
        with builder.assembly('opening/' + record['id']):
            build_opening(builder, a, tangent, normal, catalogue)
    return builder.finish()


def materialize_contoured_walls(plan):
    """Existing exact panel extrusion: one closed shell with real curved holes."""
    data = plan.to_dict() if hasattr(plan, 'to_dict') else plan
    builder = MeshBuilder(Polygon(data['request']['context']['parcel']))
    for wall in data.get('contoured_walls', ()):
        line = LineString(wall['line'])
        origin = np.asarray(line.coords[0], float)
        tangent = (np.asarray(line.coords[-1], float)-origin)/line.length
        with builder.assembly('wall/' + wall['id']):
            builder.panel(origin, tangent, np.asarray(wall['normal'],float),
                          [shape(wall['domain'])], -EXTERIOR, 0.,
                          lambda *args:'plaster', 'wall', clip='parcel')
    return builder.finish()


def mesh_items(mesh, prefix='catalogue'):
    """Material-grouped triangles for the existing GLB and z-buffer exporter."""
    for index in np.unique(mesh.face_materials):
        material = mesh.materials[int(index)]['name']
        faces = mesh.faces[mesh.face_materials == index]
        yield prefix + '/' + material, material, trimesh.Trimesh(
            vertices=mesh.vertices, faces=faces, process=False)
