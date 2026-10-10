"""Facade charts, domain ownership and geometry, independent of benchmark IDs."""
from dataclasses import asdict, replace
import hashlib
import json

import numpy as np
import pytest
from shapely.geometry import box
from shapely.ops import unary_union

from domain.theta import (FacadeControls, FacadeZone, FaceBand, MassComponent,
                          MassingControls, PlanRegion, ReconstructionContext,
                          ThetaCandidate, RoofControls, NuisanceParameters,
                          ReconstructionRequest, canonical, from_json)
from domain.models import Opening, FacadeProjection, FacadeMaterialRegion
from modeling.theta import resolve_theta, generate_resolved
from test_compositional_massing import semantic_vertices


P=ReconstructionContext(((0.,0.),(12.,0.),(12.,20.),(0.,20.)),(0,))
BLIND=FacadeControls(mode='explicit',openings=())


def explicit(tag, width=1.):
    return FacadeControls(mode='explicit',openings=(
        Opening('window',.5,.6,width,1.5,prefab='slim_window',source=tag),))


def body(zones=(), **kwargs):
    return MassComponent('main',PlanRegion(depth_m=(4.,20.)),(0.,3.,6.),zones=zones,**kwargs)


def solve(component, *others, context=P):
    return resolve_theta(context,ThetaCandidate(schema_version='0.3',
        massing=MassingControls(components=(component,*others)),roof=RoofControls(parapet_m=0.)))


def front(plan):
    return [w for w in plan.walls if w.mass_role=='main:0' and w.edge==0]


def mask(wall):
    return unary_union([box(u0,z0+wall.base_z,u1,z1+wall.base_z) for u0,z0,u1,z1 in wall.visible_domains])


def assert_partition(walls, area):
    masks=[mask(w) for w in walls]
    assert sum(m.area for m in masks)==pytest.approx(area,abs=1e-5)
    assert unary_union(masks).area==pytest.approx(area,abs=1e-5)
    assert all(a.intersection(b).area<1e-8 for i,a in enumerate(masks) for b in masks[i+1:])


def test_facade_zone_three_horizontal_regions():
    zones=tuple(FacadeZone('front',explicit(tag,width),u=span,role=tag) for tag,span,width in
                [('left',(0.,.25),.6),('middle',(.25,.60),1.),('right',(.60,1.),1.4)])
    plan=solve(body(zones))
    walls=front(plan)
    assert len(walls)==3
    for wall,zone in zip(walls,zones):
        start,end=np.array(zone.u)*12
        op,=wall.facade.openings
        assert op.source==zone.role
        assert op.u_m==pytest.approx(start+.5)
        assert start<=op.u_m<op.u_m+op.width_m<=end<=12
        assert wall.facade.vertex_a==(0.,4.)  # shared original chart
        assert wall.facade.width_m==12
    assert_partition(walls,72.)
    assert plan.masses==solve(body()).masses
    assert plan.roofs==solve(body()).roofs
    mesh=generate_resolved(plan,NuisanceParameters(curtains=False))
    assert len(semantic_vertices(mesh,'slim_frame'))>0
    # No duplicate exterior wall triangles: projected shell area equals the
    # domain area minus apertures (ignore back/side/top faces of the shell).
    triangles=[]
    for comp in mesh.components:
        if comp['assembly_id'].startswith('main:0/edge0/') and comp['name']=='wall':
            triangles.extend(mesh.vertices[mesh.faces[comp['face_start']:comp['face_start']+comp['face_count']]])
    exterior=[t for t in triangles if np.allclose(t[:,1],4.)]
    area=sum(abs(np.cross(t[1]-t[0],t[2]-t[0])[1])/2 for t in exterior)
    assert area==pytest.approx(72.-3*1.5,abs=1e-5)


def test_facade_zone_combines_u_and_z():
    zones=(FacadeZone('front',explicit('A',.7),(0.,.5),(0.,3.)),
           FacadeZone('front',explicit('B',1.1),(0.,.5),(3.,6.)),
           FacadeZone('front',explicit('C',1.5),(.5,1.),(0.,6.)))
    walls=front(solve(body(zones)))
    assert_partition(walls,72.)
    expected={'A':(.5,.6),'B':(.5,3.6),'C':(6.5,.6)}
    for wall in walls:
        for op in wall.facade.openings:
            assert (op.u_m,op.v_m)==pytest.approx(expected[op.source])
            assert mask(wall).covers(box(op.u_m,op.v_m,op.u_m+op.width_m,op.v_m+op.height_m))


