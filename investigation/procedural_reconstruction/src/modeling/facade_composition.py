"""Canonical theta-candidate composer in a local facade chart.

Consumes completed FacadeControls. No context, massing, exposure or world
coordinates belong here. Both base walls and FacadeZone use this entry point.
The legacy composer remains separate; shared family relief is reused unchanged.
"""
from dataclasses import dataclass, replace
import math
from typing import NamedTuple

import numpy as np
from shapely.geometry import box as rect

from domain.models import Opening, FacadeProjection, FacadeMaterialRegion
from domain.theta import FacadeControls
from modeling.detail import DetailBudget
from modeling.facade_program import FAMILY_RULES, compose_relief


class FacadeComposition(NamedTuple):
    axes_m: tuple[float, ...]
    openings: tuple[Opening, ...]
    projections: tuple[FacadeProjection, ...]
    material_regions: tuple[FacadeMaterialRegion, ...]


def _check(condition, message):
    if not condition:
        raise ValueError(message)


def validate_crowns(c):
    previous=0.
    for crown in c.crowns:
        u0,u1=crown.u
        _check(math.isfinite(u0) and math.isfinite(u1) and 0<=u0<u1<=1,
               'Invalid CrownProfile u interval')
        _check(u0>=previous, 'CrownProfiles must be ordered without overlap')
        _check(crown.kind in ('triangular','stepped'), 'Invalid CrownProfile kind')
        _check(math.isfinite(crown.height_m) and .20<=crown.height_m<=3.,
               'Invalid CrownProfile height_m')
        _check(math.isfinite(crown.depth_m) and .05<=crown.depth_m<=.8,
               'Invalid CrownProfile depth_m')
        previous=u1


def _crown_projections(c, length, height):
    validate_crowns(c)
    return tuple(FacadeProjection('crown_'+x.kind,length*x.u[0],height,
                                  length*(x.u[1]-x.u[0]),x.height_m,x.depth_m,
                                  material_slot='plaster',source='crown_profile')
                 for x in c.crowns)


@dataclass(frozen=True)
class ResolvedBay:
    axis_m: float
    pitch_m: float
    start_m: float
    end_m: float
    group_index: int
    local_index: int
    global_index: int
    ground_role: str
    role: str | None


# Conservative dimensions shared by every monumental_portal. Prefab cornice
# adds 4 cm drip beyond these nominal bounds, pilaster capitals 5 cm/side.
PORTAL = dict(pier_width=.28, pier_gap=.14, frame_margin=.12,
              pier_head=.24, cornice_height=.18, cornice_gap=.06,
              pediment_height=.48, edge_clearance=.10)


def _apply_motifs(c, openings, targets, length, height):
    """Decorate post-edit openings; target is the (component floor, bay) key."""
    if not c.motifs:
        return tuple(openings), ()
    ops=list(openings)
    features=[]
    for motif in c.motifs:
        key=(motif.floor,motif.bay)
        _check(key in targets, 'monumental_portal target bay/floor does not exist')
        index=targets[key]
        _check(index is not None, 'monumental_portal requires an opening after edits')
        op=ops[index]
        _check(op.kind in ('door','gate'), 'monumental_portal requires a door or gate')
        if motif.opening_shape=='arch':
            op=replace(op,shape='arch',arch_rise_m=min(op.width_m/2,op.height_m/3))
            ops[index]=op
        left=op.u_m-PORTAL['pier_gap']-PORTAL['pier_width']
        right=op.u_m+op.width_m+PORTAL['pier_gap']
        width=right+PORTAL['pier_width']-left
        pier_top=op.v_m+op.height_m+PORTAL['pier_head']
        cornice_z=pier_top+PORTAL['cornice_gap']
        top= cornice_z+PORTAL['cornice_height']+(PORTAL['pediment_height'] if motif.pediment else 0.)
        _check(left>=PORTAL['edge_clearance'] and left+width<=length-PORTAL['edge_clearance'] and
               top<=height-.1 and op.v_m>=0 and pier_top>op.v_m,
               'monumental_portal does not fit facade chart')
        source='monumental_portal'
        features.extend((
            FacadeProjection('pilaster',left,0.,PORTAL['pier_width'],pier_top,.25,source=source),
            FacadeProjection('pilaster',right,0.,PORTAL['pier_width'],pier_top,.25,source=source),
            FacadeProjection('frame',op.u_m-PORTAL['frame_margin'],op.v_m,
                op.width_m+2*PORTAL['frame_margin'],op.height_m+PORTAL['pier_head'],.3,
                border_width_m=.10,source=source),
            FacadeProjection('cornice',left, cornice_z,width,PORTAL['cornice_height'],.32,source=source),
        ))
        if motif.pediment:
            features.append(FacadeProjection('pediment',left,cornice_z+PORTAL['cornice_height'],
                                              width,PORTAL['pediment_height'],.28,source=source))
    return tuple(ops),tuple(features)


