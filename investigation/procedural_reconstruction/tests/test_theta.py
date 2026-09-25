from dataclasses import replace, asdict
import json
import numpy as np
import pytest
from domain.theta import *
from modeling.theta import resolve_theta, generate_resolved, generate_from_theta, ResolvedArchitecture

P = ReconstructionContext(((0.,0.),(10.,0.),(10.,16.),(0.,16.)),(0,))
T = ThetaCandidate(height_m=8.4,floors=3,facade=FacadeControls(bay_count=3,balconies=False))


def test_roundtrip():
    request=ReconstructionRequest(P,T)
    other=from_json(canonical(request))
    assert canonical(other)==canonical(request)
    r=resolve_theta(P,T)
    r2=decode(ResolvedArchitecture,json.loads(canonical(r)))
    assert canonical(r)==canonical(r2)
    a,b=generate_resolved(r),generate_resolved(r2)
    assert np.array_equal(a.vertices,b.vertices)
    assert np.array_equal(a.faces,b.faces)
    assert np.array_equal(a.corner_uv,b.corner_uv)


@pytest.mark.parametrize('theta',[
    replace(T,massing=MassingControls(pattern='single_block',upper_setback_m=2.5)),
    replace(T,facade=FacadeControls(balconies=False,balcony_depth_m=.8)),
    replace(T,roof=RoofControls(kind='flat',slope_deg=20)),
    replace(T,facade=FacadeControls(bay_count=3,bay_axes_m=(2.,5.,8.))),
    replace(T,facade=FacadeControls(mode='explicit',openings=(),bay_count=2)),
    replace(T,facades=(FacadeOverride('missing',0,FacadeControls()),)),
])
def test_inactive_or_invalid_rejected(theta):
    with pytest.raises(ValueError):
        resolve_theta(P,theta)


def test_unknown_and_external():
    r=resolve_theta(replace(P,locked_height_m=11.2),ThetaCandidate())
    assert r.theta.height_m==11.2
    assert r.completed['height_m']=='external'
    assert r.completed['family']=='prior/completed'
    with pytest.raises(ValueError):
        resolve_theta(replace(P,locked_height_m=11.2),T)


def test_strict_json():
    d=asdict(ReconstructionRequest(P,T))
    d['theta']['floorz']=3
    with pytest.raises(ValueError):
        from_json(json.dumps(d))
    with pytest.raises(ValueError):
        resolve_theta(P,replace(T,floors=True))


def test_setback_authority():
    t=replace(T,massing=MassingControls(pattern='stepped_back',upper_setback_m=2.5))
    a=resolve_theta(P,t)
    b=resolve_theta(P,replace(t,massing=replace(t.massing,upper_setback_m=3.5)))
    assert a.masses[0]==b.masses[0]
    assert min(y for x,y in a.masses[1].footprint)==2.5
    assert min(y for x,y in b.masses[1].footprint)==3.5
    assert a.theta.family==b.theta.family
    assert a.theta.primary_color==b.theta.primary_color
    assert a.theta.roof==b.theta.roof


def test_bays_windows_and_color_are_independent():
    a=resolve_theta(P,T)
    b=resolve_theta(P,replace(T,facade=replace(T.facade,bay_count=4)))
    assert a.masses==b.masses and a.roofs==b.roofs
    assert len(a.walls[0].axes_m)==3 and len(b.walls[0].axes_m)==4
    c=resolve_theta(P,replace(T,primary_color=(.1,.3,.5)))
    assert a.masses==c.masses and a.walls==c.walls
    ma,mc=generate_resolved(a),generate_resolved(c)
    assert np.array_equal(ma.vertices,mc.vertices)
    assert ma.materials!=mc.materials


def test_xi_does_not_change_structure():
    r=resolve_theta(P,T)
    a=generate_resolved(r,NuisanceParameters(1))
    b=generate_resolved(r,NuisanceParameters(2))
    assert a.materials==b.materials
    # All architecture remains identical; compare triangles outside curtains.
    def structural(mesh):
        return [(part['name'], np.round(mesh.vertices[mesh.faces[part['face_start']:part['face_start']+part['face_count']]],8).tobytes())
                for part in mesh.parts if 'curtain' not in part['name']]
    assert structural(a)==structural(b)