def test_facade_zone_blind_region():
    repeat=FacadeControls(bay_count=1,balconies=False,projections=())
    zones=(FacadeZone('front',repeat,(0.,.3)),FacadeZone('front',BLIND,(.3,.6)),
           FacadeZone('front',repeat,(.6,1.)))
    plan=solve(body(zones,facade=FacadeControls(bay_count=4)))
    walls=front(plan)
    assert not walls[1].facade.openings and walls[0].facade.openings and walls[2].facade.openings
    assert_partition(walls,72.)
    mesh=generate_resolved(plan)
    frames=semantic_vertices(mesh,'slim_frame')
    assert not np.any((frames[:,0]>3.6)&(frames[:,0]<7.2)&(frames[:,1]<4.1))
    vertices=semantic_vertices(mesh,'wall')
    assert np.any((vertices[:,0]>=3.6)&(vertices[:,0]<=7.2)&np.isclose(vertices[:,1],4.))


@pytest.mark.parametrize('face',['front','all'])
def test_facade_zone_rejects_overlap(face):
    zones=(FacadeZone('front',BLIND,(0.,.6),(0.,4.)),FacadeZone(face,BLIND,(.5,1.),(3.,6.)))
    with pytest.raises(ValueError,match='overlapping facade zones'):
        solve(body(zones))


def test_facade_zone_preserves_visibility_clipping():
    # Arch crosses occlusion at u=6; its surviving curve/frame must not reflow.
    op=Opening('window',1.,.6,4.,2.,prefab='slim_window',shape='arch')
    controls=FacadeControls(mode='explicit',openings=(op,))
    zone=FacadeZone('front',controls,(.25,.9))
    component=body((zone,))
    visible=solve(component)
    blocker=MassComponent('blocker',PlanRegion(u=(0.,.5),depth_m=(0.,4.)),(0.,3.))
    hidden=solve(component,blocker)
    a=next(w for w in front(visible) if '/zone' in w.facade.edge_id)
    b=next(w for w in front(hidden) if '/zone' in w.facade.edge_id)
    assert a.facade==b.facade and a.axes_m==b.axes_m
    assert b.facade.openings[0].u_m==4.
    assert_partition(front(hidden),54.)
    mesh=generate_resolved(hidden,NuisanceParameters(curtains=False))
    frames=semantic_vertices(mesh,'arched_frame')
    assert len(frames)>0
    assert np.all(frames[:,0]>=6.-1e-5)
    assert frames[:,0].max()<=8.+.1
    assert np.all(frames[:,2]<=2.6+1e-5)


def test_facade_zone_backwards_compatible():
    # Captured from the current 0.3 resolver BEFORE adding FacadeZone.
    component=MassComponent('main',PlanRegion(),(0.,3.,6.),faces=(
        FaceBand('front',FacadeControls(bay_count=2,balconies=False,projections=()),(0.,3.)),
        FaceBand('front',BLIND,(3.,6.))))
    plan=solve(component)
    # The semantic correction splits the old overloaded is_front into street
    # orientation + program_enabled. Compare the old representation as well
    # as the unchanged geometry hashes below.
    legacy=[]
    for wall in plan.walls:
        record=asdict(wall)
        assert record.pop('plane_offset_m')==0.
        record['facade'].pop('program_enabled')
        record['facade']['is_front']=wall.facade.has_program
        legacy.append(record)
    digest=hashlib.sha256(json.dumps(legacy,sort_keys=True).encode()).hexdigest()
    assert digest=='d1e7b295c0599d3d3f81f543feb86d80da03725dfe2545a3d94f6b012ba51067'
    mesh=generate_resolved(plan,NuisanceParameters(curtains=False))
    assert hashlib.sha256(mesh.vertices.tobytes()).hexdigest()=='dda933b82fe5a2b74bf053100c05703d0c3f63e0698990fac548e628bd3bbb2a'
    assert hashlib.sha256(mesh.faces.tobytes()).hexdigest()=='ee74e5d6a538e1c9b586bebf8a228083dc2361474a8502301634a290920c6bce'
    request=json.loads(canonical(ReconstructionRequest(P,plan.theta)))
    del request['theta']['massing']['components'][0]['zones']
    assert from_json(json.dumps(request)).theta.massing.components[0].zones==()