def validate_bay_groups(c):
    """Validate even inactive/hidden controls, before metric composition."""
    if not c.bay_groups:return
    _check(c.mode=='repeat','bay_groups require repeat mode')
    _check(c.bay_count is None and c.bay_axes_m is None,
           'bay_groups conflict with global bay_count/bay_axes_m')
    previous=0.
    for group in c.bay_groups:
        lo,hi=group.u
        _check(math.isfinite(lo) and math.isfinite(hi) and 0<=lo<hi<=1,'Invalid BayGroup u interval')
        _check(lo>=previous,'BayGroups must be ordered without overlap')
        _check(type(group.count) is int and group.count>=1,'BayGroup count must be a positive integer')
        _check(group.ground_role in ('inherit','entrance','garage','shopfront','blind'),'Invalid BayGroup ground_role')
        _check(group.ground_role not in ('entrance','garage') or group.count==1,
               'BayGroup entrance/garage requires count=1')
        previous=hi


def resolve_bay_layout(c, length):
    """Retain group membership and pitch; canonical indices flatten left->right."""
    validate_bay_groups(c)
    bays=[]
    for gi,group in enumerate(c.bay_groups):
        start,end=(length*u for u in group.u)
        pitch=(end-start-.64)/group.count
        _check(pitch>0,'BayGroup too narrow for its margins')
        for i in range(group.count):
            axis=start+.32+(i+.5)*pitch
            _check(start<axis<end,'BayGroup axis outside group')
            bays.append(ResolvedBay(axis,pitch,start,end,gi,i,len(bays),group.ground_role,group.role))
    return tuple(bays)


def validate_order(c):
    order=c.order
    if order is None:return
    _check(order.pilaster_mode in ('none','group_boundaries','bay_boundaries','explicit'),
           'Invalid ArchitecturalOrder pilaster_mode')
    _check(.12<=order.pilaster_width_m<=.6 and .05<=order.pilaster_depth_m<=.5 and
           all(math.isfinite(x) for x in (order.pilaster_width_m,order.pilaster_depth_m)),
           'Invalid ArchitecturalOrder pilaster dimensions')
    _check(order.pilaster_mode=='explicit' or not order.pilaster_axes_u,
           'ArchitecturalOrder axes require explicit mode')
    _check(tuple(sorted(set(order.pilaster_axes_u)))==order.pilaster_axes_u and
           all(math.isfinite(x) and 0<=x<=1 for x in order.pilaster_axes_u),
           'Invalid ArchitecturalOrder axes')
    _check(tuple(sorted(set(order.paired_bays)))==order.paired_bays and
           all(type(i) is int and i>=0 for i in order.paired_bays),
           'Invalid ArchitecturalOrder paired_bays')
    _check(all(math.isfinite(x) and 0<=x<=1.5 for x in
               (order.plinth_height_m,order.entablature_height_m,order.cornice_height_m)),
           'Invalid ArchitecturalOrder course heights')
    _check(tuple(sorted(set(order.belt_courses_m)))==order.belt_courses_m and
           all(math.isfinite(x) and x>0 for x in order.belt_courses_m),
           'Invalid ArchitecturalOrder belt_courses_m')


