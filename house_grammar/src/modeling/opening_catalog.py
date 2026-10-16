"""Single entry point for the linked window and door catalogs."""
from dataclasses import replace

from domain.models import DoorControls
from modeling.window_assembly import PROFILES, validate_window
from modeling.door_assembly import validate_door


def resolve_opening(op, style=None):
    """Complete catalog defaults, rejecting obsolete prefab-only designs.

    The original catalog JSONs contain prefab='legacy'. It is a serialization
    alias, never a dispatch to the removed constructor.
    """
    if op.kind in ('window','balcony_window'):
        if op.door is not None:
            raise ValueError('Window cannot carry a door catalog design')
        if op.prefab not in ('catalog','legacy','slim_window','storefront','open'):
            raise ValueError('Window prefab is not in catalogo_ventanas; select a catalog frame_profile')
        profile=op.frame_profile
        if style and profile not in (None,'auto',style):
            raise ValueError('Window style conflicts with building style')
        profile=style or ('moderno' if profile in (None,'auto') else profile)
        if profile not in PROFILES:
            raise ValueError('Unknown window catalog frame_profile')
        op=replace(op,frame_profile=profile,prefab='open' if op.prefab=='open' else 'catalog')
        validate_window(op)
        return op
    if op.kind in ('door','gate'):
        if op.door is None:
            if op.prefab not in ('catalog','legacy','wood_panel','metal_gate',
                                 'roller','storefront','open'):
                raise ValueError('Door prefab is not in catalogo_puertas; declare a door catalog design')
            # Legacy prefab names are read aliases: the emitted geometry is
            # always a catalog door, completed from the building style, keeping
            # each name's material/opacity intent (wood stays wood).
            alias = {'wood_panel': dict(construction='boards',leaf_material='wood'),
                     'metal_gate': dict(construction='panelled',leaf_material='metal'),
                     'roller': dict(construction='louvers',leaf_material='metal'),
                     'storefront': dict(construction='glazed'),
                     'open': dict(construction='grille',transom_infill='open'),
                     }.get(op.prefab, {})
            op=replace(op,door=DoorControls(model=style or 'moderno',**alias))
        model=op.door.model
        model=(style or 'moderno') if model=='auto' else model
        if style and model!=style:
            raise ValueError('Door style conflicts with building style')
        op=replace(op,door=replace(op.door,model=model),prefab='catalog')
        validate_door(op)
        return op
    raise ValueError('Unknown opening kind for window/door catalog')


def build_opening(mb,a,t,n,op):
    op=resolve_opening(op)
    if op.kind in ('door','gate'):
        from modeling.door_assembly import build_door
        build_door(mb,a,t,n,op)
    else:
        from modeling.window_assembly import build_window
        build_window(mb,a,t,n,op)
