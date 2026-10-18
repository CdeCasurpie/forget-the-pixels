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
            prefab='catalog', source=record['source'], sill=window,
            door=None if window else DoorControls(
                model=style,
                frame_material=('metal' if record['material']=='glass' else
                                record['material'] if record['material'] in ('wood','metal') else 'auto'),
                construction='glazed' if record['source'] == 'balcony_access' or
                               record['use'] == 'commercial' or
                               record['material'] == 'glass' else 'auto'))
        catalogue = resolve_opening(catalogue, style)
        a = np.asarray(line.coords[0], float)
        tangent = (np.asarray(line.coords[-1], float)-a)/line.length
        normal = np.asarray(host['normal'], float)
        with builder.assembly('opening/' + record['id']):
            build_opening(builder, a, tangent, normal, catalogue)
    return builder.finish()


def mesh_items(mesh):
    """Material-grouped triangles for the existing GLB and z-buffer exporter."""
    for index in np.unique(mesh.face_materials):
        material = mesh.materials[int(index)]['name']
        faces = mesh.faces[mesh.face_materials == index]
        yield 'catalogue/' + material, material, trimesh.Trimesh(
            vertices=mesh.vertices, faces=faces, process=False)
