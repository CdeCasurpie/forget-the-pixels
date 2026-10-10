"""Above-roofline facade-only silhouettes; no mass or roof mutation."""
from dataclasses import replace
import numpy as np
import pytest

from domain.theta import CrownProfile, FacadeControls, FacadeZone, MassComponent, PlanRegion
from modeling.theta import generate_resolved
from test_facade_zones import P, body, solve, front, BLIND, semantic_vertices
from test_facade_composition import cases, signatures


def crown(kind='triangular',u=(.4,.6),height=1.,depth=.2):
    return CrownProfile(u,kind,height,depth)


def plan(c,other=(),zone=False):
    control=replace(BLIND,crowns=(c,))
    component=body(zones=(FacadeZone('front',control,(.2,.8)),) if zone else (),
                   faces=() if zone else ())
    if not zone:
        from domain.theta import FaceBand
        component=replace(component,faces=(FaceBand('front',control),))
    return solve(component,*other)


def front_crown(mesh,kind):
    return semantic_vertices(mesh,'crown_'+kind)


def test_crown_empty_preserves_legacy():
    from pathlib import Path
    import json
    old=json.loads((Path(__file__).parent/'fixtures/facade_composition_hashes.json').read_text())
    assert all(signatures(c)==tuple(old[name]) for name,c in cases().items())


@pytest.mark.parametrize('kind',['triangular','stepped'])
def test_crown_extends_above_wall(kind):
    resolved=plan(crown(kind))
    original=solve(body())
    assert resolved.masses==original.masses and resolved.roofs==original.roofs
    vertices=front_crown(generate_resolved(resolved),kind)
    assert len(vertices)>0 and vertices[:,2].min()==pytest.approx(6.)
    assert vertices[:,2].max()==pytest.approx(7.)
    assert np.ptp(vertices[:,1])>=.20  # non-zero depth


def test_crown_horizontal_interval():
    verts=front_crown(generate_resolved(plan(crown())),'triangular')
    assert verts[:,0].min()==pytest.approx(4.8)
    assert verts[:,0].max()==pytest.approx(7.2)
    assert not np.any((verts[:,0]<4.79)|(verts[:,0]>7.21))


def test_crown_inside_facade_zone():
    resolved=plan(crown('stepped',(.3,.7)),zone=True)
    wall=next(w for w in front(resolved) if '/zone' in w.facade.edge_id)
    feature,=wall.facade.projections
    assert feature.u_m==pytest.approx(2.4+7.2*.3)
    assert feature.v_m==pytest.approx(6.)
    vertices=front_crown(generate_resolved(resolved),'stepped')
    assert vertices[:,2].max()==pytest.approx(7.)
    assert vertices[:,0].min()==pytest.approx(feature.u_m)
    assert vertices[:,0].max()==pytest.approx(feature.u_m+feature.width_m)


def test_crown_inside_elevated_facade_zone():
    control=replace(BLIND,crowns=(crown('triangular'),))
    component=body((FacadeZone('front',control,(.2,.8),(3.,6.)),))
    resolved=solve(component)
    feature=next(p for w in front(resolved) for p in w.facade.projections if p.source=='crown_profile')
    assert feature.v_m==pytest.approx(6.)
    assert front_crown(generate_resolved(resolved),'triangular')[:,2].max()==pytest.approx(7.)


def test_crown_survives_visibility_clipping():
    blocker=MassComponent('blocker',PlanRegion(u=(0.,.5),depth_m=(0.,4.)),(0.,3.,6.))
    clear=plan(crown())
    occluded=plan(crown(),(blocker,))
    a=next(w for w in front(clear) if w.facade.projections)
    b=next(w for w in front(occluded) if w.facade.projections)
    assert a.facade==b.facade
    verts=front_crown(generate_resolved(occluded),'triangular')
    assert len(verts)>0 and verts[:,2].max()>6.
    assert verts[:,0].min()>=6.-1e-5


@pytest.mark.parametrize('profile',[
    crown(u=(-.1,.6)),crown(u=(.6,.6)),crown(u=(.8,1.1)),
    crown(kind='curved'),crown(height=.1),crown(height=3.1),
    crown(depth=.01),crown(depth=.81),crown(u=(float('nan'),1.))])
def test_crown_invalid_parameters(profile):
    with pytest.raises(ValueError,match='CrownProfile|finite number'):
        plan(profile)


def test_crowns_overlap_rejected():
    from domain.theta import FaceBand
    controls=replace(BLIND,crowns=(crown(u=(.2,.6)),crown(u=(.5,.8))))
    with pytest.raises(ValueError,match='overlap'):
        solve(body(faces=(FaceBand('front',controls),)))


def test_crown_requires_schema_03_and_does_not_enable_motif():
    from domain.theta import ThetaCandidate, ReconstructionRequest, canonical, from_json
    from modeling.theta import resolve_theta
    c=replace(BLIND,crowns=(crown(),))
    with pytest.raises(ValueError,match='schema_version=0.3'):
        resolve_theta(P,ThetaCandidate(facade=c))
    request=ReconstructionRequest(P,ThetaCandidate(schema_version='0.3',facade=c))
    assert from_json(canonical(request)).theta.facade.crowns==c.crowns
    assert not c.motifs
