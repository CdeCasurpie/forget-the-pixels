"""R5: materialize the planned roofs with the roof catalog.

Slabs, tiles, corrugations, ridges, fascia, gutters, rafters and parapet coping
all come from ``modeling.roof_assembly``; this adapter only restores each
planned assembly (its design, faces, support, datum and flashed joints) and
places it. It mirrors ``crown_catalogue`` and ``pilaster_catalogue``.
"""
from shapely.geometry import Polygon

from domain.roof_details import EaveDesign, RoofDesign
from modeling.mesh_builder import MeshBuilder
from modeling.roof_assembly import build_roof_assembly
from modeling.roof_detail_resolver import ResolvedRoofAssembly
from modeling.roof_planes import RoofFace

from planning.catalogue_openings import mesh_items
from planning.roof_plan import _street_envelope, plan_roofs


def _design(spec):
    controls = dict(spec['design'])
    eave = EaveDesign(**controls.pop('eave'))
    return RoofDesign(eave=eave, **controls)


def materialize_roofs(plan):
    data = plan.to_dict() if hasattr(plan, 'to_dict') else plan
    specs = plan_roofs(data)
    context = data['request']['context']
    envelope = _street_envelope(context)
    builder = MeshBuilder(Polygon(context['parcel']), envelope=envelope)
    for spec in specs:
        faces = tuple(RoofFace(tuple(f['polygon']), tuple(tuple(h) for h in f['holes']),
                               tuple(f['plane'])) for f in spec['faces'])
        resolved = ResolvedRoofAssembly(
            id=spec['id'], mass_ref=spec['body'], design=_design(spec), faces=faces,
            support=tuple(tuple(p) for p in spec['support']), base_z=spec['datum_m'],
            wall_joints=tuple(tuple(j) for j in spec['wall_joints']))
        # A parapet coping lips a few centimetres past its flush wall head; the
        # roof face itself is already clipped to the envelope.
        build_roof_assembly(builder, resolved, envelope.buffer(.2, join_style=2))
    return builder.finish()


__all__ = ['materialize_roofs', 'mesh_items']