def _order_projections(c,length,height,axes,bays=None):
    if c.order is None:return ()
    o=c.order
    validate_order(c)
    _check(o.plinth_height_m+o.entablature_height_m+o.cornice_height_m<height and
           all(.06<=z<=height-.06 for z in o.belt_courses_m),
           'ArchitecturalOrder courses outside chart')
    _check(not o.paired_bays or c.mode=='repeat', 'ArchitecturalOrder paired_bays require repeat')
    _check(not o.paired_bays or max(o.paired_bays)<len(axes),
           'ArchitecturalOrder paired_bays target nonexistent bay')
    _check(o.pilaster_mode!='group_boundaries' or bool(bays),
           'ArchitecturalOrder group_boundaries require BayGroups')
    _check(o.pilaster_mode!='bay_boundaries' or bool(axes),
           'ArchitecturalOrder bay_boundaries require bays')
    if bays:
        boundaries=tuple(sorted({v for b in bays for v in (b.start_m,b.end_m)}))
        cells=tuple((b.axis_m-b.pitch_m/2,b.axis_m+b.pitch_m/2) for b in bays)
    else:
        boundaries=()
        cuts=(0.,)+tuple((a+b)/2 for a,b in zip(axes,axes[1:]))+(length,)
        cells=tuple(zip(cuts,cuts[1:]))
    if o.pilaster_mode=='group_boundaries':positions=list(boundaries)
    elif o.pilaster_mode=='bay_boundaries':
        positions=list((0.,)+tuple((a+b)/2 for a,b in zip(axes,axes[1:]))+(length,))
    elif o.pilaster_mode=='explicit':positions=[u*length for u in o.pilaster_axes_u]
    else:positions=[]
    for i in o.paired_bays:
        lo,hi=cells[i]
        positions.extend((lo+.12,hi-.12))
    _check(all(0<=x<=length for x in positions),'ArchitecturalOrder pilasters outside chart')
    # Centre the shaft on a boundary; collapse duplicate axes shared by groups.
    centres=sorted(set(round(min(max(x,o.pilaster_width_m/2+.05),
                                 length-o.pilaster_width_m/2-.05),6) for x in positions))
    def feature(kind,u,z,w,h,depth):
        return FacadeProjection(kind,u,z,w,h,depth,source='architectural_order')
    result=[feature('pilaster',x-o.pilaster_width_m/2,0.,o.pilaster_width_m,
                    height-o.cornice_height_m,o.pilaster_depth_m) for x in centres]
    if o.plinth_height_m:
        result.append(feature('panel',0.,0.,length,o.plinth_height_m,.12))
    result.extend(feature('panel',0.,z-.04,length,.08,.14) for z in o.belt_courses_m)
    if o.entablature_height_m:
        result.append(feature('panel',0.,height-o.cornice_height_m-o.entablature_height_m,
                              length,o.entablature_height_m,.18))
    if o.cornice_height_m:
        result.append(feature('cornice',.05,height-o.cornice_height_m-.05,
                              length-.10,o.cornice_height_m,.3))
    return tuple(result)


def validate_opening_programs(c):
    for p in c.opening_programs:
        _check(bool(c.bay_groups) and type(p.group) is int and 0<=p.group<len(c.bay_groups),
               'OpeningProgram requires an existing BayGroup')
        _check(p.floor is None or type(p.floor) is int and p.floor>=0,'Invalid OpeningProgram floor')
        _check(p.kind in (None,'window','door','gate') and p.shape in (None,'rectangle','arch'),
               'Invalid OpeningProgram kind/shape')
        _check(p.prefab in (None,'legacy','slim_window','wood_panel','metal_gate','roller','storefront','louver','open','screen'),
               'Invalid OpeningProgram prefab')
        _check(p.grille is None or type(p.grille) is bool,'Invalid OpeningProgram grille')
        for value,valid in ((p.width_ratio,lambda x:.1<=x<=.95),
                            (p.height_m,lambda x:x>0),(p.sill_m,lambda x:x>=0)):
            _check(value is None or math.isfinite(value) and valid(value),'Invalid OpeningProgram dimensions')
    for i,p in enumerate(c.opening_programs):
        _check(not any(q.group==p.group and (q.floor is None or p.floor is None or q.floor==p.floor)
                       for q in c.opening_programs[:i]),'Ambiguous OpeningProgram group/floor')


