"""Silhouette and raised apertures share a real wall, without extra masses."""
from dataclasses import replace
import json
from pathlib import Path
import numpy as np
import pytest
from shapely.geometry import Polygon
from domain.theta import FacadeControls, FacadeTopProfile, FacadeZone, FaceBand, Opening, MassComponent, PlanRegion
from modeling.theta import generate_resolved
from modeling.facade_top import validate_top_profile
from test_facade_zones import body, solve, front, semantic_vertices, BLIND


PROFILE=FacadeTopProfile(((0.,0.),(.25,0.),(.25,1.2),(.4,1.2),(.5,1.8),(.6,1.2),(.75,1.2),(.75,0.),(1.,0.)))


def test_raised_aperture_is_cut_in_wall_and_roof():
    c=replace(BLIND,top_profile=PROFILE,openings=(Opening('door',5.,.1,2.,6.6,shape='arch',prefab='open'),))
    plan=solve(body(faces=(FaceBand('front',c),)))
    original=solve(body())
    assert plan.masses==original.masses
    assert len(plan.masses)==1
    mesh=generate_resolved(plan)
    wall=semantic_vertices(mesh,'wall')
    assert wall[:,2].max()==pytest.approx(7.8,abs=1e-5)
    trim=semantic_vertices(mesh,'top_profile_moulding')
    assert len(trim)>0 and trim[:,2].max()>7.
    # Roof area loses only a small reveal strip at the raised opening.
    old=sum(Polygon(s.polygon,s.holes).area for r in original.roofs for s in r.surfaces)
    new=sum(Polygon(s.polygon,s.holes).area for r in plan.roofs for s in r.surfaces)
    assert 0<old-new<2.


def test_profile_inside_zone_and_hidden_top():
    c=replace(BLIND,top_profile=PROFILE)
    component=body((FacadeZone('front',c,(.2,.8)),))
    plan=solve(component)
    f=next(w.facade for w in front(plan) if '/zone' in w.facade.edge_id)
    assert f.top_profile.points_m[0]==pytest.approx((2.4,6.))
    blocker=MassComponent('blocker',PlanRegion(u=(0.,.5),depth_m=(0.,4.)),(0.,3.,6.))
    mesh=generate_resolved(solve(component,blocker))
    trim=semantic_vertices(mesh,'top_profile_moulding')
    assert len(trim)>0 and trim[:,0].min()>=6.-1e-5
    assert trim[:,2].max()>6.


@pytest.mark.parametrize('points',[
    ((.1,0.),(1.,1.)),((0.,0.),(.7,1.),(.3,2.),(1.,0.)),
    ((0.,0.),(.5,5.),(1.,0.)),((0.,0.),(.5,float('nan')),(1.,0.)),
    ((0.,0.),(.5,1.),(.5,1.),(1.,0.))])
def test_invalid_profile(points):
    with pytest.raises(ValueError):validate_top_profile(FacadeTopProfile(points))


def test_opening_outside_local_crest_rejected():
    c=replace(BLIND,top_profile=PROFILE,openings=(Opening('window',1.,1.,1.,6.),))
    with pytest.raises(ValueError,match='outside facade'):
        generate_resolved(solve(body(faces=(FaceBand('front',c),))))


def test_no_profile_legacy_identical():
    from test_facade_composition import cases,signatures
    expected=json.loads((Path(__file__).parent/'fixtures/facade_composition_hashes.json').read_text())
    assert all(signatures(c)==tuple(expected[k]) for k,c in cases().items())
