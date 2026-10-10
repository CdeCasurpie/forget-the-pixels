from dataclasses import replace
import pytest
from domain.theta import OpeningProgram as Program, OpeningEdit, FacadeZone
from test_bay_groups import compose, controls
from test_facade_zones import body, solve, front, P


def test_empty():
    from test_bay_groups import test_bay_groups_legacy_empty_is_identical
    test_bay_groups_legacy_empty_is_identical()


def test_group_and_floor():
    out=compose(controls(opening_programs=(Program(0,0,width_ratio=.3,height_m=2.),
        Program(0,1,width_ratio=.7,height_m=1.),Program(2,None,width_ratio=.7,height_m=1.))))
    assert out.openings[0].height_m==2.
    assert out.openings[8].height_m==1.
    assert out.openings[8].width_m>out.openings[0].width_m
    assert out.openings[4].height_m==1.


def test_kind_arch_and_edit():
    c=controls(opening_programs=(Program(0,0,kind='door',shape='arch',sill_m=.04),))
    out=compose(c)
    assert out.openings[0].kind=='door' and out.openings[0].arch_rise_m>0
    replacement=replace(out.openings[0],shape='rectangle',arch_rise_m=None,height_m=1.)
    edited=compose(replace(c,opening_edits=(OpeningEdit(0,0,'replace',replacement),)))
    assert edited.openings[0]==replacement


def test_zone():
    context=replace(P,parcel=((0.,0.),(40.,0.),(40.,20.),(0.,20.)))
    c=controls(opening_programs=(Program(0,0,height_m=1.),))
    plan=solve(body((FacadeZone('front',c,(.2,.8)),)),context=context)
    wall=next(w for w in front(plan) if '/zone' in w.facade.edge_id)
    assert wall.facade.openings[0].height_m==1.


@pytest.mark.parametrize('programs',[(Program(9),),(Program(0,-1),),(Program(0,9),),
    (Program(0,height_m=8.),),(Program(0,width_ratio=1.),),
    (Program(0),Program(0,0)),(Program(0,shape='bad'),)])
def test_invalid(programs):
    with pytest.raises(ValueError):compose(controls(opening_programs=programs))
