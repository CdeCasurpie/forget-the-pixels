"""Architectural order composes once in the local chart."""
from dataclasses import replace
import pytest

from domain.theta import ArchitecturalOrder, FacadeZone, FacadeControls, FaceBand, ThetaCandidate
from modeling.facade_composition import compose_facade
from modeling.theta import resolve_theta, generate_resolved
from test_bay_groups import controls, compose, GROUPS
from test_facade_zones import body, solve, front, P
from test_facade_composition import cases, signatures


def order(**kw):return ArchitecturalOrder(**kw)


def features(result,kind):
    return [p for p in result.projections if p.kind==kind and p.source=='architectural_order']


def test_order_none_preserves_legacy():
    import json
    from pathlib import Path
    expected=json.loads((Path(__file__).parent/'fixtures/facade_composition_hashes.json').read_text())
    assert all(signatures(c)==tuple(expected[name]) for name,c in cases().items())


def test_group_boundaries_and_paired_bay():
    out=compose(controls(order=order(pilaster_mode='group_boundaries',paired_bays=(3,))))
    centres=[p.u_m+p.width_m/2 for p in features(out,'pilaster')]
    assert centres==pytest.approx([.20,7.2,7.64,12.04,12.48,23.80])
    assert any(7.2<x<12.48 for x in centres)
    assert len(centres)==len(set(centres))


def test_bay_boundaries_and_explicit_axes():
    out=compose(controls(order=order(pilaster_mode='bay_boundaries')))
    p=features(out,'pilaster')
    assert len(p)==len(out.axes_m)+1
    assert p[0].u_m>=0 and p[-1].u_m+p[-1].width_m<=24
    explicit=compose(controls(order=order(pilaster_mode='explicit',pilaster_axes_u=(.25,.75))))
    assert [x.u_m+x.width_m/2 for x in features(explicit,'pilaster')]==pytest.approx([6.,18.])


def test_order_courses_single_and_replaces_family_cornice():
    o=order(plinth_height_m=.45,belt_courses_m=(3.,),entablature_height_m=.35,cornice_height_m=.28)
    out=compose(controls(order=o))
    assert len(features(out,'panel'))==3
    assert len(features(out,'cornice'))==1
    assert len([p for p in out.projections if p.kind=='cornice' and p.source=='family_rule'])==0
    assert features(out,'cornice')[0].v_m==pytest.approx(6.-.28-.05)


def test_order_inside_facade_zone():
    c=FacadeControls(mode='explicit',openings=(),order=order(pilaster_mode='explicit',pilaster_axes_u=(.25,),cornice_height_m=.28))
    plan=solve(body((FacadeZone('front',c,(.2,.8)),)))
    wall=next(w for w in front(plan) if '/zone' in w.facade.edge_id)
    assert any(p.source=='architectural_order' and p.kind=='pilaster' and
               p.u_m+p.width_m/2==pytest.approx(2.4+7.2*.25) for p in wall.facade.projections)
    assert len(generate_resolved(plan).faces)>0


@pytest.mark.parametrize('o',[order(pilaster_mode='bad'),order(pilaster_width_m=-.1),
    order(pilaster_depth_m=0.),order(pilaster_mode='explicit',pilaster_axes_u=(1.2,)),
    order(paired_bays=(99,)),order(plinth_height_m=8.),order(belt_courses_m=(7.,))])
def test_invalid_order(o):
    with pytest.raises(ValueError,match='ArchitecturalOrder'):
        compose(controls(order=o))


def test_order_schema_03_only():
    with pytest.raises(ValueError,match='schema_version=0.3'):
        resolve_theta(P,ThetaCandidate(facade=FacadeControls(order=order())))