def test_explicit_irregular_side_facade():
    ops=(Opening('window',1.,1.,1.2,1.4,prefab='slim_window'),Opening('window',5.,4.,2.,1.1,prefab='slim_window'))
    t=replace(T,facades=(FacadeOverride('main',1,FacadeControls(mode='explicit',openings=ops)),))
    r=resolve_theta(P,t)
    wall=next(w for w in r.walls if w.edge==1)
    assert wall.facade.openings==ops and wall.facade.is_front
    mesh=generate_resolved(r)
    assert len(mesh.faces)>0


@pytest.mark.parametrize('pattern', ['single_block','stepped_back','podium_tower','front_tall_rear_low','front_low_rear_tall'])
def test_patterns_generate(pattern):
    r=resolve_theta(P,replace(T,massing=MassingControls(pattern=pattern)))
    mesh=generate_resolved(r,NuisanceParameters(curtains=False))
    assert np.isfinite(mesh.vertices).all() and len(mesh.faces)>0


def test_explicit_masses_and_no_redundancy():
    mass=ArchitecturalMass('main',P.parcel,(0.,3.,6.))
    theta=ThetaCandidate(massing=MassingControls(pattern='explicit'),masses=(mass,))
    r=resolve_theta(P,theta)
    assert r.masses[0].roof_z==6 and r.theta.height_m==6
    assert r.completed['height_m']=='derived/explicit_mass_levels'
    assert len(generate_resolved(r).faces)>0
    with pytest.raises(ValueError):
        resolve_theta(P,replace(theta,height_m=6.))
    floating=replace(mass,levels_m=(3.,6.))
    with pytest.raises(ValueError):
        resolve_theta(P,replace(theta,masses=(floating,)))


def test_roof_props_are_theta_not_xi():
    t=replace(T,roof=RoofControls(props=(RoofObject('main','water_tank',(5.,8.)),RoofObject('main','rebar_cluster',(7.,12.)))))
    r=resolve_theta(P,t)
    assert [p.kind for p in r.roofs[0].props]==['water_tank','rebar_cluster']
    a=generate_resolved(r,NuisanceParameters(1,False))
    b=generate_resolved(r,NuisanceParameters(2,False))
    def significant(mesh):
        return [(part['name'],mesh.vertices[mesh.faces[part['face_start']:part['face_start']+part['face_count']]].tobytes())
                for part in mesh.parts if part['name']!='rebar']
    assert significant(a)==significant(b)
    assert not np.array_equal(a.vertices,b.vertices)


def test_explicit_fence_and_gate():
    run=FenceRun(0,0.,10.,'reja',1.8,gate_u=2.,gate_width=1.)
    t=replace(T,massing=MassingControls(front_setback_m=3.),site=SiteControls(runs=(run,)))
    r=resolve_theta(P,t)
    assert r.boundaries[0].height==1.8 and r.boundaries[0].gate_u==2.
    assert len(generate_resolved(r).faces)>0
    with pytest.raises(ValueError):
        resolve_theta(P,replace(t,site=SiteControls(runs=(replace(run,gate_width=20.),))))


def test_observation_evidence_and_unknown():
    from pipeline.theta import reconstruct
    request=ReconstructionRequest(P,replace(T,roof=RoofControls(kind=None)),
        evidence={'roof.kind':Evidence('unknown')},observations=(Observation('v1','photo.jpg'),))
    result=reconstruct(request)
    assert result.resolved.theta.roof.kind=='flat'
    assert result.requested.theta.roof.kind is None
    for evidence in ({'roof.kind':Evidence('observed')},{'floorz':Evidence('unknown')},
                     {'height_m':Evidence('observed',1.2)},{'height_m':Evidence('observed',.9,('missing',))}):
        with pytest.raises(ValueError):
            reconstruct(replace(request,evidence=evidence))


def test_parcel_canonicalization():
    shifted=replace(P,parcel=P.parcel[2:]+P.parcel[:2],fronts=(2,))
    reverse=replace(P,parcel=tuple(reversed(P.parcel)),fronts=(2,))
    a=resolve_theta(P,T)
    assert canonical(a)==canonical(resolve_theta(shifted,T))
    assert canonical(a)==canonical(resolve_theta(reverse,T))