@pytest.mark.parametrize('u,z',[
    ((-.1,.5),None),((0.,1.1),None),((.5,.5),None),((.7,.3),None),
    ((0.,1.),(-1.,3.)),((0.,1.),(3.,3.)),((0.,1.),(5.,3.)),((0.,1.),(0.,7.)),
    ((float('nan'),1.),None),((0.,1.),(0.,float('inf')))])
def test_facade_zone_rejects_invalid_bounds(u,z):
    with pytest.raises(ValueError):
        solve(body((FacadeZone('front',BLIND,u,z),)))


def test_facade_zone_fallback_does_not_recompose_remaining_width_or_bands():
    base=FacadeControls(bay_count=3,balconies=False,projections=())
    bands=(FaceBand('front',base,(0.,3.)),FaceBand('front',explicit('upper'),(3.,6.)))
    unzoned=solve(body(faces=bands))
    zoned=solve(body((FacadeZone('front',BLIND,(.3,.6),(1.,5.)),),faces=bands))
    assert [w.facade for w in front(unzoned)]==[w.facade for w in front(zoned) if '/zone' not in w.facade.edge_id]
    assert_partition(front(zoned),72.)
    # A blind rectangle punches a hole in the base ownership, not its wall.
    assert mask(front(zoned)[0]).intersection(box(3.6,1.,7.2,3.)).area<1e-8


def test_facade_zone_repeat_normalizes_width_and_preserves_storey_indices():
    from domain.theta import OpeningEdit
    controls=FacadeControls(bay_count=2,balconies=False,projections=(),
                            opening_edits=(OpeningEdit(1,0,'suppress'),))
    component=body((FacadeZone('front',controls,(.5,1.),(3.,6.)),))
    for width in (12.,20.):
        p=replace(P,parcel=((0.,0.),(width,0.),(width,20.),(0.,20.)))
        wall=next(w for w in front(solve(component,context=p)) if '/zone' in w.facade.edge_id)
        assert len(wall.axes_m)==2
        assert width*.5<wall.axes_m[0]<wall.axes_m[1]<width
        op,=wall.facade.openings
        assert op.kind=='window' and op.u_m>wall.axes_m[0] and op.v_m>=3


def test_facade_zone_translates_all_entities_and_roundtrips():
    controls=replace(explicit('A'),
        projections=(FacadeProjection('panel',.2,.1,1.,.2,.1),),
        material_regions=(FacadeMaterialRegion(0.,0.,3.,3.,'stone'),))
    plan=solve(body((FacadeZone('front',controls,(.5,1.),(3.,6.),'upper_right'),)))
    wall=next(w for w in front(plan) if '/zone' in w.facade.edge_id)
    assert wall.facade.projections[0].u_m==6.2
    assert wall.facade.projections[0].v_m==3.1
    assert wall.facade.material_regions[0].u_m==6.
    request=ReconstructionRequest(P,plan.theta)
    assert canonical(from_json(canonical(request)))==canonical(request)
    assert len(generate_resolved(plan).faces)>0


def test_facade_zone_invalid_entity_rejected_even_when_hidden():
    component=body((FacadeZone('front',explicit('outside',width=8.),(.5,1.)),))
    blocker=MassComponent('blocker',PlanRegion(depth_m=(0.,4.)),(0.,3.,6.))
    with pytest.raises(ValueError,match='outside local bounds'):
        solve(component,blocker)


def test_facade_zone_repeat_axes_do_not_reflow_with_exposure():
    controls=FacadeControls(bay_count=3,balconies=False,projections=())
    component=body((FacadeZone('front',controls,(.25,1.)),))
    blocker=MassComponent('blocker',PlanRegion(u=(0.,.5),depth_m=(0.,4.)),(0.,3.))
    original=next(w for w in front(solve(component)) if '/zone' in w.facade.edge_id)
    clipped=next(w for w in front(solve(component,blocker)) if '/zone' in w.facade.edge_id)
    assert original.axes_m==clipped.axes_m
    assert original.facade==clipped.facade
    assert mask(original).area>mask(clipped).area


