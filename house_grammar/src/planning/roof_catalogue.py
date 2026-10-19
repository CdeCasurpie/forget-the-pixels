"""R5: materialize the planned roofs with the roof catalog.

Slabs, tiles, corrugations, ridges, fascia, gutters, rafters and parapet coping
all come from ``modeling.roof_assembly``; this adapter only restores each
planned assembly (its design, faces, support, datum and flashed joints) and
places it. It mirrors ``crown_catalogue`` and ``pilaster_catalogue``.
"""
from shapely.geometry import Polygon

import numpy as np

from domain.roof_details import EaveDesign, RoofDesign
from domain.vertical_members import MemberDesign
from modeling.mesh_builder import MeshBuilder
from modeling.prefabs_roof import BUILDERS
from modeling.roof_assembly import build_roof_assembly, timber
from modeling.roof_detail_resolver import ResolvedRoofAssembly
from modeling.roof_planes import RoofFace, height
from modeling.vertical_member_assembly import build_member

from planning.catalogue_openings import mesh_items
from planning.roof_plan import _street_envelope, plan_roofs


def _design(spec):
    controls = dict(spec['design'])
    eave = EaveDesign(**controls.pop('eave'))
    return RoofDesign(eave=eave, **controls)


def _faces(spec):
    return tuple(RoofFace(tuple(f['polygon']), tuple(tuple(h) for h in f['holes']),
                          tuple(f['plane'])) for f in spec['faces'])


def materialize_roofs(plan):
    data = plan.to_dict() if hasattr(plan, 'to_dict') else plan
    specs = plan_roofs(data)
    context = data['request']['context']
    envelope = _street_envelope(context)
    builder = MeshBuilder(Polygon(context['parcel']), envelope=envelope)
    for spec in specs:
        resolved = ResolvedRoofAssembly(
            id=spec['id'], mass_ref=spec['body'], design=_design(spec), faces=_faces(spec),
            support=tuple(tuple(p) for p in spec['support']), base_z=spec['datum_m'],
            support_holes=tuple(tuple(tuple(p) for p in ring)
                                for ring in spec.get('support_holes', ())),
            wall_joints=tuple(tuple(j) for j in spec['wall_joints']))
        # A parapet coping lips a few centimetres past its flush wall head; the
        # roof face itself is already clipped to the envelope.
        build_roof_assembly(builder, resolved, envelope.buffer(.2, join_style=2))
        for index, prop in enumerate(spec.get('props', ())):
            build_prop = BUILDERS.get(prop['kind'])
            if build_prop is None:
                continue
            with builder.assembly(f"{spec['id']}/prop_{prop['kind']}_{index:02d}"):
                build_prop(builder, prop['position'], spec['datum_m'], prop['rotation_deg'],
                           prop['scale'], np.random.default_rng(prop['seed']))
        shade = spec.get('shade')
        if shade:
            canopy = ResolvedRoofAssembly(
                id=shade['id'], mass_ref=spec['body'], design=_design(shade),
                faces=_faces(shade), support=tuple(shade['support']),
                base_z=shade['datum_m'], canopy=True, depth_m=2.,
                outward=tuple(shade['outward']), post_base_z=shade['post_base_m'])
            build_roof_assembly(builder, canopy, envelope)
            corners = np.asarray(shade['support'], float)
            centre = corners.mean(axis=0)
            outward = np.asarray(shade['outward'], float)
            tangent = np.array([outward[1], -outward[0]])
            plane = np.asarray(shade['faces'][0]['plane'], float)
            with builder.assembly(shade['id']+'/frame'):
                for a, b in zip(corners, np.roll(corners, -1, axis=0)):
                    timber(builder, (*a, height(plane, *a)-.08),
                           (*b, height(plane, *b)-.08), .14, .16, 'wood',
                           'roof_shade_beam')
                for point in corners:
                    post = centre+(point-centre)*.96
                    post_top = height(plane, *post)-.15
                    build_member(builder, post, tangent, outward,
                                 shade['post_base_m'], .14, .14,
                                 post_top-shade['post_base_m'],
                                 MemberDesign(style='madera', variant='saddle_post',
                                              material='wood', ornament=False),
                                 'freestanding')
    return builder.finish()


__all__ = ['materialize_roofs', 'mesh_items']