def test_shed_and_corner():
    p=replace(P,fronts=(0,1))
    t=replace(T,massing=MassingControls(pattern='corner_accent',corner_reach_m=4.))
    r=resolve_theta(p,t)
    assert max(m.roof_z for m in r.masses)==T.height_m
    assert len(generate_resolved(r).faces)>0
    r=resolve_theta(P,replace(T,roof=RoofControls(kind='tile_shed',slope_deg=8.)))
    assert len(generate_resolved(r).faces)>0


def test_envelope_and_uv():
    from modeling.validation import validate_mesh
    from modeling.grammar import street_envelope
    from domain.architecture import ParcelContext
    from shapely.geometry import Polygon
    r=resolve_theta(P,T)
    mesh=generate_resolved(r)
    report=validate_mesh(mesh,Polygon(P.parcel),envelope=street_envelope(ParcelContext(P.parcel,explicit_fronts=P.fronts)))
    assert report['envelope_test']=='passed'
    uv=mesh.corner_uv
    area=np.abs((uv[:,1,0]-uv[:,0,0])*(uv[:,2,1]-uv[:,0,1])-(uv[:,1,1]-uv[:,0,1])*(uv[:,2,0]-uv[:,0,0]))
    assert np.isfinite(uv).all() and (area>1e-12).all()


@pytest.mark.parametrize('locked,observed,floors,expected,source',[
    (10.5,None,3,10.5,'external'),
    (None,9.,3,9.,None),
    (None,9.,None,9.,None),
    (None,None,4,11.2,'prior/completed'),
    (None,None,None,8.4,'prior/completed'),
])
def test_height_authority_matrix(locked,observed,floors,expected,source):
    r=resolve_theta(replace(P,locked_height_m=locked),replace(T,height_m=observed,floors=floors))
    assert r.theta.height_m==pytest.approx(expected)
    assert r.theta.floors==(floors if floors is not None else round(expected/2.8))
    assert r.masses[0].floor_levels[1]-r.masses[0].floor_levels[0]==pytest.approx(expected/r.theta.floors)
    if source:
        assert r.completed['height_m']==source
    assert r.completion_details.get('height_m',{}).get('value',expected)==pytest.approx(expected)


def test_height_conflict_and_explicit_mass_lock():
    with pytest.raises(ValueError,match='conflicts'):
        resolve_theta(replace(P,locked_height_m=10.5),replace(T,height_m=9.,floors=3))
    t=ThetaCandidate(massing=MassingControls(pattern='explicit'),masses=(ArchitecturalMass('main',P.parcel,(0.,3.,6.)),))
    with pytest.raises(ValueError,match='conflicts'):
        resolve_theta(replace(P,locked_height_m=9.),t)


def test_unknown_and_observed_absence_remain_distinct():
    unknown=ThetaCandidate(facade=FacadeControls(balconies=None,services=None,projections=None,stairs=None),
                           roof=RoofControls(props=None),side_material=None,finish=None)
    absent=replace(unknown,facade=replace(unknown.facade,balconies=False,services=False,
                   projections=(),stairs=()),roof=RoofControls(props=()))
    assert from_json(canonical(ReconstructionRequest(P,unknown))).theta.facade.projections is None
    assert from_json(canonical(ReconstructionRequest(P,absent))).theta.facade.projections==()
    a,b=resolve_theta(P,unknown),resolve_theta(P,absent)
    assert a.completed['facade.services']=='prior/completed'
    assert a.completed['side_material']=='prior/completed'
    assert a.completed['finish']=='prior/completed'
    assert a.completed['roof.props']=='prior/completed'
    assert 'facade.services' not in b.completed
    assert 'roof.props' not in b.completed
    assert a.theta.facade.projections is None and b.theta.facade.projections==()
    assert all(not w.facade.projections for w in b.walls)
    assert a.completion_details['side_material']['value']=='brick'


def test_roof_override_is_local_and_strict():
    base=replace(T,massing=MassingControls(pattern='stepped_back',upper_setback_m=2.5))
    a=resolve_theta(P,base)
    t=replace(base,roofs=(RoofOverride('setback:0','tile_shed',0.,14.),))
    b=resolve_theta(P,t)
    assert a.masses==b.masses and a.walls==b.walls and a.theta.primary_color==b.theta.primary_color
    main=next(r for r in b.roofs if r.mass_id=='main:0')
    top=next(r for r in b.roofs if r.mass_id=='setback:0')
    assert main.surfaces[0].kind=='flat' and top.surfaces[0].kind=='tile_shed'
    assert top.surfaces[0].slope_deg==14
    with pytest.raises(ValueError):
        resolve_theta(P,replace(base,roofs=(RoofOverride('missing:0','flat'),)))
    assert canonical(decode(ResolvedArchitecture,json.loads(canonical(b))))==canonical(b)


