"""Grouped rhythm, stable edits and one chart-wide relief pass."""
from dataclasses import replace
from collections import Counter
import json

import numpy as np
import pytest

from domain.theta import *
from modeling.facade_composition import compose_facade, resolve_bay_layout
from modeling.theta import _facade_controls, resolve_theta, generate_resolved
from test_facade_zones import body, solve, front, P
from test_compositional_massing import semantic_vertices


GROUPS=(BayGroup((0.,.30),3,role='left'),
        BayGroup((.30,.52),1,'entrance','entry'),
        BayGroup((.52,1.),4,role='right'))


def controls(**kw):
    return FacadeControls(bay_groups=GROUPS,balconies=False,**kw)


def compose(c=None,family='republicano',length=24.,levels=(0.,3.,6.),ground=True,floor_indices=None):
    c=_facade_controls(c or controls(),family)
    return compose_facade(c,family,length,levels,levels[-1],ground,True,floor_indices)


def test_bay_groups_legacy_empty_is_identical():
    from test_facade_composition import cases,signatures
    from pathlib import Path
    expected=json.loads((Path(__file__).parent/'fixtures/facade_composition_hashes.json').read_text())
    for name,c in cases().items():
        assert signatures(c)==tuple(expected[name])
    request=ReconstructionRequest(P,ThetaCandidate())
    assert 'bay_groups' not in canonical(request)
    assert from_json(canonical(request)).theta.facade.bay_groups==()


def test_bay_groups_three_regions():
    c=controls()
    bays=resolve_bay_layout(c,24.)
    out=compose(c)
    assert len(out.axes_m)==len(bays)==8
    assert all(a<b for a,b in zip(out.axes_m,out.axes_m[1:]))
    assert len({b.pitch_m for b in bays})==3
    assert [b.group_index for b in bays]==[0,0,0,1,2,2,2,2]
    assert [b.local_index for b in bays]==[0,1,2,0,0,1,2,3]
    assert [b.global_index for b in bays]==list(range(8))
    for bay in bays:
        assert bay.start_m<bay.axis_m<bay.end_m
    for floor in range(2):
        for bay,op in zip(bays,out.openings[floor*8:(floor+1)*8]):
            assert bay.start_m<=op.u_m<op.u_m+op.width_m<=bay.end_m


def test_bay_group_primary_entrance_not_first():
    out=compose()
    assert [i for i,o in enumerate(out.openings) if o.kind=='door']==[3]
    assert out.openings[0].kind=='window'
    assert out.openings[3].width_m>out.openings[0].width_m


def test_bay_group_garage():
    c=replace(controls(),bay_groups=(GROUPS[0],replace(GROUPS[1],ground_role='garage'),GROUPS[2]))
    out=compose(c,family='workshop')
    assert [(i,o.prefab) for i,o in enumerate(out.openings) if o.kind=='gate']==[(3,'roller')]
    assert out.openings[0].kind=='window'


def test_bay_group_opening_edit_flat_indices():
    original=compose()
    replacement=replace(original.openings[4],height_m=1.,source='replacement')
    changed=compose(controls(opening_edits=(OpeningEdit(0,3,'suppress'),OpeningEdit(0,4,'replace',replacement))))
    assert len(changed.openings)==15
    assert original.openings[3] not in changed.openings
    assert changed.openings[3]==replacement
    assert changed.openings[7:]==original.openings[8:]


def test_bay_groups_inside_facade_zone():
    p=replace(P,parcel=((0.,0.),(40.,0.),(40.,20.),(0.,20.)))
    c=controls(projections=())
    plan=solve(body((FacadeZone('front',c,(.2,.8)),)),context=p)
    wall=next(w for w in front(plan) if '/zone' in w.facade.edge_id)
    local=compose(c,family='quiet_house')
    assert wall.axes_m==pytest.approx([8+x for x in local.axes_m])
    assert wall.facade.openings==tuple(replace(o,u_m=o.u_m+8) for o in local.openings)
    assert len(generate_resolved(plan).faces)>0


def test_bay_groups_visibility_does_not_reflow():
    p=replace(P,parcel=((0.,0.),(24.,0.),(24.,20.),(0.,20.)))
    c=body((FacadeZone('front',controls(projections=())),))
    blocker=MassComponent('blocker',PlanRegion(u=(0.,.5),depth_m=(0.,4.)),(0.,3.))
    a=solve(c,context=p);b=solve(c,blocker,context=p)
    wa=front(a)[0];wb=front(b)[0]
    assert wa.axes_m==wb.axes_m and wa.facade==wb.facade
    frames=semantic_vertices(generate_resolved(b),'slim_frame')
    assert len(frames)>0
    assert not np.any((frames[:,0]<11.99)&(frames[:,2]<2.99))