def _compose_grouped(c, family, length, levels, height, ground, top, floor_indices):
    bays=resolve_bay_layout(c,length)
    validate_opening_programs(c)
    floors=tuple(range(len(levels)-1)) if floor_indices is None else floor_indices
    _check(all(p.floor is None or p.floor in floors for p in c.opening_programs),
           'OpeningProgram floor does not exist in chart')
    rules=FAMILY_RULES[family]
    edits={(e.floor,e.bay):e for e in c.opening_edits}
    found=set()
    ops=[]
    targets={}
    def append(op,bay,key):
        _check(op.u_m>=bay.start_m+.12 and op.u_m+op.width_m<=bay.end_m-.12+1e-8,
               'Opening outside its BayGroup')
        _check(op.width_m>0 and op.height_m>0 and op.v_m>=0 and op.v_m+op.height_m<=height-.1,
               'Opening edit/add outside facade')
        shape=rect(op.u_m,op.v_m,op.u_m+op.width_m,op.v_m+op.height_m)
        _check(all(shape.intersection(rect(x.u_m,x.v_m,x.u_m+x.width_m,x.v_m+x.height_m)).area<1e-8 for x in ops),
               'Opening edit/add overlaps another opening')
        ops.append(op)
        targets[key]=len(ops)-1
    for local_floor,(z0,z1) in enumerate(zip(levels,levels[1:])):
        floor=local_floor if floor_indices is None else floor_indices[local_floor]
        for bay in bays:
            program=next((p for p in c.opening_programs if p.group==bay.group_index and
                          (p.floor is None or p.floor==floor)),None)
            key=(floor,bay.global_index)
            found.add(key)
            edit=edits.get(key)
            if edit is not None:
                targets[key]=None
                if edit.action=='replace':append(edit.opening,bay,key)
                continue
            kind,prefab='window',rules['prefab']
            width,sill,h=bay.pitch_m*c.window_ratio,c.sill_m,c.window_height_m
            if ground and local_floor==0:
                role=bay.ground_role
                if role=='blind' and (program is None or program.kind is None):
                    targets[key]=None
                    continue
                if role in ('entrance','garage'):
                    kind,prefab=('door','wood_panel') if role=='entrance' else ('gate','roller')
                    # Explicit entry groups use their own available width,
                    # without the legacy first-door cap of 1.2 metres.
                    width,sill,h=bay.pitch_m*.75,.04,min(max(c.window_height_m,2.3),z1-z0-.3)
                elif role=='shopfront' or role=='inherit' and rules['ground']=='shopfront':
                    prefab,sill='storefront',.15
            if floor>0 and c.balconies and bay.global_index%2==0:
                kind,sill='balcony_window',.18
            h=min(h,z1-z0-sill-.2)
            shape='rectangle'
            grille=rules['grille']
            if program is not None:
                kind=program.kind if program.kind is not None else kind
                prefab=program.prefab if program.prefab is not None else prefab
                shape=program.shape or shape
                grille=program.grille if program.grille is not None else grille
                width=bay.pitch_m*program.width_ratio if program.width_ratio is not None else width
                h=program.height_m if program.height_m is not None else h
                sill=program.sill_m if program.sill_m is not None else sill
                _check(sill+h<=z1-z0-.1,'OpeningProgram does not fit floor')
            _check(h>=.5 and width>=.4,'Openings cannot fit in BayGroup: reduce count or dimensions')
            append(Opening(kind,bay.axis_m-width/2,z0+sill,width,h,prefab=prefab,
                            grille=grille,shape=shape,arch_rise_m=min(width/2,h/3) if shape=='arch' else None,
                            balcony_depth_m=c.balcony_depth_m or .75,curtain=0),bay,key)
    _check(set(edits)<=found,'Sparse edit targets nonexistent floor/bay')
    for op in c.added_openings:
        owners=[b for b in bays if b.start_m<=op.u_m and op.u_m+op.width_m<=b.end_m]
        _check(bool(owners),'Added opening outside BayGroups (gaps are blind)')
        append(op,owners[0],None)
    ops,motif_features=_apply_motifs(c,ops,targets,length,height)
    return _finish(c,rules,length,levels,height,ground,top,tuple(b.axis_m for b in bays),ops,motif_features,bays)


def _finish(c, rules, length, levels, height, ground, top, axes, ops, motif_features=(), bays=None):
    # All groups have been joined. Global relief runs exactly once; balconies
    # and shutters consume each opening's actual dimensions, not a global pitch.
    order_features=_order_projections(c,length,height,axes,bays)
    relief_rules=dict(rules)
    if c.order is not None and c.order.cornice_height_m and top:relief_rules['cornice']=0
    if c.order is not None and (c.order.pilaster_mode!='none' or c.order.paired_bays):
        relief_rules['pilasters']=False
    projections,regions=compose_relief(length,levels,ops,relief_rules,height,ground,top,
                                       np.random.default_rng(0),[],DetailBudget(2))
    projections=tuple(replace(x,depth_m=c.gallery_depth_m) if x.kind=='gallery' else
                      replace(x,depth_m=c.awning_depth_m) if x.kind=='awning' else x for x in projections)
    ops=tuple(replace(x,kind='window') if x.kind=='balcony_window' else x for x in ops)
    return FacadeComposition(axes,ops,(projections if c.projections is None else c.projections)+motif_features+order_features+
                             _crown_projections(c,length,height),
                             tuple(regions) if c.material_regions is None else c.material_regions)