def test_repeat_sparse_corrections_and_explicit_mode():
    base=resolve_theta(P,T)
    edits=(OpeningEdit(0,2,'replace',Opening('gate',7.3,.04,1.5,2.2,prefab='roller')),
           OpeningEdit(1,1,'suppress'))
    t=replace(T,facade=replace(T.facade,opening_edits=edits))
    r=resolve_theta(P,t)
    front=lambda plan:next(w for w in plan.walls if w.edge==0 and w.mass_role=='main:0')
    a,b=front(base).facade.openings,front(r).facade.openings
    assert len(b)==len(a)-1
    assert b[2].kind=='gate'
    assert a[0]==b[0] and a[-1]==b[-1]
    assert r.masses==base.masses and r.roofs==base.roofs
    assert canonical(from_json(canonical(ReconstructionRequest(P,t))).theta)==canonical(t)
    added=Opening('window',7.3,.8,1.1,1.1,prefab='slim_window')
    r2=resolve_theta(P,replace(T,facade=replace(T.facade,opening_edits=(OpeningEdit(0,2,'suppress'),),added_openings=(added,))))
    assert added in front(r2).facade.openings
    with pytest.raises(ValueError,match='overlaps'):
        resolve_theta(P,replace(T,facade=replace(T.facade,added_openings=(added,))))


def test_facade_override_inherits_global_repeat_controls():
    t=replace(T,facade=FacadeControls(bay_count=5,balconies=True,balcony_depth_m=.8),
              facades=(FacadeOverride('main:0',0,FacadeControls(opening_edits=(OpeningEdit(1,1,'suppress'),))),))
    r=resolve_theta(P,t)
    wall=next(w for w in r.walls if w.mass_role=='main:0' and w.edge==0)
    assert len(wall.axes_m)==5
    assert len(wall.facade.openings)==14
    assert r.theta.facades[0].controls.balcony_depth_m==.8
    assert r.theta.facades[0].controls.window_ratio==r.theta.facade.window_ratio


def test_same_role_refs_canonical_under_json_reordering():
    left=ArchitecturalMass('main',((0.,0.),(5.,0.),(5.,16.),(0.,16.)),(0.,2.8,5.6))
    right=ArchitecturalMass('main',((5.,0.),(10.,0.),(10.,16.),(5.,16.)),(0.,2.8,5.6))
    t=ThetaCandidate(massing=MassingControls(pattern='explicit'),masses=(right,left),
                     roofs=(RoofOverride('main:1','corrugated'),))
    a=resolve_theta(P,t)
    b=resolve_theta(P,replace(t,masses=(left,right)))
    assert [m.id for m in a.masses]==['main:0','main:1']
    assert canonical(a)==canonical(b)
    assert next(r for r in a.roofs if r.mass_id=='main:1').surfaces[0].kind=='corrugated'
    with pytest.raises(ValueError,match='ambiguous'):
        resolve_theta(P,replace(t,roofs=(RoofOverride('main','corrugated'),)))


def test_stable_evidence_and_xi_completion():
    from pipeline.theta import reconstruct
    t=replace(T,massing=MassingControls(pattern='stepped_back',upper_setback_m=None),
              roofs=(RoofOverride('setback:0',kind=None),))
    e={'theta.massing.upper_setback_m':Evidence('unknown'),
       'theta.roofs[setback:0].kind':Evidence('unknown')}
    a=reconstruct(ReconstructionRequest(P,t,NuisanceParameters(1),evidence=e))
    b=reconstruct(ReconstructionRequest(P,t,NuisanceParameters(2),evidence=e))
    assert canonical(a.resolved)==canonical(b.resolved)
    assert a.requested.evidence==e and a.requested.theta.massing.upper_setback_m is None
    assert a.resolved.completion_details['massing.upper_setback_m']['source']=='prior/completed'
    assert a.resolved.completion_details['massing.upper_setback_m']['value']==2.5
    assert a.resolved.masses==b.resolved.masses and a.resolved.roofs==b.resolved.roofs