def test_facade_zone_blind_override_does_not_leave_base_entrance_step():
    base=FacadeControls(mode='explicit',openings=(Opening('door',4.5,.1,1.2,2.3),))
    component=body((FacadeZone('front',BLIND,(.3,.6)),),faces=(FaceBand('front',base),))
    mesh=generate_resolved(solve(component))
    assert len(semantic_vertices(mesh,'entrance_step'))==0


def test_facade_zone_chart_follows_rotated_component_faces():
    # Rotated rectangle, no axis-aligned world-coordinate assumptions.
    p=replace(P,parcel=((20.,10.),(20.,22.),(0.,22.),(0.,10.)),fronts=(0,))
    from modeling.assembly import region_frame
    component=MassComponent('main',PlanRegion(),(0.,3.,6.),zones=(
        FacadeZone('front',explicit('front'),(.2,.8)),
        FacadeZone('back',explicit('back'),(.2,.8)),
        FacadeZone('left',explicit('left'),(.2,.8)),
        FacadeZone('right',explicit('right'),(.2,.8))))
    plan=solve(component,context=p)
    _,t,n,_=region_frame(plan.context,component.region)
    normals={'front':-n,'back':n,'left':-t,'right':t}
    for wall in plan.walls:
        if '/zone' not in wall.facade.edge_id:
            continue
        op,=wall.facade.openings
        assert np.allclose(wall.facade.normal_xy,normals[op.source])
        assert op.u_m==pytest.approx(wall.facade.width_m*.2+.5)
    assert len([w for w in plan.walls if '/zone' in w.facade.edge_id])==4


def test_facade_zone_vertical_origin_is_relative_to_elevated_component():
    from domain.theta import SupportControls
    component=replace(body((FacadeZone('front',explicit('upper'),(.5,1.),(3.,6.)),)),
                      levels_m=(3.,6.,9.),support=SupportControls(kind='columns'))
    wall=next(w for w in front(solve(component)) if '/zone' in w.facade.edge_id)
    assert wall.base_z==3.
    assert wall.facade.openings[0].v_m==3.6
    assert wall.base_z+wall.facade.openings[0].v_m==6.6


@pytest.mark.parametrize('face,edge',[('front',0),('right',1),('back',2),('left',3)])
def test_facade_zone_program_does_not_imply_street_front(face,edge):
    plan=solve(body((FacadeZone(face,explicit(face),(.2,.8)),)))
    wall=next(w for w in plan.walls if '/zone' in w.facade.edge_id)
    assert wall.edge==edge
    assert wall.facade.is_front is (face=='front')
    assert wall.facade.program_enabled is True and wall.facade.has_program
    assert all(w.facade.is_front is (w.edge==0) for w in plan.walls)
    mesh=generate_resolved(plan,NuisanceParameters(curtains=False))
    frames=semantic_vertices(mesh,'slim_frame')
    assert len(frames)>0  # side/back openings must still emit real geometry
    # Equivalent to the old overloaded flag, including wall treatments.
    legacy=replace(plan,walls=tuple(replace(w,facade=replace(w.facade,
        is_front=w.facade.has_program,program_enabled=None)) for w in plan.walls))
    previous=generate_resolved(legacy,NuisanceParameters(curtains=False))
    assert np.array_equal(mesh.vertices,previous.vertices)
    assert np.array_equal(mesh.faces,previous.faces)
    assert np.array_equal(mesh.face_materials,previous.face_materials)


def test_facade_zone_side_can_face_a_second_street():
    # The local face label is not a street predicate either.
    p=replace(P,fronts=(0,1))
    component=replace(body((FacadeZone('right',explicit('side'),(.2,.8)),)),
                      region=PlanRegion(front_edge=0,depth_m=(4.,20.)))
    wall=next(w for w in solve(component,context=p).walls if '/zone' in w.facade.edge_id)
    assert wall.edge==1 and wall.facade.is_front and wall.facade.has_program