def compose_facade(c: FacadeControls, family, length, levels, height, ground, top,
                   floor_indices=None) -> FacadeComposition:
    """Compose local metric entities; floor_indices preserves component floors.

    Controls must already be completed/validated by the resolver. Visibility
    must be applied after composition, never by shortening this input chart.
    """
    if c.bay_groups:
        return _compose_grouped(c,family,length,levels,height,ground,top,floor_indices)
    if c.mode == "explicit":
        return FacadeComposition((), c.openings, (c.projections or ())+_order_projections(c,length,height,())+
                                 _crown_projections(c,length,height),
                                 c.material_regions or ())
    rules = dict(FAMILY_RULES[family])
    count = c.bay_count or max(1, round((length-.64)/3.1))
    axes = c.bay_axes_m if c.bay_axes_m is not None else tuple(.32+(i+.5)*(length-.64)/count for i in range(count))
    _check(bool(axes) and tuple(sorted(set(axes))) == axes and axes[0] > .4 and axes[-1] < length-.4, "Invalid bay axes")
    pitch = min([length-.64] + [b-a for a,b in zip(axes, axes[1:])] + [2*(axes[0]-.32), 2*(length-.32-axes[-1])])
    ops = []
    found=set()
    targets={}
    edits={(e.floor,e.bay):e for e in c.opening_edits}
    for local_floor, (z0,z1) in enumerate(zip(levels, levels[1:])):
        floor=local_floor if floor_indices is None else floor_indices[local_floor]
        for i, axis in enumerate(axes):
            kind, prefab = "window", rules["prefab"]
            width, sill, h = pitch*c.window_ratio, c.sill_m, c.window_height_m
            if ground and local_floor == 0 and i == 0:
                kind = "gate" if rules["ground"] == "garage" else "door"
                prefab = "roller" if kind == "gate" else "wood_panel"
                width, sill, h = min(pitch*.75, 3.2) if kind == "gate" else min(pitch*.42, 1.2), .04, min(2.3,z1-z0-.3)
            elif ground and local_floor == 0 and rules["ground"] == "shopfront":
                prefab, sill = "storefront", .15
            if floor > 0 and c.balconies and i % 2 == 0:
                kind, sill = "balcony_window", .18
            h = min(h, z1-z0-sill-.2)
            _check(h >= .5 and width >= .4, "Openings cannot fit: reduce bays or window dimensions")
            opening=Opening(kind, axis-width/2, z0+sill, width,h,
                               prefab=prefab, grille=rules["grille"],
                               balcony_depth_m=c.balcony_depth_m or .75, curtain=0)
            key=(floor,i)
            found.add(key)
            edit=edits.get(key)
            if edit is None:
                ops.append(opening)
                targets[key]=len(ops)-1
            elif edit.action=="replace":
                ops.append(edit.opening)
                targets[key]=len(ops)-1
            else:
                targets[key]=None
    _check(set(edits)<=found,"Sparse edit targets nonexistent floor/bay")
    ops.extend(c.added_openings)
    ops,motif_features=_apply_motifs(c,ops,targets,length,height)
    rectangles=[]
    for op in ops:
        _check(op.u_m>=.12 and op.v_m>=0 and op.width_m>0 and op.height_m>0 and
               op.u_m+op.width_m<=length-.12 and op.v_m+op.height_m<=height-.1,
               "Opening edit/add outside facade")
        shape=rect(op.u_m,op.v_m,op.u_m+op.width_m,op.v_m+op.height_m)
        _check(all(shape.intersection(other).area<1e-8 for other in rectangles),"Opening edit/add overlaps another opening")
        rectangles.append(shape)
    # Family relief is reused; its two random depths are always overwritten by
    # resolved architectural controls. This RNG never sees xi.
    order_features=_order_projections(c,length,height,axes)
    if c.order is not None and c.order.cornice_height_m and top:rules['cornice']=0
    if c.order is not None and (c.order.pilaster_mode!='none' or c.order.paired_bays):rules['pilasters']=False
    projections, regions = compose_relief(length, levels, ops, rules, height,
                                  ground, top, np.random.default_rng(0), [], DetailBudget(2))
    projections = tuple(replace(x, depth_m=c.gallery_depth_m) if x.kind == "gallery" else
                        replace(x, depth_m=c.awning_depth_m) if x.kind == "awning" else x for x in projections)
    ops = tuple(replace(x, kind="window") if x.kind == "balcony_window" else x for x in ops)
    return FacadeComposition(axes, ops, (projections if c.projections is None else c.projections)+motif_features+order_features+
                             _crown_projections(c,length,height),
                             tuple(regions) if c.material_regions is None else c.material_regions)