@pytest.mark.parametrize('family',['republicano','galeria_madera','mixed_use'])
def test_bay_groups_do_not_duplicate_global_relief(family):
    out=compose(family=family)
    legacy=compose(FacadeControls(bay_count=8,balconies=False),family=family)
    global_kinds={'cornice','sill_band','pilaster','gallery','awning','sign_box','downpipe'}
    assert [p for p in out.projections if p.kind in global_kinds]==[p for p in legacy.projections if p.kind in global_kinds]
    assert out.material_regions==legacy.material_regions
    counts=Counter(p.kind for p in out.projections)
    assert counts['cornice']==1 and counts['downpipe']==1


def test_bay_groups_reject_overlap():
    with pytest.raises(ValueError,match='overlap'):
        compose(replace(controls(),bay_groups=(GROUPS[0],BayGroup((.2,.5),1))))


@pytest.mark.parametrize('kw',[{'bay_count':8},{'bay_axes_m':(1.,4.)}])
def test_bay_groups_reject_global_axes_conflict(kw):
    with pytest.raises(ValueError,match='conflict'):
        compose(controls(**kw))


@pytest.mark.parametrize('group',[
    BayGroup((-.1,.3),1),BayGroup((0.,1.1),1),BayGroup((.5,.5),1),
    BayGroup((float('nan'),1.),1),BayGroup((0.,float('inf')),1),
    BayGroup((0.,1.),0),BayGroup((0.,1.),1,'unknown'),BayGroup((0.,1.),2,'entrance')])
def test_bay_groups_invalid_definition(group):
    with pytest.raises(ValueError):compose(replace(controls(),bay_groups=(group,)))


def test_bay_groups_gaps_blind_and_ground_roles():
    c=replace(controls(),bay_groups=(BayGroup((0.,.3),2,'blind'),BayGroup((.5,1.),2,'shopfront')))
    out=compose(c)
    assert len(out.openings)==6
    assert all(o.prefab=='storefront' for o in out.openings[:2])
    assert all(not (7.2<o.u_m<12.) for o in out.openings)
    assert len(out.axes_m)==4  # blind ground bays retain upper-floor identity


def test_bay_groups_edit_must_stay_in_owner_group():
    with pytest.raises(ValueError,match='outside its BayGroup'):
        compose(controls(opening_edits=(OpeningEdit(0,3,'replace',Opening('door',1.,.1,1.,2.)),)))
    with pytest.raises(ValueError,match='gaps are blind'):
        compose(replace(controls(added_openings=(Opening('window',9.,.5,1.,1.),)),
                        bay_groups=(BayGroup((0.,.3),2),BayGroup((.5,1.),2))))


def test_bay_groups_schema_and_roundtrip():
    with pytest.raises(ValueError,match='schema_version=0.3'):
        resolve_theta(P,ThetaCandidate(facade=controls()))
    request=ReconstructionRequest(P,ThetaCandidate(schema_version='0.3',facade=controls()))
    assert from_json(canonical(request))==request
    with pytest.raises(ValueError,match='repeat mode'):
        compose(replace(controls(),mode='explicit',openings=()))


def test_bay_groups_vertical_zone_floor_indices():
    p=replace(P,parcel=((0.,0.),(24.,0.),(24.,20.),(0.,20.)))
    c=controls(opening_edits=(OpeningEdit(1,3,'suppress'),),projections=())
    plan=solve(body((FacadeZone('front',c,z_m=(3.,6.)),)),context=p)
    wall=next(w for w in front(plan) if '/zone' in w.facade.edge_id)
    assert len(wall.facade.openings)==7
    assert all(o.kind=='window' and o.v_m>=3 for o in wall.facade.openings)


def test_bay_groups_reject_reversed_order_and_too_narrow():
    with pytest.raises(ValueError,match='ordered'):
        compose(replace(controls(),bay_groups=tuple(reversed(GROUPS))))
    with pytest.raises(ValueError,match='BayGroup'):
        compose(length=3.)


def test_bay_groups_balconies_are_opening_scoped():
    out=compose(replace(controls(),balconies=True))
    balconies=[p for p in out.projections if p.kind=='balcony']
    assert len(balconies)==4  # upper global-local indices 0,2,4,6
    for projection,op in zip(balconies,out.openings[8::2]):
        assert projection.v_m==op.v_m
        assert projection.u_m==pytest.approx(op.u_m-.22)
        assert projection.width_m==pytest.approx(op.width_m+.44)
    assert all(o.kind!='balcony_window' for o in out.openings)


def test_bay_groups_override_replaces_inherited_layout_only():
    from modeling.theta import _facade_override_controls
    base=_facade_controls(FacadeControls(bay_count=2,window_ratio=.6),'quiet_house')
    local=_facade_override_controls(controls(),base,'quiet_house')
    assert local.bay_count is None and local.bay_axes_m is None
    assert local.bay_groups==GROUPS and local.window_ratio==.6
    with pytest.raises(ValueError,match='conflict'):
        _facade_override_controls(controls(bay_count=8),base,'quiet_house')
